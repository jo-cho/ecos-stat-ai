"""ECOS 시계열을 정적 PNG 그래프와 읽기 전용 HTML 통계표로 변환합니다."""
from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from threading import RLock

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib import dates as mdates
from matplotlib import ticker as mticker
from matplotlib import font_manager
import numpy as np
import pandas as pd

# 공유 Streamlit 환경에서 사용자별 동시 그래프 생성 시 충돌을 방지
_CHART_LOCK = RLock()
_PALETTE = ("#2563eb", "#0f766e", "#d97706", "#7c3aed", "#e11d48", "#0891b2", "#4f46e5", "#475569")


def _font_family():
    # Cloud의 나눔고딕과 Windows의 맑은 고딕을 자동으로 선택
    families = {font.name for font in font_manager.fontManager.ttflist}
    for name in ('NanumGothic', 'Malgun Gothic', 'Noto Sans CJK KR', 'AppleGothic'):
        if name in families:
            return name
    return 'DejaVu Sans'


def format_period(value: object, cycle: str) -> str:
    """인덱스의 이름과 무관하게 통계 주기의 표시 시점을 변환합니다."""
    if isinstance(value, pd.Period):
        value = value.to_timestamp()
    try:
        timestamp = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError):
        return str(value)
    if pd.isna(timestamp):
        return "-"
    if cycle == "M":
        return timestamp.strftime("%Y-%m")
    if cycle == "A":
        return timestamp.strftime("%Y")
    if cycle == "Q":
        return f"{timestamp.year}년 {(timestamp.month - 1) // 3 + 1}분기"
    if cycle == "S":
        return f"{timestamp.year}년 {1 if timestamp.month <= 6 else 2}반기"
    if cycle == "SM":
        return f"{timestamp.year}-{timestamp.month:02d} {1 if timestamp.day <= 15 else 2}반월"
    return timestamp.strftime("%Y-%m-%d")


def prepare_table_frame(data: pd.DataFrame, cycle: str) -> pd.DataFrame:
    """Pandas 인덱스 이름이 무엇이든 '시점' 열을 확실하게 생성합니다."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("표 데이터는 DataFrame이어야 합니다.")

    # reset_index/rename에 의존하지 않고 새 표를 구성하여 KeyError를 원천 차단
    periods = [format_period(value, cycle) for value in data.index]
    result = pd.DataFrame({"시점": periods})
    for position, raw_name in enumerate(data.columns):
        name = str(raw_name)
        if name == "시점":
            name = "시점 (원자료)"
        if name in result.columns:
            name = f"{name} ({position + 1})"
        result[name] = pd.to_numeric(data.iloc[:, position], errors="coerce").to_numpy()
    return result


def format_value(value: object) -> str:
    """표에서 숫자 자리수를 통일하고 결측값은 대시로 표시합니다."""
    if value is None or pd.isna(value):
        return "—"
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    if not np.isfinite(num):
        return "—"
    if abs(num) >= 1000:
        return f"{num:,.1f}"
    if abs(num) >= 1:
        return f"{num:,.2f}".rstrip("0").rstrip(".")
    return f"{num:,.4f}".rstrip("0").rstrip(".") if num != 0 else "0"


def static_table_html(table: pd.DataFrame, max_rows: int = 60) -> str:
    """편집 및 정렬 UI가 없는 안전한 정적 HTML 표를 생성합니다."""
    if "시점" not in table.columns:
        raise ValueError("표에 시점 열이 필요합니다.")
    display = table.tail(max(1, max_rows)).iloc[::-1]
    headers = "".join(f"<th scope='col'>{escape(str(col))}</th>" for col in display.columns)
    body = []
    for _, record in display.iterrows():
        cells = [f"<td class='period'>{escape(str(record.iloc[0]))}</td>"]
        cells.extend(f"<td class='number'>{escape(format_value(val))}</td>" for val in record.iloc[1:])
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<div class='econ-table-scroller' role='region' aria-label='경제통계 표'>"
        "<table class='econ-table'><thead><tr>" + headers + "</tr></thead>"
        "<tbody>" + "".join(body) + "</tbody></table></div>"
    )


def _format_tick(value: float, _pos: int) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:,.1f}"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:,.3f}"


def render_chart_png(chart: dict) -> bytes:
    """반응형 웹에 표시할 고해상도 비대화형 PNG 그래프를 생성합니다."""
    df = chart["data"]
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("그릴 통계 데이터가 없습니다.")
    timeline = pd.to_datetime(df.index, errors="coerce")
    if timeline.isna().all():
        raise ValueError("그래프 시점을 날짜로 변환할 수 없습니다.")

    with _CHART_LOCK:
        font = _font_family()
        fig = Figure(figsize=(11.5, 4.6), dpi=150, facecolor="#ffffff")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        ax.set_axisbelow(True)

        all_values = []
        all_times = []
        count = 0
        for i, column in enumerate(df.columns):
            values = pd.to_numeric(df.iloc[:, i], errors="coerce").to_numpy(dtype=float)
            valid = np.isfinite(values) & ~pd.isna(timeline)
            if not valid.any():
                continue
            x = timeline[valid]
            y = values[valid]
            color = _PALETTE[i % len(_PALETTE)]
            # 데이터 구간 사이에 결측이 있으면 선을 임의로 이어 붙이지 않음
            ax.plot(timeline, values, color=color, linewidth=2.5, marker="o" if valid.sum() <= 12 else None,
                    markersize=4.5, label=str(column)[:45], solid_capstyle="round")
            ax.scatter([x[-1]], [y[-1]], s=44, color=color, zorder=4, edgecolors="white", linewidths=1.1)
            all_values.extend(y.tolist())
            all_times.extend(x.tolist())
            count += 1

        if not all_values:
            raise ValueError("그래프로 표시할 유효 수치가 없습니다.")

        ymin, ymax = float(min(all_values)), float(max(all_values))
        spread = ymax - ymin
        # 상수 계열도 적절한 여백을 주어 실제 값이 가운데 표시되도록 설정
        margin = max(spread * 0.12, abs(ymax) * 0.025, 0.05)
        ax.set_ylim(ymin - margin, ymax + margin)
        if chart.get("kind") == "growth" and ymin < 0 < ymax:
            ax.axhline(0, color="#9ca3af", linewidth=1.1, linestyle="--")

        left, right = min(all_times), max(all_times)
        span = (right - left).total_seconds() / 86400
        padding_days = max(10, span * 0.035)
        if span == 0:
            padding_days = 45 if chart.get("cycle") == "M" else 10
        ax.set_xlim(left - pd.Timedelta(days=padding_days), right + pd.Timedelta(days=padding_days))

        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6))
        # 유니코드 마이너스 대신 일반 음수 부호를 사용
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_tick))
        ax.yaxis.grid(True, color="#e7edf5", linewidth=1)
        ax.xaxis.grid(False)
        for name in ("top", "right", "left"):
            ax.spines[name].set_visible(False)
        ax.spines["bottom"].set_color("#d3dce8")
        ax.tick_params(axis="x", labelsize=10, colors="#52647b", length=0, pad=10)
        ax.tick_params(axis="y", labelsize=10, colors="#52647b", length=0, pad=10)
        for text in ax.get_xticklabels() + ax.get_yticklabels():
            text.set_fontfamily(font)

        unit = chart.get("unit") or "단위 미제공"
        ax.text(0, 1.15, f"단위  {unit}", transform=ax.transAxes, fontsize=10,
                color="#6b7d94", fontfamily=font, va="top")
        if count > 1:
            legend = ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.19), ncol=min(count, 4),
                               frameon=False, prop={"family": font, "size": 10},
                               labelcolor="#26364d", handlelength=2.1)
        fig.subplots_adjust(left=0.085, right=0.975, top=0.78, bottom=0.14)
        output = BytesIO()
        fig.savefig(output, format="png", dpi=180, facecolor="#ffffff")
        fig.clear()
        return output.getvalue()
