# ECOS 경제통계 AI (Streamlit + MCP)

사용자가 자연어로 경제통계를 질문하면 LLM이 **ECOS 전용 MCP 서버**의 도구를 선택하여 한국은행 경제통계시스템에서 데이터를 조회한 후 답변하는 프로젝트입니다. 통계 수치를 제공하는 외부 데이터 소스는 ECOS API 하나뿐입니다. LLM 공급자(OpenAI API)는 질문 해석과 답변 작성을 위해 사용되며, 질문과 ECOS 결과가 모델로 전달됩니다.

## 파일 구성

- `app.py` : Streamlit 채팅·표·그래프·CSV 내보내기
- `ecos_ai/ecos.py` : ECOS API 클라이언트, 오류 처리, 페이지네이션, 기간 검증
- `ecos_ai/server.py` : 실제 MCP Server / 4개 도구
- `ecos_ai/agent.py` : MCP Client + OpenAI Responses API 도구 호출 루프
- `.env.example` : 필요한 환경변수 예시
- `tests/test_ecos.py` : API 모의 테스트

## 설치 및 실행

Python 3.11 이상 권장.

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Windows에서는 `copy .env.example .env` 명령을 사용합니다. `.env`에 본인의 `ECOS_API_KEY`, `OPENAI_API_KEY`를 입력하세요. **ChatGPT 구독과 OpenAI API 과금은 별도입니다.** `OPENAI_MODEL`은 계정에서 사용 가능한 도구 호출 지원 모델로 바꿀 수 있습니다.

```bash
streamlit run app.py
```

브라우저에서 표시되는 Streamlit URL(기본 `http://localhost:8501`)로 접속합니다.

### MCP만 테스트하기

```bash
mcp dev ecos_ai/server.py
```

CLI 실행 환경에 따라 import 경로가 다를 수 있습니다. `python -m ecos_ai.server`를 프로젝트 루트에서 실행하면 stdio MCP Server가 시작되며, 정상 동작 시 별도 콘솔 출력이 없는 것이 정상입니다.

### 테스트

```bash
python -m pytest -q
```

위 테스트는 모의 API를 사용하므로 실제 ECOS 인증키가 필요하지 않습니다. 실제 ECOS / OpenAI 연결을 포함하는 통합 테스트는 본인 키로 따로 해야 합니다.

## 처리 예시

1. '최근 3년 한국은행 기준금리 추이' 질의
2. `find_statistics('기준금리')`
3. `get_statistic_items(실제 통계표 코드)`
4. `get_statistic_data(확인된 코드, 주기, 기간, 항목코드)`
5. ECOS로부터 받은 값·단위·기준시점과 출처를 이용해 설명

## 제약과 보완 사항

- 초기 버전은 통계표명을 전체 목록에서 부분 문자열 검색하므로, 검색 정확도가 제한됩니다. 검색 실패 시 더 짧은 핵심어로 검색하세요. `ECOS_MAX_ROWS` 이상의 목록은 누락될 수 있으며 `catalog_truncated`가 표시됩니다.
- ECOS API가 반환하는 통계항목코드는 서로 다른 항목 그룹으로 구분될 수 있습니다. 항목코드를 먼저 확인해야 합니다.
- 단순한 계산은 LLM이 수행할 수 있지만 **결정적·감사 가능한 전년동월비 계산**은 후속 버전에서 전용 계산 도구를 구현하는 것이 좋습니다.
- 그래프는 한 종류의 항목코드로 조회된 시계열에 대해서만 표시합니다.
- API 호출 수·응답 건수 제한(`ECOS_MAX_ROWS`, 최대 10000)이 적용됩니다. `truncated`이면 전체 자료라고 답해서는 안 됩니다.
- 외부로 공개하려면 접근통제, 비용 상한, IP 및 rate limit, 요청 감사 로그, TLS, 비밀키 관리가 추가로 필요합니다.
- `OPENAI_API_KEY`는 통계 데이터 소스가 아니지만, 사용자의 질문과 도구 결과는 OpenAI API로 전송됩니다. 조직 데이터 정책에 따라 승인 후 사용하세요.
- ECOS의 일부 통계는 타 기관 작성 통계를 재수록한 것이며, 이 프로그램은 **ECOS 경유 데이터로 한정**한다는 의미입니다.

## 공식 참고 자료

- https://ecos.bok.or.kr/api/
- https://py.sdk.modelcontextprotocol.io/
- https://developers.openai.com/api/docs/guides/function-calling
