"""실제 키 없이 ECOS 응답을 모의 검증합니다."""
import pytest
from ecos_ai.ecos import EcosAPI, EcosError

class MockResponse:
    def __init__(self, obj): self.obj = obj
    def raise_for_status(self): pass
    def json(self): return self.obj

class MockSession:
    def __init__(self, result): self.result = result; self.urls = []
    def get(self, url, timeout):
        self.urls.append(url)
        return MockResponse(self.result)

def test_series_and_provenance():
    session = MockSession({'StatisticSearch': {'list_total_count': 1, 'row': [
        {'STAT_CODE': '722Y001', 'STAT_NAME': '기준금리', 'TIME': '202501',
         'DATA_VALUE': '3.0', 'UNIT_NAME': '연%', 'ITEM_CODE1': '0101000'}]}})
    data = EcosAPI('testkey', session=session).series('722Y001','M','202501','202501','0101000')
    assert data['rows'][0]['DATA_VALUE'] == '3.0'
    assert data['source'] == '한국은행 ECOS Open API'
    assert '/StatisticSearch/testkey/json/kr/1/500/722Y001/M/202501/202501/0101000' in session.urls[0]

def test_invalid_date():
    with pytest.raises(EcosError):
        EcosAPI('testkey').series('722Y001', 'M', '202513', '202514', '0101000')

def test_ecos_error():
    session = MockSession({'RESULT': {'CODE':'ERROR-200','MESSAGE':'오류'}})
    with pytest.raises(EcosError, match='ERROR-200'):
        EcosAPI('testkey', session=session).request('StatisticSearch', 1, 10)

def test_catalog_cache_survives_new_client(tmp_path, monkeypatch):
    monkeypatch.setenv('ECOS_CACHE_DIR', str(tmp_path))
    session = MockSession({'StatisticTableList': {'list_total_count': 1, 'row': [
        {'STAT_CODE': '722Y001', 'STAT_NAME': '기준금리', 'SRCH_YN': 'Y'}]}})
    assert EcosAPI('testkey', session=session).tables('금리')['matches']
    assert EcosAPI('anotherkey', session=session).tables('금리')['matches']
    assert len(session.urls) == 1
    assert 'testkey' not in (tmp_path / 'catalog-v1.json').read_text()


def test_items_only_fetch_requested_limit():
    session = MockSession({'StatisticItemList': {'list_total_count': 1000, 'row': [
        {'ITEM_CODE': str(i)} for i in range(10)]}})
    result = EcosAPI('testkey', session=session).items('722Y001', limit=10)
    assert len(session.urls) == 1
    assert '/1/10/' in session.urls[0]
    assert result['truncated']


def test_timeout_retries_and_safe_error(monkeypatch):
    import requests
    monkeypatch.setenv('ECOS_RETRIES', '1')
    monkeypatch.setattr('ecos_ai.ecos.time.sleep', lambda _: None)
    class TimeoutSession:
        calls = 0
        def get(self, url, timeout):
            self.calls += 1
            raise requests.ReadTimeout(url)
    session = TimeoutSession()
    with pytest.raises(EcosError, match='StatisticTableList.*초과') as error:
        EcosAPI('secretkey', session=session).request('StatisticTableList')
    assert session.calls == 2
    assert 'secretkey' not in str(error.value)

def test_failed_catalog_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv('ECOS_CACHE_DIR', str(tmp_path))
    session = MockSession({'RESULT': {'CODE': 'ERROR-200', 'MESSAGE': '실패'}})
    with pytest.raises(EcosError):
        EcosAPI('testkey', session=session).tables('금리')
    assert not (tmp_path / 'catalog-v1.json').exists()


def test_truncated_catalog_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv('ECOS_CACHE_DIR', str(tmp_path))
    session = MockSession({'StatisticTableList': {'list_total_count': 10, 'row': [
        {'STAT_NAME': '금리', 'SRCH_YN': 'Y'}]}})
    result = EcosAPI('testkey', max_rows=1, session=session).tables('금리')
    assert result['catalog_truncated']
    assert not (tmp_path / 'catalog-v1.json').exists()
