"""ECOS 시계열을 표·그래프·정량 요약으로 변환하는 표시 계층.

외부 서비스 요청을 수행하지 않으며, MCP로 조회한 ECOS 원자료만 사용합니다.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
import re
from typing import Any

import pandas as pd

from ecos_ai.mcp_result import normalize_series_payload


ITEM_CODE_KEYS = tuple(f"ITEM_CODE{i}" for i in range(1, 5))
ITEM_NAME_KEYS = tuple(f"ITEM_NAME{i}" for i in range(1, 5))


def _normalize_result(value: Any) -> dict:
    # 기존 세션에 저장된 JSON 텍스트 래퍼도 읽어 복구
    try:
        return normalize_series_payload(value)
    except ValueError:
        return {}


def _to_timestamp(value: str, cycle: str) -> pd.Timestamp | None:
    # 주기별 날짜를 표준 시간 인덱스로 변환
    value = str(value).strip()
    try:
        if cycle == 'A' and re.fullmatch(r'\d{4}', value):
            return pd.Timestamp(int(value), 1, 1)
        if cycle == 'M' and re.fullmatch(r'\d{6}', value):
            return pd.Timestamp(int(value[:4]), int(value[4:]), 1)
        if cycle == 'D' and re.fullmatch(r'\d{8}', value):
            return pd.Timestamp(int(value[:4]), int(value[4:6]), int(value[6:]))
        if cycle == 'Q' and re.fullmatch(r'\d{4}Q[1-4]', value):
            return pd.Timestamp(int(value[:4]), (int(value[-1]) - 1) * 3 + 1, 1)
        if cycle == 'S' and re.fullmatch(r'\d{4}S[12]', value):
            return pd.Timestamp(int(value[:4]), 1 if value[-1] == '1' else 7, 1)
        if cycle == 'SM' and re.fullmatch(r'\d{6}S[12]', value):
            return pd.Timestamp(int(value[:4]), int(value[4:6]), 1 if value[-1] == '1' else 16)
    except (ValueError, TypeError):
        return None
    return None


def _label(row: dict) -> str:
    # 지역·상품 종류를 구별하여 여러 계열의 범례를 생성
    values = [str(row.get(k, '') or '').strip() for k in ITEM_NAME_KEYS]
    labels = list(dict.fromkeys(v for v in values if v and v != 'None'))
    if labels:
        return ' / '.join(labels)
    return str(row.get('STAT_NAME') or row.get('STAT_CODE') or '통계 계열')


def _growth_request(question: str) -> tuple[str | None, int]:
    # 명시적인 전년동월비·전월비 요청에 한해서만 파생값을 계산
    compact = re.sub(r'\s+', '', question)
    if any(x in compact for x in ('전년동월대비', '전년동월비', '전년같은달대비')):
        return ('전년동월대비 상승률', 12)
    if any(x in compact for x in ('전월대비', '전월비', '전달대비')):
        return ('전월대비 상승률', 1)
    return (None, 0)


def _window(df: pd.DataFrame, question: str, today: date) -> pd.DataFrame:
    # 파생 증가율 계산 후 사용자 질의의 표시 기간으로 제한
    explicit = [int(y) for y in re.findall(r'(?<!\d)(20\d{2})\s*년', question)]
    if explicit:
        year_start, year_end = min(explicit), max(explicit)
        return df.loc[(df.index.year >= year_start) & (df.index.year <= year_end)]
    relative = re.search(r'최근\s*(\d{1,2})\s*년', question)
    if relative:
        years = min(int(relative.group(1)), 30)
        if years > 0:
            cutoff = pd.Timestamp(today.year - years, today.month, 1)
            # 최근 3년이면 현재 월을 포함한 최대 36개월을 표시
            cutoff += pd.DateOffset(months=1)
            return df.loc[(df.index >= cutoff) & (df.index <= pd.Timestamp(today))]
    return df


def _unit_text(value: object) -> str:
    return str(value or '').strip()


def _fmt_num(value: float) -> str:
    if abs(value) >= 1000:
        return f'{value:,.1f}'
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


def _wide(group: pd.DataFrame) -> pd.DataFrame:
    if group.empty:
        return pd.DataFrame()
    # 같은 시점의 중복 조회값은 가장 마지막 값을 선택
    selected = group.drop_duplicates(['timestamp', 'series_key'], keep='last')
    return selected.pivot(index='timestamp', columns='series_key', values='value').sort_index()


def build_report(question: str, calls: list[dict], today: date | None = None) -> dict:
    """MCP 호출 기록을 사용자가 보는 수치 요약·시계열·표로 변환합니다."""
    today = today or datetime.now(ZoneInfo('Asia/Seoul')).date()
    records = []
    sources = []
    truncated = False
    seen_sources = set()
    diagnostics = {'calls': 0, 'successful_calls': 0, 'received_rows': 0,
                   'invalid_period_rows': 0, 'invalid_value_rows': 0,
                   'accepted_rows': 0, 'errors': [], 'available_period': None}
    seen_times = []

    for call in calls or []:
        if call.get('tool') != 'get_statistic_data':
            continue
        diagnostics['calls'] += 1
        if not call.get('success'):
            diagnostics['errors'].append(str(call.get('error_type') or '도구 호출 오류'))
            continue
        result = _normalize_result(call.get('result'))
        rows = result.get('rows', [])
        if not isinstance(rows, list) or not result:
            diagnostics['errors'].append('MCP 통계 결과 구조를 인식하지 못했습니다.')
            continue
        diagnostics['successful_calls'] += 1
        diagnostics['received_rows'] += len(rows)
        truncated = truncated or bool(result.get('truncated'))
        cycle = str(result.get('cycle') or '').upper()
        for row in rows:
            if not isinstance(row, dict):
                continue
            ts = _to_timestamp(row.get('TIME', ''), cycle)
            if ts is None:
                diagnostics['invalid_period_rows'] += 1
                continue
            numeric = pd.to_numeric(
                str(row.get('DATA_VALUE', '') or '').replace(',', '').strip(),
                errors='coerce',
            )
            if pd.isna(numeric):
                diagnostics['invalid_value_rows'] += 1
                continue
            diagnostics['accepted_rows'] += 1
            seen_times.append(ts)
            code = str(row.get('STAT_CODE') or result.get('stat_code') or '')
            item_codes = tuple(str(row.get(k) or '') for k in ITEM_CODE_KEYS)
            series_key = (code, cycle, *item_codes)
            records.append({
                'timestamp': ts,
                'value': float(numeric),
                'series_key': series_key,
                'raw_label': _label(row),
                'stat_name': str(row.get('STAT_NAME') or ''),
                'stat_code': code,
                'cycle': cycle,
                'unit': _unit_text(row.get('UNIT_NAME')),
            })
        # API 키나 전체 요청 인수는 출처 정보에 포함하지 않음
        requested_items = tuple(
            str(call.get('arguments', {}).get(f'item_code{i}', '') or '')
            for i in range(1, 5)
        )
        source_key = (str(result.get('stat_code') or ''), cycle,
                      str(result.get('requested_period') or ''), requested_items)
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append({
                'stat_code': source_key[0], 'cycle': cycle,
                'stat_name': str(rows[0].get('STAT_NAME') or '') if rows else '',
                'item_codes': [code for code in requested_items if code],
                'requested_period': result.get('requested_period', []),
                'retrieved_on': result.get('retrieved_on', ''),
                'total_count': result.get('total_count', len(rows)),
                'truncated': bool(result.get('truncated')),
            })

    if seen_times:
        diagnostics['available_period'] = [min(seen_times).strftime('%Y-%m-%d'),
                                           max(seen_times).strftime('%Y-%m-%d')]
    if not records:
        warnings = []
        if diagnostics['calls'] and diagnostics['successful_calls'] == 0:
            warnings.append('ECOS 통계 조회가 정상 완료되지 않았습니다. MCP 호출 상세 기록을 확인해 주세요.')
        elif diagnostics['received_rows'] == 0 and diagnostics['successful_calls']:
            warnings.append('ECOS가 반환한 시계열 행이 없습니다. 통계항목과 조회 기간을 확인해 주세요.')
        elif diagnostics['received_rows']:
            warnings.append('ECOS 응답은 있으나 시점(TIME) 또는 수치(DATA_VALUE)를 읽을 수 없습니다.')
        return {'charts': [], 'tables': [], 'summary': [], 'sources': sources,
                'truncated': truncated, 'has_data': False, 'warnings': warnings,
                'diagnostics': diagnostics}

    frame = pd.DataFrame.from_records(records)
    catalog = frame.groupby('series_key', sort=False).first()
    # 항목명이 동일하다면 통계표명과 코드를 이용하여 범례 충돌을 제거
    raw_labels = {key: row['raw_label'] for key, row in catalog.iterrows()}
    counts = pd.Series(list(raw_labels.values())).value_counts().to_dict()
    labels = {}
    for key, row in catalog.iterrows():
        name = raw_labels[key]
        if counts[name] > 1:
            name = f"{row['stat_name']} / {name} ({row['stat_code']})"
        labels[key] = name

    charts = []
    tables = []
    summary = []
    warnings = []
    growth_name, lag = _growth_request(question)

    for (cycle, unit), group in frame.groupby(['cycle', 'unit'], sort=False):
        base = _wide(group)
        if base.empty:
            continue
        base.columns = [labels[key] for key in base.columns]
        # 월별 기준의 증가율만 계산; 결측 월은 자동으로 채우지 않음
        growth = None
        if growth_name is not None and cycle == 'M':
            full_months = pd.date_range(base.index.min(), base.index.max(), freq='MS')
            complete = base.reindex(full_months)
            # 공식 증가율 계열을 다시 증가율로 변환하는 오류 방지
            is_rate = any(w in unit for w in ('%', '퍼센트')) or any(
                any(w in str(s) for w in ('증감률', '상승률', '변동률')) for s in base.columns
            )
            if is_rate:
                warnings.append('조회 계열이 이미 비율 또는 증감률 형태입니다. 중복 증가율 계산을 생략했습니다.')
            else:
                previous = complete.shift(lag)
                growth = (complete / previous.where(previous != 0) - 1) * 100
        elif growth_name is not None:
            warnings.append('전월·전년동월 증가율 계산에는 ECOS 월별(M) 원계열이 필요합니다.')

        shown = _window(base, question, today).dropna(how="all")
        # 명시적 기간과 조회 기간이 맞지 않을 때 앞 기간을 억지로 표시하지 않음
        if shown.empty:
            warnings.append('질문에서 요청한 기간에 해당하는 조회값이 없습니다.')
            continue
        charts.append({'title': f"원자료 추이 ({unit or '단위 미제공'})", 'data': shown,
                       'unit': unit, 'cycle': cycle, 'kind': 'original'})
        tables.append({'title': f"통계표 · 원자료 ({unit or '단위 미제공'})",
                       'data': shown, 'unit': unit, 'cycle': cycle, 'kind': 'original'})

        for label in shown.columns[:6]:
            observed = shown[label].dropna()
            if observed.empty:
                continue
            first, last = observed.index[0], observed.index[-1]
            summary.append(f"{label}: {first:%Y-%m-%d} {_fmt_num(float(observed.iloc[0]))}"
                           f" → {last:%Y-%m-%d} {_fmt_num(float(observed.iloc[-1]))} {unit}".strip())

        if growth is not None:
            visible_growth = _window(growth, question, today)
            visible_growth = visible_growth.dropna(how='all')
            if visible_growth.empty:
                warnings.append(f'{growth_name}을 계산하기 위한 비교 기준월 데이터가 부족합니다. 이전 기간을 추가 조회해 주세요.')
            else:
                charts.append({'title': f'{growth_name} (%)', 'data': visible_growth,
                               'unit': '%', 'cycle': cycle, 'kind': 'growth'})
                tables.append({'title': f'통계표 · {growth_name} (%)', 'data': visible_growth,
                               'unit': '%', 'cycle': cycle, 'kind': 'growth'})
                for label in visible_growth.columns[:6]:
                    observed = visible_growth[label].dropna()
                    if not observed.empty:
                        summary.append(f"{label}: {observed.index[-1]:%Y-%m} {growth_name} "
                                       f"{_fmt_num(float(observed.iloc[-1]))}% (ECOS 원자료 계산)")

    if truncated:
        warnings.append('ECOS 조회 결과 일부가 행 수 상한에 의해 잘렸습니다. 전체 기간 결과로 해석하지 마세요.')
    if not charts and diagnostics['available_period']:
        warnings.append('ECOS 수치는 받았지만 질문의 표시 기간에 포함되는 값이 없습니다. '
                        f"ECOS 수신 범위: {diagnostics['available_period'][0]} ~ "
                        f"{diagnostics['available_period'][1]}")
    return {'charts': charts, 'tables': tables, 'summary': summary[:12],
            'sources': sources, 'truncated': truncated, 'warnings': list(dict.fromkeys(warnings)),
            'has_data': bool(charts), 'diagnostics': diagnostics}
