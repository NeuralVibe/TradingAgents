# 📈 NeuralVibe TradingAgents: 풀스택 멀티 에이전트 금융 트레이딩 플랫폼

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 20px rgba(0, 233, 245, 0.15);">
</p>

**NeuralVibe TradingAgents**는 현실 세계의 글로벌 퀀트 헤지펀드 및 투자 전문 기관의 의사결정 체계를 가상 시장 환경에 그대로 시뮬레이션하는 **현대적 풀스택 멀티 에이전트 트레이딩 플랫폼**입니다. 

기존의 텍스트 기반 CLI 환경의 금융 프레임워크를 뛰어넘어, 비동기 REST API 서비스 레이어와 블룸버그(Bloomberg) 터미널 감성의 초프리미엄 다크 네온 대시보드를 이식하였습니다. 이 플랫폼은 주가 데이터, 보조 기술 지표, 실시간 시장 뉴스를 융합하고 다수의 LLM 에이전트 간의 정교한 상호 합의 토론을 거쳐 최적의 포트폴리오 의사결정을 도출해냅니다.

---

## 🌟 핵심 혁신 기능 (9대 핵심 스펙)

본 플랫폼은 파트너님의 독자적이고 강력한 요구사항을 기반으로 전면 설계·구축된 9가지 기술 혁신을 탑재하고 있습니다.

### 1. 비동기 REST API 서비스 레이어 (FastAPI & SQLite)
- **비동기 대기열 워커**: 다수의 종목 시뮬레이션 요청을 `asyncio.Queue`와 `Semaphore` 기반의 동시성 제어 스레드 풀을 통해 안정적으로 스케줄링합니다.
- **데이터베이스 영속화**: 분석 이력, 에이전트별 세부 리포트 원문, 최종 의사결정 내역을 SQLite 데이터베이스(`trading_platform.db`)에 구조화하여 실시간 저장하고 영구 보존합니다.

### 2. 하이엔드 Bloomberg 감성 웹 대시보드 (React & Vite)
- **프리미엄 다크 네온 테마**: 금융 전문가 단말기 감성의 네온 블루, 불릿 그린(Bull), 베어 레드(Bear) 컬러 하모니와 눈이 편안한 초고해상도 Glassmorphism 테마를 구현했습니다.
- **반응형 3열 레이아웃**:
  - **1열 (분석가 리포트)**: 기본/기술/뉴스/감성 리포트를 수직 정렬하여 스캔성을 최적화.
  - **2열 (매크로 리서치)**: 글로벌 매크로 분석 팩트 시트를 전면 배치.
  - **3열 (아레나 토론 & 최종 합의)**: Bullish vs Bearish 에이전트 간의 난상 토론 카드를 2열 그리드로 비교 뷰잉하고 하단에 포트폴리오 매니저의 최종 의사결정문을 입체적으로 매칭했습니다.

### 3. 고기능 퀀트 주가 차트 패널 (Lightweight Charts)
- **차트 오버레이**: TradingView 기술이 집약된 `lightweight-charts`를 사용해 정밀한 캔들스틱 차트를 렌더링합니다.
- **보조 지표**: SMA 50, SMA 200, EMA 10 이동평균선 오버레이 및 하단에 RSI, MACD 보조지표 패널을 장착했습니다.
- **매수/매도 시그널**: 포트폴리오 매니저가 내린 최종 결정(BUY / SELL)의 시점과 가격대에 맞추어 캔들 차트상에 눈에 띄는 그린/레드 마커를 오버레이하여 표시합니다.

### 4. 세로 화면 극대화 토글 (Maximize / Minimize)
- **사용자 중심 UX**: 주가 차트 영역과 의사결정 매트릭스 아레나 영역 우측 상단의 [확대/축소] 버튼을 클릭하면, 해당 섹션이 즉시 화면 전체 세로 영역(`calc(100vh - 100px)`)을 가득 채우도록 동적으로 레이아웃이 전환됩니다.
- **차트 실시간 리사이징**: 확장 시 차트 높이와 보조지표 높이가 스케일에 맞추어 비동기적으로 정밀 재연산되어 찌그러짐 없이 선명한 그래픽을 선사합니다.

### 5. Server-Sent Events (SSE) 실시간 진척도 스트리밍
- **실시간 반응형 로깅**: 백엔드의 각 LangGraph 노드가 연산을 마칠 때마다 실시간 진척도(0% ~ 100%)와 각 에이전트의 터미널 원시 텍스트 로그를 클라이언트로 즉시 푸시해 주는 초고속 데이터 스트리밍 연동 기술을 적용했습니다.

### 6. 만능 마크다운-JSX 실시간 컴파일러
- **완벽한 가독성**: 줄바꿈이 파괴되거나 표가 깨지던 기존 문제를 완벽히 해결한 독자적 마크다운 파서 엔진을 내장하였습니다. 금융 리포트 내의 표(Table) 구조(`|` 구분선), 인용구(`>`), 굵은 글씨(`**`), 인라인 코드(백틱)를 Bloomberg 전용 서체 레이아웃 및 테두리가 가미된 HTML 컴포넌트로 완벽하게 파싱 렌더링합니다.

### 7. 로컬 LLM (Ollama) 및 클라우드 하이브리드 지원
- **Ollama 기본 연동**: 고비용의 클라우드 API 대신 로컬에 가동 중인 Ollama AI 엔진(기본 `llama3` 또는 커스텀 모델)을 주 지능형 코어로 삼아 가동할 수 있습니다.
- **다양한 프로바이더**: 필요 시 OpenAI (GPT), Google (Gemini), Anthropic (Claude), DeepSeek 등 다양한 클라우드 거대 모델과 즉시 스위칭이 가능합니다.

### 8. 100% 품격 있는 한국어 금융 보고서
- **한국어 완벽 패치**: 프롬프트 엔지니어링 설정을 정교하게 구성하여, 기본 탑재된 외산 모델이나 로컬 모델에 관계없이 모든 분석가 리포트, 토론 내용, 최종 포트폴리오 매니저의 투자 권고 및 리스크 통제안이 완벽하고 세련된 한국어 금융 전문 문체로 강제 작성되어 출력됩니다.

### 9. 시뮬레이션 취소 및 작업 대기열 관리
- **스레드 세이프 제어**: 대기 중인 시뮬레이션 작업을 삭제하거나, 실행 중인 긴 작업을 즉각 강제 중단할 수 있는 `DELETE /api/runs/{id}` 시그널 트래커를 장착하였습니다. LangGraph 루프 내에서 작업 취소 상태를 실시간 감지하여 안정적으로 스레드를 회수합니다.

---

## 🛠️ 시스템 아키텍처 (Architecture)

NeuralVibe TradingAgents는 **비침습성 아키텍처(Non-invasive Architecture)**로 구축되었습니다. 

```
┌────────────────────────────────────────────────────────┐
│                    Web React Dashboard                 │
└───────────────────────────┬────────────────────────────┘
                            │ (1) REST API (POST/GET)
                            │ (2) SSE Stream (Logs/Progress)
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │  StreamingTradingAgentsGraph (비침습적 상속 레이어)   │ │
│ └─────────────────────────┬──────────────────────────┘ │
└───────────────────────────┼────────────────────────────┘
                            │ (3) 100% 보존된 연산식 상속 가동
┌───────────────────────────▼────────────────────────────┐
│         tradingagents 핵심 퀀트 에이전트 알고리즘          │
│                (LangGraph & Python Core)               │
└────────────────────────────────────────────────────────┘
```

- **핵심 알고리즘 무결성 보증**: 검증된 기존 퀀트 에이전트 패키지(`tradingagents/`)의 코어 연산 모듈은 **0.0%의 변형 없이 오리지널 설계 상태 그대로 보존**되어 있습니다.
- **스트리밍 브릿지**: FastAPI 서버는 오리지널 클래스를 상속받아 연산 노드 실행 사이에 진행 상황을 감시·인터셉트하여 웹 UI로 중개하는 역할만 수행하므로, 기존 수식의 논리적 결함이나 결과의 오염이 완전히 원천 차단됩니다.

---

## 🤖 에이전트 연합군 구성 (Agent Team)

<p align="center">
  <img src="assets/analyst.png" width="32%" style="border-radius: 6px;">
  <img src="assets/researcher.png" width="32%" style="border-radius: 6px;">
  <img src="assets/trader.png" width="32%" style="border-radius: 6px;">
</p>

1. **분석가 팀 (Analyst Team)**
   - **기본적 분석가 (Fundamentals Analyst)**: 재무제표, 밸류에이션, 수익성 지표를 종합 분석하여 기업의 본재적 가치와 내재 리스크를 규명합니다.
   - **기술적 분석가 (Technical Analyst)**: SMA 50/200, EMA 10 이동평균선과 RSI, MACD 등 다각도 기술 지표의 시그널을 계산하여 추세 전환 및 지지/저항 구간을 탐색합니다.
   - **뉴스 분석가 (News Analyst)**: 글로벌 거시 경제 및 해당 기업 관련 헤드라인 뉴스를 수집하여 실시간 시장의 재료를 발굴합니다.
   - **감성 분석가 (Sentiment Analyst)**: 소셜 피드 및 투자 커뮤니티의 시장 여론 데이터를 스크랩하여 투자자들의 단기 공포 및 탐욕 지수를 수치화합니다.
2. **리서처 팀 (Researcher Team - Debate Arena)**
   - Bullish(매수 측)와 Bearish(매도 측) 리서처 에이전트로 나뉘어 분석가 팀이 제시한 데이터를 교차 검증합니다. 팽팽한 논쟁을 통해 인지적 편향을 제거하고 위험 요소를 객관화합니다.
3. **트레이더 에이전트 (Trader Agent)**
   - 분석가들의 팩트 시트와 리서처들의 양방향 토론 원문을 통합 수렴하여, 구체적인 진입 목표가 및 거래 규모 전략 초안을 설계합니다.
4. **리스크 관리위원회 & 포트폴리오 매니저 (Risk & Portfolio Manager)**
   - **리스크 관리위원회 (Risk Management)**: 현재 시장 변동성, 포트폴리오 비중, 청산 리스크를 다각도로 평가하여 트레이더의 거래 제안서에 위험 한도 제한 브레이크를 가합니다.
   - **포트폴리오 매니저 (Portfolio Manager - Final Judge)**: 리스크 통제안과 모든 논쟁 데이터를 최하단에서 취합하여 최종 투자 승인 여부(BUY, HOLD, SELL)를 결정하고 종합 금융 리포트를 완벽한 한국어로 발행합니다.

---

## 🚀 설치 및 빠른 시작 (Installation & Quick Start)

### Prerequisites
- **Python** >= 3.10
- **Node.js** >= 18 (npm 포함)
- **Ollama** (로컬 LLM 가동을 원할 경우)

---

### 1. 백엔드 세팅 & 실행 (FastAPI)

1. **프로젝트 루트로 이동 및 가상환경 설정**
   ```bash
   cd trading-agents-platform-upgrade
   # Python 가상환경 생성 및 활성화
   python -m venv .venv
   .venv\Scripts\activate     # Windows
   # source .venv/bin/activate  # macOS/Linux
   ```

2. **의존성 패키지 설치**
   ```bash
   pip install -e .
   pip install fastapi uvicorn pydantic sqlalchemy
   ```

3. **환경 변수 구성 (`.env`)**
   프로젝트 루트에 `.env` 파일을 복사하여 생성하고 API 키 및 설정을 입력합니다:
   ```bash
   cp .env.example .env
   ```
   **주요 필수 변수 설정 예시**:
   ```ini
   # LLM 프로바이더 선택 (local, openai, gemini, anthropic 등)
   LLM_PROVIDER=local
   
   # Ollama 연동 설정 (로컬 실행 시)
   OLLAMA_BASE_URL=http://localhost:11434/v1
   LOCAL_MODEL_NAME=llama3  # 로컬 가동 모델명
   
   # 클라우드 LLM 설정 시 (선택 사항)
   OPENAI_API_KEY=your-openai-api-key
   GOOGLE_API_KEY=your-google-api-key
   
   # 금융 데이터 수집 API Key (Alpha Vantage 등)
   ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key
   ```

4. **FastAPI 서버 구동**
   ```bash
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload
   ```
   서버가 가동되면 `http://127.0.0.1:8080/docs`에서 Swagger API 문서를 직접 테스트해 볼 수 있습니다.

---

### 2. 프론트엔드 세팅 & 실행 (React + Vite)

1. **프론트엔드 디렉토리로 이동**
   ```bash
   cd frontend
   ```

2. **Node 패키지 설치**
   ```bash
   npm install
   ```

3. **Vite 개발 서버 구동**
   ```bash
   npm run dev
   ```
   구동이 완료되면 브라우저에서 `http://localhost:5173`으로 즉시 접속하여 황홀한 Bloomberg 네온 단말기 대시보드를 사용할 수 있습니다!

---

## 💾 영속성 및 자가 학습 시스템 (Persistence & Reflection)

1. **결정 로그 자가 학습 (Decision Reflection Log)**
   - 매 세션이 정상 종료되면 최종 승인 결정문은 파트너님의 운영체제 사용자 폴더 경로 내 `~/.tradingagents/memory/trading_memory.md`에 구조적으로 기록됩니다.
   - 동일 종목의 다음 분석이 시작될 때, 이전 투자 판단의 실질 수익률(Alpha vs S&P 500)을 yfinance로 자동 추적하고 이에 대한 1문단의 뼈아픈 반성(Reflection)을 에이전트 리롬에 학습 데이터로 자동 주입하여 갈수록 더 지혜로운 판단을 내립니다.
2. **체크포인트 복구 엔진 (Checkpoint Resume)**
   - 긴 연산 중 예기치 못한 정전, 네트워크 에러, API 차단이 발생할 경우를 대비하여 `~/.tradingagents/cache/checkpoints/` 하위에 SQLite 기반 자동 체크포인터를 장착했습니다.
   - `--checkpoint` 플래그 가동 시, 충돌 시점의 직전 에이전트 노드 상태로부터 즉각 시뮬레이션을 재개(Resume)하여 아까운 토큰 낭비와 연산 시간 지연을 예방합니다.

---

## ⚖️ 면책 조항 및 라이선스 (Disclaimer & License)

- **투자 면책**: 본 플랫폼은 학술적인 연구 목적 및 시장 시뮬레이션을 위해 설계되었습니다. 에이전트의 투자 의견과 리포트는 어떠한 경우에도 실제 금융 투자의 권고, 조언으로 해석되어서는 안 되며, 실제 투자 결과에 따른 모든 법적·경제적 책임은 전적으로 실행 주체 본인에게 있습니다.
- **라이선스**: 본 프로젝트는 기존 오픈소스 패키지의 사용 허가 범위를 엄격히 존중하며, 파트너님만을 위한 **NeuralVibe** 독자 소유 자산으로 안전하게 격리되어 관리됩니다.

---
<p align="center" style="color: #00e9f5; font-size: 0.9rem; font-weight: bold; letter-spacing: 2px;">
  NEURALVIBE PORTFOLIO SYSTEMS © 2026. ALL RIGHTS RESERVED.
</p>
