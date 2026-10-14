"""검색 흐름과 답변 정보 분리를 외부 API 없이 검증합니다."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from ecos_ai.agent import split_answer, RULES


def test_answer_metadata():
    result = split_answer('{"answer":"기준금리 자료입니다.","query_info":"조회일: 2026-10-14"}')
    assert result['text'] == '기준금리 자료입니다.'
    assert '조회일' in result['query_info']
    assert '현재 날짜: 2026-10-14' in RULES.format(today='2026-10-14')


def test_single_search_and_examples(monkeypatch):
    calls = []
    async def mock_answer(question, history, model, **kwargs):
        calls.append((question, history, model))
        return {'text': f'결과: {question}', 'query_info': '조회일: 오늘', 'calls': []}
    monkeypatch.setattr('ecos_ai.agent.answer', mock_answer)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py').run()
    assert not app.exception
    assert app.title[0].value == '경제통계 AI 검색'
    assert len(app.selectbox[0].options) == 5
    app.text_input(key='ecos_key').set_value('test').run()
    app.text_input(key='openai_key').set_value('test').run()
    app.button(key='example_0').click().run()
    assert '기준금리' in app.text_area(key='question').value
    next(b for b in app.button if b.label == '검색하기').click().run()
    assert calls[-1][1] == []
    assert calls[-1][2] == 'gpt-5.5'
    app.selectbox(key='model').select('GPT-6 Luna').run()
    assert app.session_state.search_result is None
    app.button(key='example_1').click().run()
    next(b for b in app.button if b.label == '검색하기').click().run()
    assert calls[-1][2] == 'gpt-6-luna'
    assert '소비자물가' in app.session_state.search_result['question']
    assert not app.exception
    assert app.expander[0].label == '조회 정보 및 출처'
    assert not app.expander[0].proto.expanded
