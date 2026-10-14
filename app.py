"""한국은행 ECOS 데이터를 조회하는 단일 검색 화면."""
import asyncio
import json
import time
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from ecos_ai.agent import answer, clean_suggestions
from ecos_ai.periods import to_timestamp

load_dotenv()
st.set_page_config(page_title='경제통계 AI 검색', layout='wide')

MODELS = {
    'GPT-5.5': 'gpt-5.5',
    'GPT-5 mini': 'gpt-5-mini',
    'GPT-4.1': 'gpt-4.1',
    'GPT-4.1 mini': 'gpt-4.1-mini',
    'GPT-6 Luna': 'gpt-6-luna'
    
}
EXAMPLES = [
    '2026년 월별 소비자물가 상승률 추이를 알려줘',
    '전국 및 서울 아파트 매매가격의 2년간 추이를 비교해줘',
    '가장 최신 경상수지 통계를 조회해줘',
]
LOADING = ['KDI 빅데이터분석팀 경제통계 AI를 찾아주셔서 감사합니다.','경제통계 검색을 준비하고 있어요.', '관련 통계 자료를 살펴보고 있어요.','한국은행 ECOS에서 관련 통계를 찾았어요',
           '잠시만 기다려 주세요. 조회를 진행하고 있어요.', '답변을 준비 중이에요. 조금만 기다려 주세요.']

st.markdown('''<style>
.stApp {background:#f7f9fc;}
.block-container {max-width:1060px;padding-top:3rem;}
h1 {letter-spacing:-.045em;}
div[data-testid="stTextArea"] textarea {border-radius:12px;font-size:1.05rem;}
div.stButton>button {border-radius:10px;}
</style>''', unsafe_allow_html=True)

if 'search_result' not in st.session_state:
    st.session_state.search_result = None
if 'show_raw' not in st.session_state:
    st.session_state.show_raw = False
if 'question' not in st.session_state:
    st.session_state.question = ''


def clear_result():
    st.session_state.search_result = None
    st.session_state.show_raw = False


def choose_example(value):
    st.session_state.question = value
    clear_result()


def reset_search():
    st.session_state.question = ''
    clear_result()


async def run_search(question, model, ecos_key, openai_key, status):
    # 실제 작업을 비동기로 기다리며 안내 문구만 주기적으로 갱신
    task = asyncio.create_task(answer(question, history=[], model=model,
                                     ecos_api_key=ecos_key, openai_api_key=openai_key))
    started = time.monotonic()
    index = 0
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=2.5)
            if not task.done():
                index += 1
                elapsed = int(time.monotonic() - started)
                status.update(label=f'{LOADING[index % len(LOADING)]} · {elapsed}초', state='running')
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


with st.sidebar:
    st.subheader('검색 설정')
    ecos_key = st.text_input('한국은행 ECOS API 키', type='password', key='ecos_key', on_change=clear_result)
    openai_key = st.text_input('OpenAI API 키', type='password', key='openai_key', on_change=clear_result)
    selected = st.selectbox('GPT 모델', list(MODELS), key='model', on_change=clear_result)
    st.caption('선택한 모델의 사용 가능 여부는 API 계정 권한에 따라 달라집니다.')
    st.divider()
    st.button('새 검색', on_click=reset_search, use_container_width=True)
    st.caption('입력한 키는 현재 세션에서 사용하며 파일에 저장하지 않습니다.')

st.title('경제통계 AI 검색')
st.caption('궁금한 경제지표를 검색하세요. 한국은행 ECOS 자료로 답변합니다.')
with st.container(border=True):
    st.text_area('경제통계 질문', key='question', height=110,
                 placeholder='지표와 원하는 기간을 입력해 주세요.', on_change=clear_result)
    submitted = st.button('검색하기', type='primary', use_container_width=True,
                          disabled=not (ecos_key.strip() and openai_key.strip()))
    st.caption('검색마다 새로운 질문으로 처리하며, 이전 결과는 교체됩니다.')

if not st.session_state.search_result:
    st.caption('질문 예시')
    columns = st.columns(3)
    for i, example in enumerate(EXAMPLES):
        columns[i].button(example, key=f'example_{i}', on_click=choose_example,
                          args=(example,), use_container_width=True)

if submitted:
    clear_result()
    question = st.session_state.question.strip()
    if not question:
        st.warning('검색할 질문을 입력해 주세요.')
    else:
        with st.status(LOADING[0], expanded=False) as status:
            try:
                response = asyncio.run(run_search(question, MODELS[selected], ecos_key, openai_key, status))
                failed = any(not c.get('success') for c in response.get('calls', []))
                status.update(label='일부 조회에 실패했습니다.' if failed else '검색이 완료되었습니다.',
                              state='error' if failed else 'complete', expanded=False)
                st.session_state.search_result = {'question': question, 'response': response, 'model': selected}
            except Exception as exc:
                status.update(label='검색을 완료하지 못했습니다.', state='error')
                st.error(f'처리 오류: {type(exc).__name__}. API 키, 모델 사용 권한과 연결 상태를 확인해 주세요.')

saved = st.session_state.search_result
if saved:
    response = saved['response']
    st.divider()
    st.subheader('검색 결과')
    st.caption(saved['question'])
    st.markdown(response.get('text') or '답변을 생성하지 못했습니다.')
    if st.button('원데이터 닫기' if st.session_state.show_raw else '원데이터 확인하기', key='raw_data'):
        st.session_state.show_raw = not st.session_state.show_raw
        st.rerun()
    if st.session_state.show_raw:
        st.subheader('ECOS 원데이터')
        found = False
        for i, call in enumerate(response.get('calls', [])):
            result = call.get('result') or {}
            rows = result.get('rows')
            if not call.get('success') or not rows:
                continue
            found = True
            df = pd.DataFrame(rows)
            st.markdown(f"**{df.iloc[0].get('STAT_NAME') or '통계 자료'}**")
            # 표와 CSV는 ECOS에서 받은 원본 열과 값을 그대로 제공
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button('원데이터 CSV 다운로드', df.to_csv(index=False).encode('utf-8-sig'),
                               file_name=f'ecos_raw_{i}.csv', mime='text/csv', key=f'csv_{i}')
            if not {'TIME', 'DATA_VALUE'}.issubset(df.columns):
                continue
            # 그래프용 변환만 별도 사본에 적용하고 원자료는 변경하지 않음
            plot = df.copy()
            cycle = str(result.get('cycle') or call.get('arguments', {}).get('cycle') or '')
            plot['시점'] = plot['TIME'].map(lambda value: to_timestamp(str(value), cycle))
            plot['수치'] = pd.to_numeric(plot['DATA_VALUE'].astype(str).str.replace(',', '', regex=False), errors='coerce')
            names = [k for k in ('ITEM_NAME1', 'ITEM_NAME2', 'ITEM_NAME3', 'ITEM_NAME4') if k in plot]
            codes = [k for k in ('ITEM_CODE1', 'ITEM_CODE2', 'ITEM_CODE3', 'ITEM_CODE4') if k in plot]
            plot['계열'] = plot.apply(lambda row: ' / '.join(str(row.get(k) or '') for k in names).strip(' / ') or '수치', axis=1)
            if codes:
                plot['계열'] += plot[codes].fillna('').astype(str).apply(lambda row: ' (' + '/'.join(row) + ')', axis=1)
            plot['단위'] = plot['UNIT_NAME'].fillna('') if 'UNIT_NAME' in plot else ''
            for unit, group in plot.dropna(subset=['시점', '수치']).groupby('단위', dropna=False):
                chart = group.drop_duplicates(['시점', '계열'], keep='last').pivot(index='시점', columns='계열', values='수치').sort_index()
                if not chart.empty:
                    st.caption(f"단위: {unit or '미제공'}")
                    st.line_chart(chart, use_container_width=True)
            if result.get('truncated'):
                st.warning('조회 상한으로 원데이터 일부가 제외되었습니다.')
        if not found:
            st.info('이번 검색에는 확인할 수 있는 시계열 원데이터가 없습니다.')
    suggestions = clean_suggestions(response.get('suggestions'), saved['question'])
    if suggestions:
        st.subheader('이런 검색도 해보세요')
        for i, suggestion in enumerate(suggestions):
            st.button(suggestion, key=f'suggestion_{i}', on_click=choose_example,
                      args=(suggestion,), use_container_width=True)
    with st.expander('조회 정보 및 출처', expanded=False):
        st.caption(f"출처: 한국은행 ECOS Open API · 모델: {saved['model']}")
        if response.get('query_info'):
            st.markdown(response['query_info'])
        for call in response.get('calls', []):
            result = call.get('result') or {}
            if result:
                st.write({k: result[k] for k in ('stat_code', 'cycle', 'requested_period',
                                                'retrieved_on', 'total_count', 'truncated') if k in result})
        with st.expander('도구 호출 기록', expanded=False):
            for call in response.get('calls', []):
                st.write(f"{call['tool']} · {'성공' if call.get('success') else '실패'}")
                st.code(json.dumps(call.get('arguments', {}), ensure_ascii=False, indent=2), language='json')
