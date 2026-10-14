"""한국은행 ECOS 전용 Streamlit 웹 화면."""
import asyncio
import json
from io import StringIO
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from ecos_ai.agent import answer

load_dotenv()
st.set_page_config(page_title='ECOS 경제통계 AI', page_icon='📊', layout='wide')
st.title('📊 ECOS 경제통계 AI')
st.caption('통계 데이터 출처: 한국은행 ECOS Open API만 사용 · LLM은 자연어 해석과 답변 생성에 사용')
with st.sidebar:
    st.subheader('질문 예시')
    st.markdown('• 최근 3년간 한국은행 기준금리 추이를 알려줘\n\n• 2025년 월별 소비자물가지수를 보여줘\n\n• 최신 경상수지 통계를 조회해줘')
    if st.button('대화 초기화'):
        st.session_state.messages = []
        st.rerun()
    st.info('정확한 통계표·항목을 찾지 못하면 수치를 추측하지 않도록 설계했습니다.')

if 'messages' not in st.session_state:
    st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])
        for i, c in enumerate(msg.get('calls', [])):
            if c.get('result') and c['result'].get('rows'):
                df = pd.DataFrame(c['result']['rows'])
                if 'TIME' in df.columns and 'DATA_VALUE' in df.columns:
                    df['numeric_value'] = pd.to_numeric(df['DATA_VALUE'], errors='coerce')
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    if df['numeric_value'].notna().any():
                        # 서로 다른 항목을 합쳐 그리는 잘못된 그래프를 피함
                        ids = [k for k in ['ITEM_CODE1','ITEM_CODE2','ITEM_CODE3','ITEM_CODE4'] if k in df.columns]
                        if len(df[ids].drop_duplicates()) == 1:
                            plot = df[['TIME', 'numeric_value']].dropna().drop_duplicates('TIME')
                            st.line_chart(plot.set_index('TIME').sort_index())
                    st.download_button('CSV 다운로드', df.to_csv(index=False).encode('utf-8-sig'),
                                       file_name=f'ecos_{i}.csv', mime='text/csv', key=f'{id(msg)}_{i}')
        if msg.get('calls'):
            with st.expander('MCP 호출 기록'):
                for c in msg['calls']:
                    st.write(f"{c['tool']} · {'성공' if c['success'] else '오류'}")
                    st.json(c['arguments'])

question = st.chat_input('경제통계에 대해 질문하세요')
if question:
    history = [{'role': m['role'], 'content': m['content']} for m in st.session_state.messages]
    st.session_state.messages.append({'role': 'user', 'content': question})
    with st.spinner('ECOS 통계를 검색하고 조회하는 중...'):
        try:
            response = asyncio.run(answer(question, history))
        except Exception as exc:
            response = {'text': f'요청을 처리하지 못했습니다: {type(exc).__name__}. .env 및 연결 설정을 확인해 주세요.', 'calls': []}
    st.session_state.messages.append({'role': 'assistant', 'content': response['text'], 'calls': response['calls']})
    st.rerun()
