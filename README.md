# 경제통계 AI 검색 v4 — Streamlit + MCP + 한국은행 ECOS

자연어로 경제통계를 질문하면 한국은행 **ECOS Open API에서만 통계 수치를 조회**하여 정적 그래프, 정적 통계표, 수치 중심 요약을 출력하는 단일 질의형 웹 앱입니다. LLM은 자연어 해석 및 MCP 도구 호출에 사용되며, LLM 제공자는 경제통계 데이터의 출처가 아닙니다.

## v4 개선 사항

- **KeyError: '시점' 수정**: 표 생성에 `reset_index().rename(columns={'timestamp':'시점'})`를 사용하지 않습니다. 인덱스 이름이 `TIME`, `index`, `timestamp`, 공란이어도 `시점` 열을 직접 만듭니다.
- **정적 그래프**: Streamlit 기본 대화형 그래프 대신 Matplotlib의 고해상도 PNG. 데이터 분포에 따른 y축 상·하한 여백, 날짜 범위 자동 지정, 여러 지역 범례, 시점 축 레이블, 결측값 처리.
- **정적 표**: 검색·정렬·편집이 없는 고정 레이아웃 표. 최근 60개 시점 표시, 전체 데이터는 CSV 다운로드.
- **답변 순서**: 그래프 → 통계표 → 통계 수치 요약 → 조회 기준(기본 접기).
- **통계 요약만 출력**: ECOS에서 조회한 실제 관측치를 이용한 시작·마지막 값과 계산된 증가율만 요약. LLM 일반 해설은 통계 결과가 정상적으로 나온 경우 표시하지 않음.
- **한 화면 한 턴**: 최근 질의 하나와 결과만 유지. 다음 질문에는 이전 대화 내역을 LLM에 전달하지 않고 결과도 교체.
- **디자인 개선**: 그라데이션 헤더, 카드형 UI, 한국어 글꼴, 간결한 색상과 간격, 단계별 진행 메시지.

## 설치

Python 3.11 이상 권장. 운영 환경은 배포 전에 특정 Python 버전으로 고정하는 것이 좋습니다.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud에서는 `requirements.txt` 및 `packages.txt`를 자동 인식합니다. `packages.txt`의 `fonts-nanum`은 Matplotlib의 한글 범례 렌더링용 시스템 패키지입니다. **글꼴 파일은 프로젝트에 포함하지 않았습니다.**

앱 사이드바에 아래 키를 입력합니다.

1. 한국은행 ECOS Open API 키
2. OpenAI API 키

로컬 테스트에 사용할 `.env.example`도 포함되어 있습니다. `.env`를 GitHub에 커밋하지 마세요. OpenAI API 사용료는 ChatGPT 구독과 별개입니다.

## Streamlit Community Cloud 기존 앱 업데이트

기존 v3 GitHub 저장소에 아래를 덮어씁니다.

```text
app.py                      교체
requirements.txt            교체
ecos_ai/presentation.py     교체
ecos_ai/rendering.py        새로 추가
.streamlit/config.toml      새로 추가
packages.txt                새로 추가
```

기존 MCP 통신은 유지하며, 이 배포 ZIP에는 `ecos_ai/agent.py`, `ecos_ai/server.py`, `ecos_ai/ecos.py` 등 실행에 필요한 전체 파일도 포함되어 있습니다. 전체 ZIP을 저장소 루트에 반영하는 방법을 권장합니다.

## 동작 방식

1. 사용자가 통계 질문을 한 번 입력합니다.
2. LLM이 `find_statistics`, `get_statistic_items`로 통계표와 항목을 찾습니다.
3. MCP의 `get_statistic_data`가 ECOS API에서 실제 수치를 수집합니다.
4. `presentation.py`가 계열을 그룹화하고 요청한 전월비 / 전년동월비를 Python으로 계산합니다.
5. `rendering.py`가 Matplotlib 정적 PNG 그래프와 HTML 표를 생성합니다.
6. 결과 맨 아래에 **ECOS 통계 수치에 한정한 요약**과 접힌 조회 기준/호출 로그를 표시합니다.

**주의:** 임베딩 검색 고도화 및 공식 증감률 계열 자동 선택은 아직 구현 대상입니다. ECOS 응답의 통계표·항목 선택 결과를 실제 키로 확인하세요. 실제 API 키가 없어 모의 데이터 테스트만 수행했으며, 서비스 배포 이후 실제 질문으로 연결 검증이 필요합니다.

## 테스트

```bash
python -m pytest -q
```

ECOS 인증키 없이 시점 열 이름 회귀, 빈 데이터, 단일·다중 계열 그래프, 월별 상승률 및 MCP 응답 형식 테스트를 실행합니다.

## 프로젝트 파일

```text
ecos-stat-ai-v4/
├── app.py
├── requirements.txt
├── packages.txt
├── .streamlit/config.toml
├── .env.example
├── .gitignore
├── ecos_ai/
│   ├── __init__.py
│   ├── ecos.py
│   ├── server.py
│   ├── agent.py
│   ├── mcp_result.py
│   ├── presentation.py
│   └── rendering.py
└── tests/
    ├── test_ecos.py
    ├── test_mcp_result.py
    ├── test_presentation.py
    └── test_rendering.py
```

## 보안 및 데이터 정확도

- 외부 **통계 데이터** 조회는 ECOS API를 통해서만 수행합니다. 질문·조회 수치는 OpenAI API에 전달될 수 있습니다.
- 웹 앱은 API 키를 별도 파일이나 CSV 다운로드에 저장하지 않습니다. 해당 세션의 위젯 상태와 MCP 서브프로세스 환경에서는 사용합니다.
- 공유 사이트 운영자·클라우드 사업자를 신뢰할 수 있는 경우에만 비밀키를 입력하세요.
- 자료가 없거나 ECOS 조회에 실패하면 가짜 그래프나 수치를 만들지 않습니다. 데이터 진단과 MCP 호출 기록은 기본 접힌 상태로 제공됩니다.
- Matplotlib은 단순 시계열 축 조정에 최적화했으며, 서로 다른 단위를 가진 계열은 별도의 그래프로 분리됩니다.

## v4.1 · MCP 호출이 모두 오류로 표시되는 경우

v3와 v4의 MCP 서버/에이전트 연결 코드는 동일하지만, 기존 버전에서는 실패 사유가 보이지 않았습니다.
이 버전은 **원래 문제가 발생한 도구, ECOS API의 오류 코드, 인증/HTTP/시간 초과 여부**를 구분해서 표시합니다.

1. Streamlit 사이드바에서 **ECOS API 키**를 입력합니다.
2. **🔎 MCP + ECOS 연결 진단** 버튼을 누릅니다. OpenAI API 키는 이 검사에 필요하지 않습니다.
3. MCP 서버 연결이 실패하면 배포 로그와 `mcp` 패키지 설치 상태를 확인합니다.
4. MCP 서버 연결은 성공하고 ECOS API 테스트가 실패하면 인증키, ECOS 이용 한도, ECOS 서버 연결 상태를 확인합니다.
5. 연결 검사가 성공하는데 질문 도구 호출만 오류라면, **MCP 호출 기록**에서 실패한 도구명·오류 유형·오류 내용을 확인합니다.

인증키와 원시 URL은 진단 기록에 저장/출력하지 않습니다. 화면에 표시된 오류만 공유하고 **API 키는 공유하지 마세요**.

> 외부 ECOS API 실호출은 사용자의 개인 API 키가 없어 자동 검증되지 않았습니다. 이 버튼은 실제 배포 환경에서 원인 식별용입니다.
