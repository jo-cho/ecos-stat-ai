"""한국은행 ECOS에만 연결되는 읽기 전용 API 클라이언트."""
import os
import re
import json
import time
import tempfile
from pathlib import Path
from datetime import date
from urllib.parse import quote
import requests

ROOT = 'https://ecos.bok.or.kr/api'
CYCLES = {'A': r'\d{4}', 'S': r'\d{4}S[12]', 'Q': r'\d{4}Q[1-4]',
          'M': r'\d{6}', 'SM': r'\d{6}S[12]', 'D': r'\d{8}'}

class EcosError(Exception):
    pass

class EcosAPI:
    def __init__(self, api_key=None, page_size=None, max_rows=None, session=None):
        self.key = api_key or os.getenv('ECOS_API_KEY', '')
        if not self.key:
            raise EcosError('ECOS_API_KEY를 .env에 설정하세요.')
        self.page_size = min(1000, max(1, int(page_size or os.getenv('ECOS_PAGE_SIZE', '500'))))
        self.max_rows = min(10000, max(1, int(max_rows or os.getenv('ECOS_MAX_ROWS', '3000'))))
        self.session = session or requests.Session()
        self.timeout = (float(os.getenv('ECOS_CONNECT_TIMEOUT', '15')),
                        float(os.getenv('ECOS_READ_TIMEOUT', '50')))
        self.retries = min(2, max(0, int(os.getenv('ECOS_RETRIES', '2'))))
        self.cache_dir = Path(os.getenv('ECOS_CACHE_DIR', str(Path(tempfile.gettempdir()) / 'ecos-stat-ai')))
        self.cache_ttl = max(0, int(os.getenv('ECOS_CACHE_TTL', '86400')))

    def catalog(self):
        # 인증키를 저장하지 않는 공개 메타데이터 캐시를 질문 간 재사용
        path = self.cache_dir / 'catalog-v1.json'
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            result = saved['result']
            if (0 <= time.time() - saved['saved_at'] < self.cache_ttl
                    and isinstance(result.get('rows'), list) and not result.get('truncated')):
                return result
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
        result = self.pages('StatisticTableList')
        if not result['truncated']:
            temporary = None
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.cache_dir,
                                                 delete=False) as handle:
                    json.dump({'saved_at': time.time(), 'result': result}, handle, ensure_ascii=False)
                    temporary = Path(handle.name)
                temporary.replace(path)
            except OSError:
                pass
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return result

    def _get(self, url):
        # 시간 초과와 일시적 서버 오류만 제한적으로 재시도
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if getattr(response, 'status_code', 200) in (429, 502, 503, 504) and attempt < self.retries:
                    response.close()
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return response
            except (requests.Timeout, requests.ConnectionError):
                if attempt >= self.retries:
                    raise
                time.sleep(0.5 * (attempt + 1))

    def request(self, service, start=1, end=100, *args):
        allowed = {'StatisticTableList', 'StatisticItemList', 'StatisticSearch', 'KeyStatisticList', 'StatisticWord'}
        if service not in allowed:
            raise EcosError('허용되지 않은 ECOS 서비스')
        parts = [service, self.key, 'json', 'kr', str(start), str(end)]
        parts.extend(str(p) for p in args)
        url = ROOT + '/' + '/'.join(quote(p, safe='') for p in parts)
        try:
            res = self._get(url)
            res.raise_for_status()
            payload = res.json()
        except requests.ConnectTimeout:
            raise EcosError(f'{service}: ECOS 서버 연결 시간이 초과되었습니다.') from None
        except requests.Timeout:
            raise EcosError(f'{service}: ECOS API 응답 시간이 초과되었습니다. 잠시 후 다시 조회하세요.') from None
        except requests.HTTPError as exc:
            # 전체 URL에 API 키가 포함되므로 상태 코드만 노출
            status = getattr(getattr(exc, 'response', None), 'status_code', '알 수 없음')
            raise EcosError(f'ECOS HTTP 오류(상태 코드 {status})') from None
        except requests.RequestException:
            raise EcosError('ECOS 네트워크 연결에 실패했습니다.') from None
        except ValueError:
            raise EcosError('ECOS 응답을 JSON으로 읽지 못했습니다.') from None
        if 'RESULT' in payload:
            detail = payload['RESULT']
            raise EcosError(f"ECOS: {detail.get('CODE', '')}: {detail.get('MESSAGE', '')}")
        data = payload.get(service)
        if not isinstance(data, dict):
            raise EcosError('ECOS 응답 형식이 예상과 다릅니다.')
        if 'RESULT' in data:
            detail = data['RESULT']
            raise EcosError(f"ECOS: {detail.get('CODE', '')}: {detail.get('MESSAGE', '')}")
        return data

    def pages(self, service, *args, limit=None):
        cap = min(self.max_rows, limit or self.max_rows)
        rows = []
        while len(rows) < cap:
            start = len(rows) + 1
            end = min(start + self.page_size - 1, cap)
            data = self.request(service, start, end, *args)
            batch = data.get('row', []) or []
            rows.extend(batch)
            total = int(data.get('list_total_count', len(rows)))
            if len(rows) >= total or not batch:
                break
        return {'rows': rows, 'total_count': total, 'truncated': len(rows) < total}

    def tables(self, keyword, limit=20):
        if not keyword or len(keyword.strip()) < 2:
            raise EcosError('두 글자 이상의 통계표 검색어가 필요합니다.')
        # 통계표 전체를 순회한 뒤 실제 ECOS 메타데이터만 대상으로 필터링
        result = self.catalog()
        terms = [t.casefold() for t in keyword.split() if t.strip()]
        matched = []
        for r in result['rows']:
            title = str(r.get('STAT_NAME', ''))
            if r.get('SRCH_YN') == 'Y' and all(t in title.casefold() for t in terms):
                matched.append({'stat_code': r.get('STAT_CODE'), 'stat_name': title,
                                'cycle': r.get('CYCLE'), 'org': r.get('ORG_NAME')})
        return {'matches': matched[:min(max(1, limit), 30)], 'catalog_truncated': result['truncated'],
                'note': '검색 결과가 없으면 통계표명 중 더 짧은 핵심어로 재검색하세요.'}

    def items(self, stat_code, limit=100):
        self._code(stat_code)
        limit = min(300, max(1, int(limit)))
        data = self.pages('StatisticItemList', stat_code, limit=limit)
        out = []
        for r in data['rows'][:min(limit, 300)]:
            out.append({'item_code': r.get('ITEM_CODE'), 'item_name': r.get('ITEM_NAME'),
                        'group': r.get('GRP_CODE'), 'cycle': r.get('CYCLE'),
                        'unit': r.get('UNIT_NAME'), 'start': r.get('START_TIME'),
                        'end': r.get('END_TIME')})
        return {'stat_code': stat_code, 'items': out,
                'total_count': data['total_count'],
                'truncated': data['truncated'] or len(data['rows']) > len(out)}

    @staticmethod
    def _code(code):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', str(code)):
            raise EcosError('통계 코드 형식이 올바르지 않습니다.')

    @staticmethod
    def _period(cycle, value):
        if cycle not in CYCLES or not re.fullmatch(CYCLES[cycle], value):
            raise EcosError('조회 주기와 기간 형식이 일치하지 않습니다.')
        # 월/일 값이 유효한지 확인
        try:
            if cycle == 'M':
                date(int(value[:4]), int(value[4:6]), 1)
            if cycle == 'D':
                date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            raise EcosError('존재하지 않는 날짜입니다.') from None

    def series(self, stat_code, cycle, start, end, item_code1='', item_code2='', item_code3='', item_code4=''):
        self._code(stat_code)
        self._period(cycle, start)
        self._period(cycle, end)
        if start > end:
            raise EcosError('조회 시작일이 종료일보다 늦습니다.')
        item_codes = [item_code1, item_code2, item_code3, item_code4]
        for code in item_codes:
            if code:
                self._code(code)
        while item_codes and not item_codes[-1]:
            item_codes.pop()
        if not item_codes:
            raise EcosError('통계항목 코드가 필요합니다. get_statistic_items로 확인하세요.')
        # ECOS 다차원 항목 경로의 공백은 ?로 표시
        args = [stat_code, cycle, start, end] + [x or '?' for x in item_codes]
        result = self.pages('StatisticSearch', *args)
        rows = []
        for r in result['rows']:
            rows.append({k: r.get(k) for k in ('STAT_CODE', 'STAT_NAME', 'ITEM_CODE1',
                'ITEM_NAME1', 'ITEM_CODE2', 'ITEM_NAME2', 'ITEM_CODE3', 'ITEM_NAME3',
                'ITEM_CODE4', 'ITEM_NAME4', 'TIME', 'DATA_VALUE', 'UNIT_NAME')})
        return {'source': '한국은행 ECOS Open API', 'retrieved_on': date.today().isoformat(),
                'stat_code': stat_code, 'cycle': cycle, 'requested_period': [start, end],
                'total_count': result['total_count'], 'truncated': result['truncated'], 'rows': rows}

    def keywords(self, limit=30):
        result = self.pages('KeyStatisticList', limit=min(limit, 100))
        return {'source': '한국은행 ECOS Open API', 'rows': result['rows'][:limit]}
