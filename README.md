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
- 전월비·전년동월비는 표시 계층인 `ecos_ai/presentation.py`에서 계산합니다. 실제 데이터가 누락되거나 월별 계열이 아니라면 정확한 계산이 가능한지 안내합니다.
- 그래프는 서로 다른 항목코드로 조회된 다중 시계열도 함께 표시할 수 있습니다.
- API 호출 수·응답 건수 제한(`ECOS_MAX_ROWS`, 최대 10000)이 적용됩니다. `truncated`이면 전체 자료라고 답해서는 안 됩니다.
- 외부로 공개하려면 접근통제, 비용 상한, IP 및 rate limit, 요청 감사 로그, TLS, 비밀키 관리가 추가로 필요합니다.
- `OPENAI_API_KEY`는 통계 데이터 소스가 아니지만, 사용자의 질문과 도구 결과는 OpenAI API로 전송됩니다. 조직 데이터 정책에 따라 승인 후 사용하세요.
- ECOS의 일부 통계는 타 기관 작성 통계를 재수록한 것이며, 이 프로그램은 **ECOS 경유 데이터로 한정**한다는 의미입니다.

## 공식 참고 자료

- https://ecos.bok.or.kr/api/
- https://py.sdk.modelcontextprotocol.io/
- https://developers.openai.com/api/docs/guides/function-calling


## 공유 Streamlit 사이트에서 API 키 직접 입력

Streamlit Community Cloud에 배포한 뒤, 웹 앱 왼쪽 사이드바의 **한국은행 ECOS API 키**와 **OpenAI API 키** 입력창에 각 이용자가 자신의 키를 입력하면 됩니다. 두 키가 모두 입력되어야 질문창이 활성화됩니다.

- `.env`는 로컬 테스트용 예시이며, 이 버전의 웹 화면은 사용자가 사이드바에 입력한 키를 우선 사용합니다. 키를 입력하지 않으면 질문할 수 없습니다.
- 키는 `type="password"`로 가려져 표시되고, 별도 파일이나 대화 내역에 저장하지 않습니다. 단, Streamlit 세션 메모리에는 세션 동안 유지됩니다.
- ECOS 키는 MCP 서버를 실행하는 해당 요청의 자식 프로세스 환경변수에만 전달하고, OpenAI 키는 해당 요청의 OpenAI 클라이언트에만 전달합니다. 서버 전역 환경변수를 변경하지 않으므로 다른 사용자의 키와 섞이지 않도록 설계했습니다.
- API 키의 유효성은 실제 호출 시 확인되며, 사이트 운영자 또는 인프라의 로그 및 런타임 접근 권한은 별도로 통제해야 합니다.
- 앱의 GitHub 저장소에는 `.env`를 올리지 마세요.

## 2차 UI 개편 (2026-10)

### 요청 사항 반영

1. 웹 페이지와 브라우저 탭의 제목을 **경제통계 AI 검색**으로 변경했습니다.
2. 사이드바 질문 예시를 아래 세 문장으로 교체했습니다.
   - 국고채(3년) 금리 추이를 그려줘
   - 2026년 소비자물가지수 추이와 전년동월대비 상승률 그래프를 그려줘.
   - 최근 3년간 전국 및 서울 아파트 매매가격지수의 전월대비 상승률 그래프를 그려줘
3. 숫자 데이터가 정상적으로 검색되면 **요약 → 그래프 → 통계표**가 모두 펼쳐진 상태로 표시됩니다. **조회 기준 · 출처**와 **MCP 호출 기록**은 기본적으로 접혀 있습니다.
4. 질문 처리 중에는 `st.status`로 실제 실행 단계에 맞춘 문구가 표시됩니다. 예: 통계표 검색 → 항목·주기 확인 → ECOS 데이터 수집 → 답변 정리. 작업이 완료되면 진행 표시가 자동으로 접힙니다.

### 월별 증감률과 다중 계열

신규 파일 `ecos_ai/presentation.py`가 MCP로 가져온 ECOS 시계열만으로 표·그래프·숫자 요약을 구성합니다.

- 전국과 서울 등 항목 코드가 다른 계열을 **한 그래프에서 여러 선으로 비교**할 수 있습니다.
- 질문에 **전년동월대비 / 전월대비**가 포함되면, 월별(M) **원지수**에서 전년 동일월 / 전월 값을 기준으로 `(현재값 / 비교값 - 1) * 100`을 계산하고 별도 그래프와 표를 표시합니다.
- `2026년`처럼 표시 기간이 지정되어 있어도, 증가율 계산을 위해 조회한 이전 연도의 원자료는 계산에만 쓰고 그래프 및 표는 요청한 기간으로 제한합니다.
- 해당 증감률 계열을 **이미 ECOS에서 직접 조회한 경우**, 동일 계열의 증가율을 한 번 더 계산하지 않도록 경고를 표시합니다.
- 비교에 필요한 과거 월의 값이 누락되었다면 수치를 만들어내지 않고 계산 부족 안내를 표시합니다. 월별 이외의 계열에서는 월별 증가율을 억지로 계산하지 않습니다.
- 유효한 원자료가 조회되지 않았으면 표와 그래프를 가짜로 생성하지 않습니다.

### Streamlit Community Cloud 업데이트

이 버전을 배포하려면 기존 리포지토리에서 다음 파일을 갱신해야 합니다.

- `app.py` (새 화면과 진행 상태)
- `ecos_ai/agent.py` (진행 이벤트와 새 답변 규칙)
- `ecos_ai/presentation.py` (**새 파일**, 시계열 표시·증감률 계산)
- `tests/test_presentation.py` (선택 사항, 신규 모의 테스트)

나머지 파일은 기존의 ECOS 키 입력 버전과 호환됩니다. 모든 파일을 전체 ZIP으로 교체해도 됩니다. GitHub에 업로드한 뒤 Streamlit Community Cloud가 재배포하면 웹 화면에 반영됩니다. `.env` 및 API 키를 Git에 올리지 마세요.

### 새 테스트

```bash
python -m pytest -q
```

API 키 없이 실행되는 모의 테스트로 기간 필터링, 두 지역의 다중 그래프, 전년동월비 계산, 결측월 처리, 표·그래프 자동 표시 여부를 확인합니다.
