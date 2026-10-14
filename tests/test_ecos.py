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
