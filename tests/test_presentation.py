"""실제 API 키 없이 표·그래프 생성과 증가율 계산을 검증합니다."""
from datetime import date

import pandas as pd
import pytest

from ecos_ai.presentation import build_report


def _call(rows, start='202501', end='202612'):
    # 실제 ECOS 데이터 구조를 본뜬 테스트 호출 결과 생성
    return {
        'tool': 'get_statistic_data', 'arguments': {}, 'success': True,
        'result': {
            'stat_code': '901Y009', 'cycle': 'M',
            'requested_period': [start, end],
            'retrieved_on': '2026-10-14',
            'total_count': len(rows), 'truncated': False,
            'rows': rows,
        },
    }


def _row(month, value, region='전국', code='A'):
    return {
        'TIME': month, 'DATA_VALUE': str(value),
        'STAT_CODE': '901Y009', 'STAT_NAME': '아파트 매매가격지수',
        'ITEM_CODE1': code, 'ITEM_NAME1': region,
        'UNIT_NAME': '2021.6=100',
    }


def test_monthly_yoy_requires_previous_year_and_shows_only_requested_year():
    # 2025년 1월과 2026년 1월을 비교해 정확히 10%인지 확인
    rows = [_row('202501', 100), _row('202601', 110), _row('202602', 121)]
    report = build_report(
        '2026년 소비자물가지수 추이와 전년동월대비 상승률 그래프를 그려줘.',
        [_call(rows)], today=date(2026, 10, 14),
    )
    assert report['has_data']
    assert len(report['charts']) == 2
    base = report['charts'][0]['data']
    yoy = report['charts'][1]['data']
    assert all(v.year == 2026 for v in base.index)
    assert len(yoy) == 1
    assert yoy.iloc[0, 0] == pytest.approx(10.0)


def test_two_regions_are_separate_series_for_mom():
    rows = [
        _row('202601', 100, '전국', 'A'), _row('202602', 101, '전국', 'A'),
        _row('202601', 100, '서울', 'B'), _row('202602', 103, '서울', 'B'),
    ]
    report = build_report(
        '최근 3년간 전국 및 서울 아파트 매매가격지수의 전월대비 상승률 그래프를 그려줘',
        [_call(rows)], today=date(2026, 10, 14),
    )
    assert len(report['charts']) == 2
    mom = report['charts'][1]['data']
    assert set(mom.columns) == {'전국', '서울'}
    assert mom.loc[pd.Timestamp('2026-02-01'), '서울'] == pytest.approx(3.0)
    assert mom.loc[pd.Timestamp('2026-02-01'), '전국'] == pytest.approx(1.0)


def test_missing_month_is_not_treated_as_previous_month():
    # 2026년 2월 데이터가 없으면 3월의 전월비는 결측 처리
    rows = [_row('202601', 100), _row('202603', 103)]
    report = build_report('2026년 전월대비 상승률을 보여줘',
                          [_call(rows)], today=date(2026, 10, 14))
    assert len(report['charts']) == 1
    assert any('비교 기준월 데이터가 부족' in w for w in report['warnings'])


def test_data_without_rate_request_always_has_table_and_chart():
    rows = [_row('202601', 100), _row('202602', 101)]
    report = build_report('국고채(3년) 금리 추이를 그려줘',
                          [_call(rows)], today=date(2026, 10, 14))
    assert report['has_data']
    assert len(report['charts']) == 1
    assert len(report['tables']) == 1
    assert len(report['summary']) > 0


def test_empty_calls_never_fabricate_values():
    report = build_report('2026년 물가', [], today=date(2026, 10, 14))
    assert report['has_data'] is False
    assert not report['charts']
    assert not report['tables']
