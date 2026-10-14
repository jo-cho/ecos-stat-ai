"""한국은행 ECOS 전용, 단일 질의형 경제통계 AI 웹 프로그램."""
from __future__ import annotations

import asyncio
import json
from html import escape

import streamlit as st
from dotenv import load_dotenv

from ecos_ai.agent import answer
from ecos_ai.presentation import build_report
from ecos_ai.rendering import prepare_table_frame, render_chart_png, static_table_html

load_dotenv()
st.set_page_config(page_title="경제통계 AI 검색", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

EXAMPLES = [
    "국고채(3년) 금리 추이를 그려줘",
    "2026년 소비자물가지수 추이와 전년동월대비 상승률 그래프를 그려줘.",
    "최근 3년간 전국 및 서울 아파트 매매가격지수의 전월대비 상승률 그래프를 그려줘",
]
PROGRESS = {
    "starting": "질문에서 통계지표와 조회 기간을 파악하고 있어요.",
    "find_statistics": "ECOS에서 질문과 관련된 통계표를 탐색하고 있어요.",
    "get_statistic_items": "통계 항목·지역·주기·단위를 확인하고 있어요.",
    "get_statistic_data": "ECOS에서 실제 통계 수치를 수집하고 있어요.",
    "get_key_statistics": "ECOS 주요 경제지표를 확인하고 있어요.",
    "preparing_answer": "조회한 정보를 검토하고 분석을 진행하고 있어요.",
    "finishing": "표·그래프·통계 요약을 구성하고 있어요.",
}

CSS = """
<style>
:root { --ink:#142840; --blue:#1b54c5; --teal:#117d80; --line:#e3eaf4; }
.stApp { background: linear-gradient(180deg,#eff5ff 0px,#f7f9fc 230px,#f6f8fb 100%); }
.block-container { max-width:1180px; padding-top:2.0rem; padding-bottom:4rem; }
.econ-hero {
  border-radius:22px; padding:32px 36px; color:white;
  background:radial-gradient(circle at 90% 2%,rgba(69,190,207,.31),transparent 37%),
             linear-gradient(110deg,#132b61 5%,#205cc9 70%,#237a9e 115%);
  box-shadow:0 17px 40px rgba(16,48,118,.17); margin-bottom:22px;
}
.econ-hero .eyebrow {font-size:.82rem; letter-spacing:.12em; text-transform:uppercase;
  color:#baddff; font-weight:700; margin-bottom:10px;}
.econ-hero h1 { color:white !important; font-size:2.15rem; margin:0 0 10px; letter-spacing:-.035em; }
.econ-hero p {font-size:1rem; color:#e2efff; margin:0; line-height:1.7;}
.econ-info { display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; }
.econ-pill {font-size:.76rem; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.19);
 color:#edf7ff; padding:6px 12px; border-radius:100px; }
.econ-section {display:flex; align-items:center; justify-content:space-between; gap:12px; margin:28px 0 13px; }
.econ-section h2 {margin:0; font-size:1.3rem; letter-spacing:-.03em; color:var(--ink);}
.econ-section .sub {color:#61718a; font-size:.83rem;}
.econ-card {border:1px solid #e3eaf5; border-radius:17px; padding:19px 24px;
 background:#fff; box-shadow:0 6px 21px rgba(32,62,105,.045); margin-bottom:14px;}
.econ-card-title {font-size:1.03rem; color:#193351; font-weight:720; margin-bottom:8px;}
.econ-micro {font-size:.81rem; color:#7a8ba1; margin-top:6px;}
.econ-table-scroller {border:1px solid #e5eaf3; border-radius:12px; max-height:475px;
 overflow-x:auto; overflow-y:auto; background:#fff;}
.econ-table {border-collapse:collapse; min-width:100%; font-size:.86rem; font-variant-numeric:tabular-nums;}
.econ-table th {position:sticky; top:0; z-index:2; background:#eaf1fc; color:#244466;
 text-align:right; white-space:nowrap; padding:11px 16px; border-bottom:1px solid #cfdbea;}
.econ-table th:first-child {text-align:left;}
.econ-table td {white-space:nowrap; padding:10px 16px; border-bottom:1px solid #e9eef6; color:#233954;}
.econ-table td.number {text-align:right;}
.econ-table td.period {font-weight:650; color:#1b4382; background:#f9fbff;}
.econ-table tr:nth-child(even) td {background:#f8fafd;}
.econ-table tr:hover td {background:#eef5ff;}
.econ-summary-line {margin:9px 0; line-height:1.75; color:#29415b;
 padding:10px 13px; background:#f4f8ff; border-left:3px solid #3c76d6; border-radius:6px;}
section[data-testid='stSidebar'] {background:#f0f5fd; border-right:1px solid #dce7f6;}
section[data-testid='stSidebar'] .stButton button {border-radius:11px; white-space:normal; height:auto;
 min-height:44px; padding:10px 13px; text-align:left; background:#fff; border:1px solid #dce6f4;}
div[data-testid='stTextArea'] textarea {border-radius:13px; border:1px solid #d6e1f1; background:#fff;
 font-size:1.03rem; padding:17px;}
div.stButton > button[kind='primary'] {border-radius:12px; font-weight:700; min-height:48px;
 box-shadow:0 6px 16px rgba(38,89,184,.18);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def _clear_result() -> None:
    # 질문이나 인증 정보가 바뀌면 기존 사용자 결과를 화면에서 제거
    st.session_state.single_result = None


def _set_example(value: str) -> None:
    # 예시는 질문 입력창만 채우며 이전 질의의 대화 문맥은 사용하지 않음
    st.session_state.question_text = value
    _clear_result()


def _display_answer(question: str, result: dict) -> None:
    # 표와 그래프의 값은 LLM 텍스트가 아닌 MCP로 조회한 ECOS 원자료에서만 생성
    report = build_report(question, result.get("calls", []))

    if report["has_data"]:
        st.markdown("<div class='econ-section'><h2>01 · 통계 그래프</h2><span class='sub'>Matplotlib · 정적 이미지</span></div>",
                    unsafe_allow_html=True)
        for number, chart in enumerate(report["charts"]):
            with st.container(border=True):
                st.markdown(f"<div class='econ-card-title'>{escape(chart['title'])}</div>", unsafe_allow_html=True)
                try:
                    image = render_chart_png(chart)
                    st.image(image, use_container_width=True)
                    st.download_button("PNG 저장", data=image, file_name=f"ecos_chart_{number + 1}.png",
                                       mime="image/png", key=f"chart_png_{number}")
                except (ValueError, TypeError) as exc:
                    st.warning("그래프를 생성할 수 없습니다. 자료의 시점과 수치 형식을 확인해 주세요.")

        st.markdown("<div class='econ-section'><h2>02 · 통계표</h2><span class='sub'>최근 행부터 표시 · 정렬·편집 없음</span></div>",
                    unsafe_allow_html=True)
        for number, table in enumerate(report["tables"]):
            with st.container(border=True):
                st.markdown(f"<div class='econ-card-title'>{escape(table['title'])}</div>", unsafe_allow_html=True)
                try:
                    # 인덱스 이름에 의존하지 않으므로 KeyError('시점') 발생 방지
                    table_frame = prepare_table_frame(table["data"], table["cycle"])
                    st.markdown(static_table_html(table_frame), unsafe_allow_html=True)
                    visible = min(len(table_frame), 60)
                    st.caption(f"표에는 최근 {visible:,}개 시점을 표시합니다. 전체 {len(table_frame):,}개 시점은 CSV에서 확인할 수 있습니다.")
                    st.download_button(
                        "전체 통계표 CSV 저장", data=table_frame.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"ecos_table_{number + 1}.csv", mime="text/csv", key=f"table_csv_{number}"
                    )
                except (ValueError, TypeError) as exc:
                    st.warning("통계표 표시 중 문제가 발생했습니다. 아래 조회 진단을 확인해 주세요.")

        for warning in report["warnings"]:
            st.warning(warning)

        st.markdown("<div class='econ-section'><h2>03 · 통계 요약</h2><span class='sub'>ECOS 수치 기반 · 사실 정보만</span></div>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            if report["summary"]:
                for line in report["summary"]:
                    st.markdown(f"<div class='econ-summary-line'>{escape(line)}</div>", unsafe_allow_html=True)
            else:
                st.info("요약할 수 있는 유효 수치가 없습니다.")
            st.caption("요약은 ECOS 조회값만 이용합니다. 경기 원인이나 정책 효과를 임의로 추정하지 않습니다.")
    else:
        diagnostic = report.get("diagnostics", {})
        if diagnostic.get("calls", 0) == 0:
            st.info("ECOS 통계표 또는 항목 검색만 수행되었습니다. 실제 시계열 조회가 실행되지 않았습니다.")
        elif diagnostic.get("errors"):
            st.error("ECOS 수치 조회 과정에서 오류가 발생했습니다. 아래 데이터 진단을 확인해 주세요.")
        elif diagnostic.get("received_rows", 0) == 0:
            st.info("ECOS에서 조회 조건에 해당하는 시계열 행을 반환하지 않았습니다.")
        elif diagnostic.get("accepted_rows", 0) == 0:
            st.warning("ECOS 응답은 있었지만 수치 또는 시점 형식을 읽을 수 없었습니다.")
        else:
            st.info("ECOS 수치는 수신했지만 질문에 지정된 표시 기간 내 자료가 없습니다.")
        for warning in report.get("warnings", []):
            st.warning(warning)
        if result.get("text"):
            with st.expander("질의 처리 안내", expanded=False):
                st.write(result["text"])
        if diagnostic.get("calls", 0):
            with st.expander("데이터 진단", expanded=False):
                st.write(f"시계열 조회: {diagnostic['calls']}회 / 성공: {diagnostic['successful_calls']}회")
                st.write(f"수신 행: {diagnostic['received_rows']}건 / 유효 수치: {diagnostic['accepted_rows']}건")
                st.write(f"시점 해석 실패: {diagnostic['invalid_period_rows']}건 / 값 해석 실패: {diagnostic['invalid_value_rows']}건")
                if diagnostic.get("available_period"):
                    st.write("수신 기간: " + " ~ ".join(diagnostic["available_period"]))
                if diagnostic.get("errors"):
                    st.write("오류 유형: " + ", ".join(dict.fromkeys(diagnostic["errors"])))

    # 조회 근거는 기본적으로 접어서 사용자 요청에만 표시
    if report.get("sources"):
        with st.expander("조회 기준 및 ECOS 출처", expanded=False):
            st.caption("경제통계 데이터의 유일한 외부 출처: 한국은행 ECOS Open API")
            for src in report["sources"]:
                st.markdown(f"**{src['stat_name'] or '통계명 미확인'}** (`{src['stat_code']}`)")
                st.caption(
                    f"주기: {src['cycle']} · 요청 기간: {' ~ '.join(map(str, src['requested_period']))} "
                    f"· API 조회일: {src['retrieved_on']} · 총 수신 대상: {src['total_count']}건"
                )
                if src.get("item_codes"):
                    st.caption("통계항목 코드: " + ", ".join(src["item_codes"]))
                if src.get("truncated"):
                    st.warning("조회 상한으로 일부 자료가 제외됐을 수 있습니다.")
    if result.get("calls"):
        with st.expander("MCP 호출 기록", expanded=False):
            for call in result["calls"]:
                st.markdown(f"**{escape(call['tool'])}** · {'성공' if call['success'] else '오류'}")
                if call.get("row_count") is not None:
                    st.caption(f"반환 행: {call['row_count']}건")
                st.code(json.dumps(call.get("arguments", {}), ensure_ascii=False, indent=2), language="json")


# 화면은 질의 하나와 그 답변 하나만 유지함
if "single_result" not in st.session_state:
    st.session_state.single_result = None
if "question_text" not in st.session_state:
    st.session_state.question_text = ""

with st.sidebar:
    st.markdown("### 🔐 개인 API 키")
    st.caption("입력한 키는 현재 Streamlit 세션에서만 사용됩니다.")
    ecos_key = st.text_input("한국은행 ECOS API 키", type="password", key="ecos_key", on_change=_clear_result)
    openai_key = st.text_input("OpenAI API 키", type="password", key="openai_key", on_change=_clear_result)
    ready = bool(ecos_key.strip() and openai_key.strip())
    if ready:
        st.success("키 입력 완료 · 실제 접속 시 유효성 확인")
    else:
        st.info("질문 실행을 위해 두 API 키를 입력하세요.")
    st.divider()
    st.markdown("### 💡 추천 질문")
    for i, example in enumerate(EXAMPLES):
        st.button(example, key=f"example_{i}", on_click=_set_example, args=(example,), use_container_width=True)
    st.divider()
    if st.button("새 질문 시작", use_container_width=True):
        st.session_state.question_text = ""
        _clear_result()
        st.rerun()
    st.caption("수치는 ECOS에서만 가져옵니다. LLM은 질문 해석에 이용됩니다.")
    st.caption("공유 사이트에 입력한 키는 사이트 운영자와 클라우드 인프라를 신뢰할 수 있는 경우에만 사용하세요.")

st.markdown(
    """<div class='econ-hero'>
      <div class='eyebrow'>ECOS · Statistical Intelligence</div>
      <h1>경제통계 AI 검색</h1>
      <p>경제지표를 자연어로 물어보세요. 한국은행 ECOS의 실측 데이터를 바탕으로<br>
      정돈된 그래프, 통계표, 핵심 수치를 한 화면에 제공합니다.</p>
      <div class='econ-info'>
        <span class='econ-pill'>ECOS 단일 데이터 출처</span>
        <span class='econ-pill'>정적 고해상도 그래프</span>
        <span class='econ-pill'>한 번에 하나의 질문</span>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown("**궁금한 경제통계를 입력하세요**")
    st.text_area("경제통계 질문", key="question_text", label_visibility="collapsed", height=112,
                 placeholder="예: 2026년 소비자물가지수 추이와 전년동월대비 상승률을 보여줘",
                 on_change=_clear_result)
    submitted = st.button("📊 ECOS 통계 조회하기", type="primary", use_container_width=True, disabled=not ready)
    st.caption("새 질문을 실행하면 이전 결과는 대체됩니다. 이전 질문의 맥락을 이어받지 않습니다.")

if submitted:
    question = st.session_state.question_text.strip()
    _clear_result()
    if not question:
        st.warning("경제통계에 관한 질문을 입력해 주세요.")
    else:
        seen_stages = set()
        with st.status(PROGRESS["starting"], expanded=True) as status:
            def on_progress(stage: str) -> None:
                # 실제 MCP 및 LLM 처리 단계가 변할 때만 메시지를 갱신
                label = PROGRESS.get(stage)
                if label:
                    status.update(label=label, state="running")
                    if stage not in seen_stages:
                        status.write(label)
                        seen_stages.add(stage)
            try:
                response = asyncio.run(answer(
                    question, history=[], ecos_api_key=ecos_key,
                    openai_api_key=openai_key, on_progress=on_progress,
                ))
                st.session_state.single_result = {"question": question, "result": response}
                status.update(label="조회와 답변 구성이 완료되었습니다.", state="complete", expanded=False)
            except Exception as exc:
                # 비밀키 등이 포함된 원본 예외 문자열은 화면에 노출하지 않음
                st.session_state.single_result = {
                    "question": question,
                    "result": {"text": f"처리 실패: {type(exc).__name__}. API 키와 ECOS 서비스를 확인해 주세요.", "calls": []},
                }
                status.update(label="조회 중 문제가 발생했습니다.", state="error", expanded=False)

if st.session_state.single_result is not None:
    saved = st.session_state.single_result
    st.markdown("<div class='econ-section'><h2>조회 결과</h2><span class='sub'>최근 실행한 질문 1건</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='econ-card'><strong>질문</strong>　{escape(saved['question'])}</div>", unsafe_allow_html=True)
    _display_answer(saved["question"], saved["result"])
else:
    st.markdown("<div class='econ-section'><h2>이용 안내</h2></div>", unsafe_allow_html=True)
    cols = st.columns(3)
    for col, title, description in zip(cols,
                                       ("01　질문 입력", "02　ECOS 실측 조회", "03　시각화·요약 확인"),
                                       ("경제지표와 원하는 기간을 입력합니다.",
                                        "통계표와 항목을 확인하고 수치를 가져옵니다.",
                                        "정적 그래프와 표, 통계 중심 요약을 확인합니다.")):
        with col:
            st.markdown(f"<div class='econ-card'><strong>{escape(title)}</strong><p class='econ-micro'>{escape(description)}</p></div>",
                        unsafe_allow_html=True)
