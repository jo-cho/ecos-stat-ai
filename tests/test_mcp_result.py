"""MCP SDK 응답 구조 변화에 대한 회귀 테스트."""
import json
from types import SimpleNamespace
import pytest

from ecos_ai.mcp_result import normalize_mcp_payload, normalize_series_payload
from ecos_ai.presentation import build_report
from datetime import date


PAYLOAD = {
    'stat_code': '111Y001', 'cycle': 'M', 'total_count': 2,
    'requested_period': ['202601', '202602'],
    'rows': [
        {'TIME': '202601', 'DATA_VALUE': '2.5', 'STAT_CODE': '111Y001',
         'STAT_NAME': '국고채 (3년)', 'ITEM_CODE1': 'AA', 'ITEM_NAME1': '국고채 3년', 'UNIT_NAME': '%'},
        {'TIME': '202602', 'DATA_VALUE': '2.7', 'STAT_CODE': '111Y001',
         'STAT_NAME': '국고채 (3년)', 'ITEM_CODE1': 'AA', 'ITEM_NAME1': '국고채 3년', 'UNIT_NAME': '%'},
    ],
}


def test_structured_dict_is_preserved():
    assert normalize_mcp_payload(PAYLOAD, []) == PAYLOAD


def test_structured_wrapped_result_is_unwrapped():
    assert normalize_mcp_payload({'result': PAYLOAD}, []) == PAYLOAD


def test_unstructured_json_text_is_parsed():
    text = SimpleNamespace(text=json.dumps(PAYLOAD, ensure_ascii=False))
    assert normalize_mcp_payload(None, [text]) == PAYLOAD


def test_nested_content_wrapper_is_parsed():
    wrapper = {'content': [{'type': 'text', 'text': json.dumps(PAYLOAD)}]}
    assert normalize_series_payload(wrapper)['rows'] == PAYLOAD['rows']


def test_json_result_string_is_parsed():
    wrapper = {'result': json.dumps(PAYLOAD)}
    assert normalize_series_payload(wrapper)['rows'] == PAYLOAD['rows']


def test_unparseable_text_fails_loudly():
    with pytest.raises(ValueError):
        normalize_mcp_payload(None, [SimpleNamespace(text='invalid')])


def test_unstructured_response_produces_graph_and_table():
    # 이전 v2에서는 성공 호출이어도 result.content만 있으면 모든 도표가 사라졌음
    call = {'tool': 'get_statistic_data', 'success': True,
            'result': {'content': [json.dumps(PAYLOAD)]}, 'arguments': {}}
    report = build_report('국고채(3년) 금리 추이를 그려줘', [call], today=date(2026, 10, 14))
    assert report['has_data']
    assert len(report['charts']) == 1
    assert len(report['tables']) == 1
    assert report['diagnostics']['accepted_rows'] == 2


def test_empty_ecos_response_is_distinguishable_from_invalid_response():
    empty = {**PAYLOAD, 'rows': [], 'total_count': 0}
    report = build_report('2026년', [{'tool': 'get_statistic_data', 'success': True,
                                     'result': empty, 'arguments': {}}], today=date(2026, 10, 14))
    assert not report['has_data']
    assert report['diagnostics']['successful_calls'] == 1
    assert report['diagnostics']['received_rows'] == 0


def test_requested_period_with_no_rows_is_distinguished():
    old = {**PAYLOAD, 'rows': [{**PAYLOAD['rows'][0], 'TIME': '202501'}]}
    report = build_report('2026년 국고채', [{'tool': 'get_statistic_data', 'success': True,
                                         'result': old, 'arguments': {}}], today=date(2026, 10, 14))
    assert not report['has_data']
    assert report['diagnostics']['accepted_rows'] == 1
    assert any('받았지만 질문' in s or 'ECOS 수치는 받았지만' in s for s in report['warnings'])


def test_unsuccessful_mcp_call_has_diagnostic():
    report = build_report('국고채', [{'tool': 'get_statistic_data', 'success': False,
                                    'error_type': 'ValueError', 'result': None}], today=date(2026, 10, 14))
    assert not report['has_data']
    assert report['diagnostics']['errors'] == ['ValueError']
