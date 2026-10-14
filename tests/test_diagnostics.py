"""진단용 오류 분류와 API 키 비공개 처리 테스트."""
from types import SimpleNamespace

import pytest
import requests
from ecos_ai.diagnostics import safe_error_text, tool_error_text
from ecos_ai.ecos import EcosAPI, EcosError


def test_tool_error_detail_is_displayable_without_api_keys():
    # MCP가 반환한 오류 텍스트에 인증키가 포함되어도 제거
    result = SimpleNamespace(content=[SimpleNamespace(text='ECOS 인증 실패 KEY=SECRET987')])
    detail = tool_error_text(result, 'SECRET987')
    assert 'SECRET987' not in detail
    assert 'ECOS 인증 실패' in detail


def test_ecos_url_is_scrubbed():
    # URL 전체가 예외에 남아도 ECOS 인증키 경로를 마스킹
    detail = safe_error_text('GET https://ecos.bok.or.kr/api/StatisticSearch/MYSECRET/json/kr/1/10')
    assert 'MYSECRET' not in detail
    assert '[비공개]' in detail


def test_standard_secret_labels_are_scrubbed():
    msg = safe_error_text('ECOS_API_KEY=KEY123 OPENAI_API_KEY: sk-abcdefghijklmnopqrstuvwxyz')
    assert 'KEY123' not in msg
    assert 'sk-abcdefghijklmnopqrstuvwxyz' not in msg


def test_ecos_api_result_error_is_preserved_without_url():
    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'RESULT': {'CODE': 'ERROR-100', 'MESSAGE': '인증키 오류'}}

    class MockSession:
        def get(self, url, timeout):
            return MockResponse()

    with pytest.raises(EcosError, match='ERROR-100: 인증키 오류'):
        EcosAPI(api_key='SECRETKEY', session=MockSession()).request('KeyStatisticList')


def test_ecos_timeout_does_not_expose_url():
    class SlowSession:
        def get(self, url, timeout):
            raise requests.Timeout('URL에 API 키가 포함되어 있을 수 있음')

    with pytest.raises(EcosError, match='응답 시간이 초과') as error:
        EcosAPI(api_key='PRIVATEKEY', session=SlowSession()).request('KeyStatisticList')
    assert 'PRIVATEKEY' not in str(error.value)
