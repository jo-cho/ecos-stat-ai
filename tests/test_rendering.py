"""실제 ECOS 키 없이 새 표 변환과 정적 그래프를 회귀 테스트합니다."""
from io import BytesIO

import pandas as pd
import pytest
from PIL import Image

from ecos_ai.rendering import prepare_table_frame, render_chart_png, static_table_html


@pytest.mark.parametrize('index_name', [None, 'timestamp', 'TIME', 'index', '임의의 이름', '시점'])
def test_timestamp_col_always_exists(index_name):
    # 기존 KeyError('시점')을 발생시키던 다양한 인덱스 이름을 시험
    data = pd.DataFrame(
        {'전국': [100.0, 100.4], '서울': [101.0, 102.3]},
        index=pd.DatetimeIndex(['2026-01-01', '2026-02-01'], name=index_name),
    )
    frame = prepare_table_frame(data, 'M')
    assert frame.columns[0] == '시점'
    assert frame['시점'].tolist() == ['2026-01', '2026-02']
    assert frame.iloc[1]['서울'] == pytest.approx(102.3)


def test_empty_dataframe_never_throws_key_error():
    # 빈 표도 시점 열을 생성하고 정적 표의 골격을 유지
    frame = prepare_table_frame(pd.DataFrame(index=pd.DatetimeIndex([])), 'M')
    assert list(frame.columns) == ['시점']
    assert '<table' in static_table_html(frame)


def test_period_index_and_quarter():
    frame = pd.DataFrame({'지수': [108]}, index=pd.PeriodIndex(['2026Q3'], freq='Q'))
    assert prepare_table_frame(frame, 'Q')['시점'].iloc[0] == '2026년 3분기'


def test_static_table_escapes_untrusted_labels():
    # ECOS가 돌려준 항목명을 HTML 요소로 해석하지 않는지 확인
    frame = pd.DataFrame({'시점': ['2026-01'], '<script>alert(1)</script>': [12.2]})
    html = static_table_html(frame)
    assert '&lt;script&gt;' in html
    assert '<script>' not in html
    assert '<input' not in html


def test_static_table_limit_rows_and_numeric_format():
    frame = pd.DataFrame({'시점': [f'2026-{i:02d}' for i in range(1, 13)],
                          '금리': [3.1234] * 12})
    html = static_table_html(frame, max_rows=5)
    assert html.count('<tr>') == 6  # 표 머리 1행 + 최근 5행
    assert '2026-12' in html
    assert '2026-01' not in html


def test_png_single_and_multi_series():
    months = pd.date_range('2026-01-01', periods=8, freq='MS', name='TIME')
    for count in [1, 2]:
        data = pd.DataFrame({'전국': [100, 100.5, 101, 100.1, 101, 102, 103, 102]}, index=months)
        if count == 2:
            data['서울'] = [102.2, 101, 103, 105, 101, 106, 107, 107]
        png = render_chart_png({'data': data, 'unit': '2021.6=100', 'cycle': 'M', 'kind': 'original'})
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        img = Image.open(BytesIO(png))
        assert img.width > 1000 and img.height > 500
        img.verify()


def test_png_negative_positive_growth_and_single_point():
    months = pd.DatetimeIndex(['2026-01-01', '2026-03-01'], name='other')
    for values in [[-0.4, 1.25], [2.5, 2.5]]:
        data = pd.DataFrame({'전월비': values}, index=months)
        assert render_chart_png({'data': data, 'unit': '%', 'cycle': 'M', 'kind': 'growth'})
    single = pd.DataFrame({'금리': [2.5]}, index=pd.DatetimeIndex(['2026-02-01']))
    assert render_chart_png({'data': single, 'unit': '%', 'cycle': 'M', 'kind': 'original'})
