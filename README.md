# TradingAgents: 멀티 에이전트 LLM 기반 풀스택 퀀트 트레이딩 플랫폼 (v0.2.5 Enterprise)

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
</p>

**TradingAgents**는 금융 전문가 에이전트 군집(Swarm Intelligence)의 대화와 합의 알고리즘을 활용하여 고도화된 투자 의사결정을 도출하고, 이를 한눈에 제어할 수 있는 **현대적인 풀스택 웹 대시보드 플랫폼**입니다. 

기존의 파이썬 CLI 엔진을 웹 UI 및 비동기 서비스 레이어로 전격 전환하여, 주가 차트, 실시간 로그 스트리밍, 3열 토론 아레나(Debate Arena), PM 최종 승인 주문서를 결합한 명품 트레이딩 관제 시스템을 선사합니다.

---

## 🚀 주요 특징 (Key Features)

### 1. 풀스택 다중 사용자 대시보드 (React / Vite)
* **Bloomberg 터미널 감성의 하이엔드 UI/UX**: 딥 다크 테마와 세련된 네온 블루, 불릿 그린, 베어 레드 악센트 색상이 어우러진 고급 디자인 시스템.
* **세로 전체화면 확장 기능 (Maximize/Minimize)**: 주가 차트 패널과 리포트 아레나 패널 우측 상단에 실시간 스케일 최적화 확장 버튼 장착.
* **완벽한 한국어 금융 리포트 출력**: 모든 리포트 내용, 토론 히스토리, 최종 승인 주문서가 매끄럽고 격조 높은 한국어로 자동 추론 및 시각화.

### 2. 고성능 비동기 백엔드 레이어 (FastAPI)
* **LangGraph 실시간 스트리밍 인터셉터**: 비침습 상속 구조(`StreamingTradingAgentsGraph`)를 활용하여 핵심 연산 프롬프트를 100% 원본 유지한 채, 각 추론 단계 완료 시점마다 진척률과 실시간 콘솔 로그를 추출.
* **Server-Sent Events (SSE) 비동기 통신**: 클라이언트에 실시간 이벤트를 안전하게 푸시하고, 동시성 작업 관리를 위한 대기열 큐 워커 및 세마포어 적용.
* **SQLite 영속성 데이터 저장소**: 모든 시뮬레이션 요청, 실시간 로그, 퀀트 결과 데이터가 `trading_platform.db`에 정밀 구조화되어 기록.

### 3. 인터랙티브 퀀트 차트뷰 & 기술 오버레이
* **Lightweight Charts 종목 주가 차트**: 봉 캔들스틱 및 이동평균선(SMA 50, SMA 200, EMA 10), 거래 시점 마커 시각화.
* **퀀트 오버레이 점선 가격 장선**: 포트폴리오 매니저(PM)의 매매 보고서 텍스트를 실시간 파싱하여 차트 우측에 익절 목표가(**Take Profit**), 손절 라인(**Stop Loss**), 진입 타깃가(**Entry**)를 점선 가선으로 자동 투영.

### 4. 3열 토론 대립 아레나 (Debate Arena)
* **에이전트 논리 대립 분리 시각화**: 긍정 세력과 부정 세력의 토론 로그를 가로 2분할로 병렬 배치하여 핵심 쟁점을 직관적으로 비교.
* **종합 맥락 및 중재 배치**: 거시 뉴스를 수집하는 리서치 매니저 리포트 원문을 중앙 열에 팩트 시트로 배치하고, 하단에 심판 합의문 및 리스크 통제안을 위치시켜 완성도 높은 의사결정 워크플로우 표현.

### 5. 만능 마크다운 컴파일러 탑재
* 금융 리포트 내의 표(`|`), 인용구(`>`), 구분선(`---`), 리스트(`- ` / `1. `), 백틱 인라인 코드(`` ` ``), 중첩 볼드/이탤릭 서식이 개행 뭉개짐이나 기호 노출 없이 브라우저 상에서 완벽한 명품 서체 레이아웃으로 변환 렌더링.

---

## 📊 플랫폼 시스템 아키텍처 (System Architecture)

본 플랫폼은 핵심 과학적 트레이딩 모델의 무결성을 100% 지키기 위해 비침습 격리 아키텍처로 구현되었습니다.

```mermaid
graph TD
    A[React Dashboard Client (Port: 5173)] <-->|REST API / GET, POST, DELETE| B[FastAPI Web Server (Port: 8080)]
    B <-->|ORM / SQL| C[SQLite Database (trading_platform.db)]
    B -->|Server-Sent Events / Stream| A
    B -->|Thread Pool / Async Queue| D[Streaming LangGraph Agent Wrapper]
    D <-->|Original core package| E[TradingAgents Core Engine (tradingagents/)]
    D <-->|API / Local Client| F[Local LLM Server / Ollama]
```

---

## 🛠️ 설치 및 가동 방법 (Installation & Running)

### 1. 사전 준비 (Requirements)
* Python 3.10 ~ 3.13 버전
* Node.js 18 버전 이상
* 로컬 Ollama 또는 외부 LLM API 키 (OpenAI, Anthropic 등)

### 2. 가상환경 및 파이썬 패키지 설치
프로젝트 루트 디렉토리에서 패키지 의존성을 구성합니다.
```bash
# uv 패키지 매니저 활용 권장
uv sync
```

### 3. 환경 변수 파일 구성 (`.env`)
루트 폴더의 `.env.example` 파일을 복사하여 `.env` 파일을 생성하고 필요한 API Key 및 로컬 LLM 설정을 적용합니다.
```bash
cp .env.example .env
```
```ini
# 로컬 Ollama 모델 가동 설정 예시
LLM_PROVIDER=local
LOCAL_LLM_URL=http://localhost:11434/v1
LOCAL_LLM_MODEL=qwen2.5-coder:7b     # 또는 gemma2:9b 등 보유 모델 기재
```

### 4. FastAPI 백엔드 서버 기동
```bash
# 포트 8080에서 가동
uv run uvicorn backend.app.main:app --port 8080 --host 0.0.0.0 --reload
```

### 5. 프론트엔드 React 대시보드 기동
```bash
cd frontend
# 의존성 모듈 설치 (최초 1회)
npm install
# 개발 서버 기동 (포트 5173)
npm run dev -- --port 5173 --host 0.0.0.0
```
기동 완료 후 브라우저에서 `http://localhost:5173`으로 접속하여 인터랙티브 대시보드를 사용할 수 있습니다.

---

## ⚔️ 에이전트 군집 구성 (Agent Swarm Roles)

대시보드 내부에서 협업 추론을 전개하는 금융 AI 에이전트 구성입니다:

<p align="center">
  <img src="assets/analyst.png" style="width: 48%; display: inline-block; margin-right: 2%; border-radius: 4px;">
  <img src="assets/researcher.png" style="width: 48%; display: inline-block; border-radius: 4px;">
</p>

* **Analyst Team (분석팀)**:
  * **시장 분석가 (Market Analyst)**: 주가 흐름 및 보조 기술적 지표(RSI, MACD) 연산 및 패턴 판별.
  * **재무 분석가 (Fundamentals Analyst)**: 기업의 재무제표 실적 및 기업 내재 가치 적합성 판별.
  * **감성 분석가 (Sentiment Analyst)**: 뉴스 미디어 헤드라인 및 투자자 커뮤니티 감성점수 계량화.
* **Researcher Team (토론 대립팀)**:
  * **강세론 변호인 (Bull Researcher)**: 공격적인 성장 지표와 매수 당위성 주장 전개.
  * **약세론 변호인 (Bear Researcher)**: 밸류에이션 과열 프리미엄 및 평균 회귀 위험 요인 발굴 경고.
* **Consensus & Decision Team (조율 및 의사결정)**:
  * **매크로 리서처 (Research Manager)**: 글로벌 거시 경제 및 종합 뉴스 리서치 및 1차 종합 조율.
  * **토론 심판 (Debate Judge)**: 대립하는 논거의 사실 관계를 최종 조율하여 합의문 작성.
  * **포트폴리오 매니저 (Portfolio Manager)**: 리스크 통제 필터와 에이전트 의견을 총망라하여 최종 승인 매매 주문서(Decision) 하달.

---

## 📁 디렉토리 구조 (Folder Structure)

```text
TradingAgents/
├── backend/                  # FastAPI 백엔드 레이어
│   └── app/
│       ├── routers/          # REST API 엔드포인트 라우터 (시뮬레이션, 차트)
│       ├── main.py           # uvicorn 실행 엔트리포인트
│       └── services.py       # LangGraph 상속 스트리밍 연동 핵심 서비스
├── frontend/                 # React/TypeScript 웹 프론트엔드
│   ├── src/
│   │   ├── components/       # UI 패널 컴포넌트 (차트, 아레나, 타임라인)
│   │   ├── App.tsx           # 전체화면 토글 및 상태 동기화 컨테이너
│   │   └── index.css         # 다크 네온 Bloomberg 테마 스타일 시트
│   └── vite.config.ts        # Vite 컴파일러 설정
├── tradingagents/            # [원본 보존] 퀀트 시뮬레이션 알고리즘 코어
├── run_trading.py            # CLI 실행 스크립트
├── trading_platform.db       # SQLite 데이터베이스
└── README.md                 # 프로젝트 마스터 설명서 (본 파일)
```

---

## 🔒 라이선스 및 면책 조항 (License & Disclaimer)

본 플랫폼은 연구 및 개인 자산 포트폴리오 모니터링 가상 시뮬레이션을 목적으로 개발되었습니다. 에이전트의 합의 추천 결과(BUY/SELL/HOLD) 및 제시된 퀀트 가격 장선은 **어떠한 형태의 투자 자문, 재정 보증 또는 매매 조언으로 해석될 수 없으며**, 투자 실행에 따른 결과와 책임은 전적으로 투자자 본인에게 있습니다.
