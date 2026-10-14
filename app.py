"""한국은행 ECOS 데이터를 조회하는 단일 검색 화면."""
import asyncio
import json
import time
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from ecos_ai.agent import answer
from ecos_ai.rendering import render_chart_png
from ecos_ai.periods import to_timestamp

load_dotenv()
st.set_page_config(page_title='경제통계 AI 검색', layout='wide')

MODELS = {
    'GPT-5.5': 'gpt-5.5',
    'GPT-6.1 Sol': 'gpt-6.1-sol',
    'GPT-6 Luna': 'gpt-6-luna',
    'GPT-6 Astra': 'gpt-6-astra',
    'GPT-5 mini': 'gpt-5-mini',
}
EXAMPLES = [
    '최근 3년간 한국은행 기준금리 추이를 알려줘',
    '2026년 월별 소비자물가지수를 보여줘',
    '최신 경상수지 통계를 조회해줘',
]
LOADING = ['경제통계 검색을 준비하고 있어요.', '관련 통계 자료를 살펴보고 있어요.',
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
if 'question' not in st.session_state:
    st.session_state.question = ''


def clear_result():
    st.session_state.search_result = None


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
    for i, call in enumerate(response.get('calls', [])):
        result = call.get('result') or {}
        rows = result.get('rows')
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if not {'TIME', 'DATA_VALUE'}.issubset(df.columns):
            continue
        df['수치'] = pd.to_numeric(df['DATA_VALUE'], errors='coerce')
        names = [k for k in ('ITEM_NAME1', 'ITEM_NAME2', 'ITEM_NAME3', 'ITEM_NAME4') if k in df]
        st.markdown(f"**{df.iloc[0].get('STAT_NAME') or '통계 자료'}**")
        ids = [k for k in ('ITEM_CODE1', 'ITEM_CODE2', 'ITEM_CODE3', 'ITEM_CODE4') if k in df]
        if ids and len(df[ids].drop_duplicates()) == 1 and df['수치'].notna().any():
            plot = df[['TIME', '수치']].dropna().drop_duplicates('TIME').sort_values('TIME')
            # ECOS 주기를 이용해 날짜를 해석하고 Matplotlib 정적 이미지로 표시
            cycle = str(result.get('cycle') or call.get('arguments', {}).get('cycle') or 'M')
            plot['시점'] = plot['TIME'].map(lambda value: to_timestamp(str(value), cycle))
            plot = plot.dropna(subset=['시점']).sort_values('시점')
            if not plot.empty:
                unit = str(df.iloc[0].get('UNIT_NAME') or '')
                label = ' / '.join(str(df.iloc[0].get(k) or '') for k in names).strip(' / ') or '수치'
                chart_data = plot.set_index('시점')[['수치']].rename(columns={'수치': label})
                image = render_chart_png({'data': chart_data, 'cycle': cycle, 'unit': unit, 'kind': 'original'})
                st.image(image, use_container_width=True)
                st.download_button('그래프 PNG 다운로드', image, file_name=f'ecos_chart_{i}.png',
                                   mime='image/png', key=f'png_{i}')
        visible = df[['TIME', *names, '수치', *(['UNIT_NAME'] if 'UNIT_NAME' in df else [])]].rename(
            columns={'TIME': '시점', 'UNIT_NAME': '단위', **{k: f'항목 {n+1}' for n, k in enumerate(names)}})
        st.dataframe(visible, use_container_width=True, hide_index=True)
        st.download_button('CSV 다운로드', visible.to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'ecos_{i}.csv', mime='text/csv', key=f'csv_{i}')
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
