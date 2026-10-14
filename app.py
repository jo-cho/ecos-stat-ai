"""ECOS 전용 Streamlit 웹 앱: 요약·차트·통계표 기본 표시."""
import asyncio
import json

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ecos_ai.agent import answer
from ecos_ai.presentation import build_report

load_dotenv()
st.set_page_config(page_title='경제통계 AI 검색', page_icon='📊', layout='wide')
st.title('📊 경제통계 AI 검색')
st.caption('한국은행 ECOS Open API 전용 · 자연어 질문으로 통계 조회·표·그래프 생성')

EXAMPLES = [
    '국고채(3년) 금리 추이를 그려줘',
    '2026년 소비자물가지수 추이와 전년동월대비 상승률 그래프를 그려줘.',
    '최근 3년간 전국 및 서울 아파트 매매가격지수의 전월대비 상승률 그래프를 그려줘',
]

PROGRESS = {
    'starting': '🧠 질문 속 경제지표와 조회 기간을 살펴보고 있어요.',
    'find_statistics': '🔎 한국은행 ECOS에서 알맞은 통계표를 찾고 있어요.',
    'get_statistic_items': '🧩 통계항목, 지역, 주기와 단위를 확인하고 있어요.',
    'get_statistic_data': '📥 ECOS에서 실제 통계 수치를 가져오는 중이에요.',
    'get_key_statistics': '📚 ECOS의 주요 경제지표를 확인하고 있어요.',
    'preparing_answer': '🗺️ 질문에 맞는 통계를 연결하고 답변 흐름을 정리하고 있어요.',
    'finishing': '✍️ 출처와 수치를 확인하며 답변을 정리하고 있어요.',
}


def _display_time(value: pd.Timestamp, cycle: str) -> str:
    # 원자료의 통계 주기에 맞춰 날짜 문자열을 표시
    if cycle == 'M':
        return value.strftime('%Y-%m')
    if cycle == 'A':
        return value.strftime('%Y')
    if cycle == 'Q':
        return f'{value.year}년 {((value.month - 1) // 3) + 1}분기'
    if cycle == 'S':
        return f'{value.year}년 {1 if value.month == 1 else 2}반기'
    return value.strftime('%Y-%m-%d')


def _display_answer(message: dict, index: int, question: str) -> None:
    # 도구 결과에 기반한 정량 요약과 LLM 요약을 동일한 답변에 표시
    report = build_report(question, message.get('calls', []))
    st.markdown('### 📝 요약')
    st.markdown(message['content'])
    if report['summary']:
        st.caption('ECOS 조회값을 기준으로 자동 산출한 핵심 수치')
        for line in report['summary']:
            st.markdown(f'- {line}')

    if report['has_data']:
        st.markdown('### 📈 그래프')
        for chart in report['charts']:
            st.markdown(f"**{chart['title']}**")
            # 다중 계열(전국·서울 등)을 각기 다른 선으로 표시
            st.line_chart(chart['data'], use_container_width=True)

        st.markdown('### 📋 통계표')
        for number, table in enumerate(report['tables']):
            st.markdown(f"**{table['title']}**")
            chart_data = table['data']
            rendered = chart_data.reset_index().rename(columns={'timestamp': '시점'})
            rendered['시점'] = rendered['시점'].map(
                lambda dt: _display_time(dt, table['cycle'])
            )
            st.dataframe(rendered, use_container_width=True, hide_index=True)
            st.download_button(
                f"CSV 다운로드 · {table['title']}",
                data=rendered.to_csv(index=False).encode('utf-8-sig'),
                file_name=f'ecos_results_{index}_{number}.csv',
                mime='text/csv',
                key=f'csv_{index}_{number}',
            )
    else:
        diagnostic = report.get('diagnostics', {})
        if diagnostic.get('calls', 0) == 0:
            st.info('이번 답변에서는 ECOS 수치 조회가 실행되지 않았습니다. 통계표나 항목 검색만 진행됐을 수 있습니다.')
        elif diagnostic.get('errors'):
            st.error('ECOS 수치 조회 결과를 처리하지 못했습니다. 아래 상세 진단을 확인해 주세요.')
        elif diagnostic.get('received_rows', 0) == 0:
            st.info('ECOS 통계 조회는 수행했지만 해당 조건에서 반환된 수치가 없습니다.')
        elif diagnostic.get('accepted_rows', 0) == 0:
            st.error('ECOS 응답은 도착했지만 시점 또는 수치 형식을 해석하지 못했습니다.')
        else:
            st.info('ECOS 원자료는 받았지만 질문에서 지정한 기간에 해당하는 결과가 없습니다.')

    for warning in report['warnings']:
        st.warning(warning)

    if not report['has_data'] and report.get('diagnostics', {}).get('calls', 0):
        with st.expander('데이터 진단 (클릭하여 보기)', expanded=False):
            diagnostic = report['diagnostics']
            st.write(f"시계열 조회 횟수: {diagnostic['calls']}회 · 성공: {diagnostic['successful_calls']}회")
            st.write(f"ECOS 수신 행: {diagnostic['received_rows']}건 · 유효 수치: {diagnostic['accepted_rows']}건")
            st.write(f"시점 해석 실패: {diagnostic['invalid_period_rows']}건 · 수치 해석 실패: {diagnostic['invalid_value_rows']}건")
            if diagnostic.get('available_period'):
                st.write('받은 데이터 기간: ' + ' ~ '.join(diagnostic['available_period']))
            if diagnostic.get('errors'):
                st.write('도구 오류 유형: ' + ', '.join(dict.fromkeys(diagnostic['errors'])))

    # 상세 조회 기준과 호출 기록은 처음부터 열지 않음
    if report['sources']:
        with st.expander('조회 기준 · 출처 (클릭하여 보기)', expanded=False):
            st.caption('데이터 출처: 한국은행 경제통계시스템(ECOS) Open API')
            for item in report['sources']:
                st.write(
                    f"통계표: {item['stat_name']} (`{item['stat_code']}`) · 주기: `{item['cycle']}` · "
                    f"API 조회 기간: {', '.join(map(str, item['requested_period']))} · "
                    f"조회일: {item['retrieved_on']} · 반환 건수: {item['total_count']}"
                )
                if item.get('item_codes'):
                    st.caption('조회 항목 코드: ' + ', '.join(item['item_codes']))
                if item['truncated']:
                    st.warning('조회 상한으로 일부 값이 누락됐을 수 있습니다.')
    if message.get('calls'):
        with st.expander('MCP 호출 기록 (클릭하여 보기)', expanded=False):
            for call in message['calls']:
                st.write(f"{call['tool']} · {'성공' if call['success'] else '오류'}" +
                         (f" · 받은 행 {call['row_count']}개" if call.get('row_count') is not None else ''))
                # 인증키는 도구 인수에 넣지 않으므로 화면으로 노출되지 않음
                st.code(json.dumps(call.get('arguments', {}), ensure_ascii=False, indent=2), language='json')


with st.sidebar:
    st.subheader('API 키 설정')
    st.caption('각 이용자의 API 키는 세션에서만 사용하며 채팅 내역·CSV 파일에 저장하지 않습니다.')
    ecos_key = st.text_input('한국은행 ECOS API 키', type='password',
                             placeholder='ECOS API 키 입력', key='ecos_key')
    openai_key = st.text_input('OpenAI API 키', type='password',
                               placeholder='OpenAI API 키 입력', key='openai_key')
    ready = bool(ecos_key.strip() and openai_key.strip())
    if ready:
        st.success('두 API 키가 입력되었습니다. 키의 유효성은 실제 조회 시 확인합니다.')
    else:
        st.warning('질문하려면 두 API 키를 모두 입력하세요.')
    st.caption('공유 사이트에서 이용자의 키를 관리하는 운영자와 서비스 인프라를 신뢰할 수 있는지 확인하세요.')
    st.divider()
    st.subheader('질문 예시')
    for example in EXAMPLES:
        st.markdown(f'- {example}')
    if st.button('대화 초기화'):
        st.session_state.messages = []
        st.rerun()
    st.info('통계 수치를 추측하지 않고 ECOS 조회 결과만 사용합니다.')

if 'messages' not in st.session_state:
    st.session_state.messages = []

last_question = ''
for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message['role']):
        if message['role'] == 'user':
            last_question = message['content']
            st.markdown(message['content'])
        else:
            _display_answer(message, index, last_question)

question = st.chat_input('경제통계를 자연어로 질문해 주세요', disabled=not ready)
if question:
    history = [
        {'role': msg['role'], 'content': msg['content']}
        for msg in st.session_state.messages
    ]
    st.session_state.messages.append({'role': 'user', 'content': question})
    with st.chat_message('assistant'):
        with st.status(PROGRESS['starting'], expanded=True) as status:
            def on_progress(stage: str) -> None:
                # 실제 도구 호출 단계에 따라 진행 문구를 갱신
                message = PROGRESS.get(stage)
                if message:
                    status.update(label=message, state='running')
                    status.write(message)

            try:
                response = asyncio.run(answer(
                    question, history,
                    ecos_api_key=ecos_key,
                    openai_api_key=openai_key,
                    on_progress=on_progress,
                ))
                status.update(label='✅ ECOS 경제통계 답변을 준비했습니다.',
                              state='complete', expanded=False)
            except Exception as exc:
                # 예외 메시지에 포함될 수 있는 민감정보는 노출하지 않음
                response = {
                    'text': f'요청을 처리하지 못했습니다: {type(exc).__name__}. API 키와 서비스 연결을 확인해 주세요.',
                    'calls': [],
                }
                status.update(label='⚠️ 조회 중 오류가 발생했습니다.', state='error', expanded=False)
        _display_answer({'content': response['text'], 'calls': response['calls']},
                        len(st.session_state.messages), question)
    st.session_state.messages.append({
        'role': 'assistant', 'content': response['text'], 'calls': response['calls']
    })
    # 키가 아닌 조회 결과만 세션 메시지에 저장
