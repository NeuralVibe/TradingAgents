# 🖥️ React 대시보드 컴포넌트 및 스트리밍 시각화 명세서 (Frontend Specification)

본 명세서는 TradingAgents 플랫폼의 웹 사용자 인터페이스를 담당하는 **React/Vite 프론트엔드(`frontend/src/`)**의 모듈형 컴포넌트 계층 설계 사양, **`EventSource` API**를 통하여 백엔드의 비동기 이벤트를 실시간 단방향 스트리밍 수신하는 **Server-Sent Events(SSE) 리시버** 구현부, 그리고 대량의 시계열 주가 캔들 및 가상 포트폴리오 수익률 곡선을 렉 없이 초당 60FPS 속도로 부드럽게 렌더링하는 **TradingView Lightweight Charts** 시각화 연동 사양을 상세히 기술합니다. 본 문서는 옵시디언(Obsidian) 전용 링크 및 이미지 임베딩 포맷에 최적화되어 있습니다.

---

## 🧱 1. React 컴포넌트 계층 아키텍처 (Component Hierarchy)

![[dashboard_grid_layout.png]]

프론트엔드 아키텍처는 코드의 모듈성 확보와 단일 책임 원칙(SRP)을 충족하기 위해, 단일 페이지로 구성하되 기능별로 물리 격리되어 계층적으로 조립되는 **조립형 컴포넌트 구조**를 취하고 있습니다. 

상위 컴포넌트인 `App.tsx`가 전체 애플리케이션의 공용 컨텍스트 상태 관리와 REST API 통신, 그리고 SSE 영속 연결 관리를 수행하며, 하부 컴포넌트로 데이터를 단방향(One-way Props-down) 바인딩하는 단방향 제어 흐름 구조를 가집니다.

### 🗺️ 1.1 컴포넌트 계층 구조 및 데이터 흐름도

```mermaid
graph TD
    %% 컴포넌트 트리
    App["상위 컴포넌트<br/>App.tsx<br/>- state: currentRun, selectedRun<br/>- SSE: EventSource listener"]
    
    App -->|"[1] runs list, selectedRunId"| AppCSS["스타일 레이어<br/>App.css / index.css"]
    App -->|"[2] triggerSubmit 호출"| RunForm["파라미터 입력 및 트리거 폼<br/>components/RunForm.tsx"]
    App -->|"[3] progress, current_step, logs"| Timeline["실시간 타임라인 로그<br/>components/Timeline.tsx"]
    App -->|"[4] ticker, market_data, indicators"| ChartPanel["금융 시각화 차트<br/>components/ChartPanel.tsx"]
    App -->|"[5] detailed_reports, agent_decisions"| ReportDetails["마크다운 종합 회의록<br/>components/ReportDetails.tsx"]

    %% 데이터 단방향 흐름 표시
    style App fill:#003366,stroke:#33ccff,stroke-width:2px,color:#fff
    style RunForm fill:#1a1a1a,stroke:#e6007e,stroke-width:2px,color:#fff
    style Timeline fill:#1a1a1a,stroke:#00ffcc,stroke-width:2px,color:#fff
    style ChartPanel fill:#1a1a1a,stroke:#ffcc00,stroke-width:2px,color:#fff
    style ReportDetails fill:#1a1a1a,stroke:#ab47bc,stroke-width:2px,color:#fff
```

### 📋 1.2 하부 컴포넌트별 렌더링 명세 및 역할

* **`RunForm.tsx` (분석 파라미터 조종간)**
  * **목적**: 대상 티커 코드, 분석 기준 날짜를 검증 및 수집하여 백엔드 포스트 호출(`POST /api/v1/runs`)을 수행하는 트리거 폼 컴포넌트입니다.
  * **소스 코드 위치**: `frontend/src/components/RunForm.tsx` $\rightarrow$ [[RunForm.tsx#L1]]
* **`Timeline.tsx` (실시간 진행 바)**
  * **목적**: 백엔드가 전송하는 SSE 실시간 이벤트를 수집하여, 현재 구동 중인 에이전트 노드 상태(시장분석, 토론중, 결제완료 등)와 실시간 타임라인 진행률 바를 렌더링합니다.
  * **소스 코드 위치**: `frontend/src/components/Timeline.tsx` $\rightarrow$ [[Timeline.tsx#L1]]
* **`ChartPanel.tsx` (금융 시각화 캔버스)**
  * **목적**: 백테스트 완료 데이터를 근거로, 주가 캔들스틱 시계열, 매매 체결 화살표 마커 및 목표 익절가/손절가/매수진입 가격 앵커 라인을 오버레이 렌더링합니다.
  * **소스 코드 위치**: `frontend/src/components/ChartPanel.tsx` $\rightarrow$ [[ChartPanel.tsx#L122]]
* **`ReportDetails.tsx` (마크다운 리포트 디스플레이)**
  * **목적**: 4대 애널리스트가 수립한 정성 보고서와 연구 팀의 찬반 회의록 텍스트를 파싱하여 이쁘게 정렬된 마크다운 카드 리스트 형태로 화면에 출력합니다.
  * **소스 코드 위치**: `frontend/src/components/ReportDetails.tsx` $\rightarrow$ [[ReportDetails.tsx#L1]]

---

## 📻 2. EventSource API 기반 실시간 SSE 스트리밍 수신부 (Server-Sent Events)

에이전트가 백엔드에서 2분 동안 분석을 수행하는 과정을 브라우저가 화면 새로고침 없이 실시간 트래킹하기 위해, 호출 오버헤드가 극심한 전통적 단기 폴링(Short Polling) 대신 HTTP 단일 영속 연결 기반의 **Server-Sent Events (SSE)** 수신 모듈을 구축했습니다. (백엔드 큐 대기 구조: [[06_backend_api.md]])

```
                    [ SSE 실시간 통신 이벤트 파이프라인 ]

  [ Web Browser (Timeline.tsx) ] ────► 수신 리스너 등록 (`/api/runs/stream`)
                                           │
                                           ▼ (단일 TCP 소켓 오픈 후 대기)
                                    📡 [ EventSource API ]
                                           ▲
                                           │  (백엔드 노드 클리어 시점마다 패킷 브로드캐스트)
  [ backend (services.py) ] ────────┼── "event: progress (시장분석 진행률 20%)"
                                           ├── "event: progress (토론배틀 진행률 60%)"
                                           └── "event: completed (최종 완료 100%)"
```

### 📡 2.1 Timeline.tsx의 EventSource 리스너 구현 패턴
* **소스 코드 위치**: `frontend/src/components/Timeline.tsx`

클라이언트 브라우저는 수립된 엔드포인트 URL로 `EventSource` 인스턴스를 즉석 점화하고 리액티브한 이벤트 감시 상태로 진입합니다.

```typescript
// 1단계: 백엔드의 비동기 중계 스트리밍 엔드포인트로 커넥션을 연결합니다.
const eventSource = new EventSource(`${BACKEND_URL}/api/v1/runs/stream`);

// 2단계: 'progress'라는 명칭으로 브로드캐스트되는 실시간 이벤트를 트랩합니다.
eventSource.addEventListener("progress", (event) => {
  try {
    const payload = JSON.parse(event.data);
    
    // 3단계: 전달받은 정량 진행율 수치와 로그 메시지를 React의 상태 변수로 바인딩합니다.
    setProgress(payload.progress);
    setCurrentStepText(payload.current_step);
    
    // 실시간 로그 터미널 창에 실시간으로 로그 문자열을 스트리밍 누적
    setLiveLogs((prev) => [...prev, payload.log]);
  } catch (err) {
    console.error("SSE parse error:", err);
  }
});
```

> [!TIP]
> **네트워크 결합 복구 메커니즘**
> * 브라우저의 EventSource 객체는 와이파이 단절 등으로 인해 연결이 유실될 시, 백엔드 서버에 추가 조작 없이 즉석에서 3초 간격으로 자동 연결 복구 시도(Auto-Reconnection)를 수행하도록 네이티브 표준 규격으로 통제되어 강력한 통신 유지보수성을 보장합니다.

---

## 🎨 3. HTML5 Canvas 및 GPU 가속 기반 초고속 금융 차트 시각화

![[lightweight_charts_canvas.png]]

백테스트 시뮬레이션 결과로 쏟아지는 수만 줄의 일별 시계열 데이터(Open, High, Low, Close 가격 배열 및 일별 Portfolio Value 자산 값)를 브라우저 내에서 부드럽게 렌더링하기 위해, 시스템은 TradingView가 빚어낸 오픈소스 금융 드로잉 엔진 **`Lightweight Charts`**를 내장하고 있습니다.

### ⚙️ 3.1 Lightweight Charts의 시각적 및 성능적 핵심 이점

1. **HTML5 Canvas 렌더링**:
   * 매 화면 갱신 시마다 무거운 DOM 태그 수천 개를 다시 렌더링하는 SVG 차트 방식과 달리, 그래픽 메모리 비트맵 위에 직접 초고속 픽셀 도포를 실행하는 **HTML5 Canvas** 드로잉 모드를 사용합니다.
2. **GPU 하드웨어 가속**:
   * 브라우저의 WebGL/GPU 가속 파이프라인과 완벽 동기화되어 마우스로 스크롤하거나 줌인/줌아웃을 초고속으로 왕복 실행해도 **밀리초(ms) 단위의 화면 딜레이나 렉 현상 없이 60FPS의 우아하고 매끄러운 줌 스크롤 렌더링**을 구현해 냅니다.
3. **타임스케일 동기화 (Time Scale Synchronization)**:
   * 메인 캔들 차트와 하단의 보조 지표 차트(RSI/MACD) 간의 시계열 이동이 양방향으로 동기화되어, 사용자가 하나의 스케일을 잡아끌면 다른 하나도 동기화되어 고속 자동 이동합니다:
```typescript
mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
  if (range && indChart) {
    indChart.timeScale().setVisibleRange(range);
  }
});
```

### 💵 3.2 3중 퀀트 가격선 오버레이 파싱 알고리즘 (`parseQuantPriceLevels`)

`ChartPanel` 컴포넌트는 포트폴리오 매니저 에이전트의 종합 보고서(`decisionText`) 내에 기록된 **매수진입가, 익절목표가, 손절기준선** 자연어를 실시간 정규식으로 역추출하여 차트에 점선 지지선으로 렌더링합니다:

* **소스 코드 위치**: `frontend/src/components/ChartPanel.tsx` $\rightarrow$ [[ChartPanel.tsx#L33]]

```typescript
const parseQuantPriceLevels = (decisionText: string | null | undefined, fallbackPrice: number): PriceLevels => {
  let entry = fallbackPrice;
  let target = fallbackPrice * 1.15;   // 기본 익절가: +15% 편차 적용
  let stopLoss = fallbackPrice * 0.95; // 기본 손절가: -5% 편차 적용
  
  if (!decisionText) return { entry, target, stopLoss };
  
  // 50%를 넘는 비정상 가격 노이즈 필터링 장치 (임계 범위)
  const maxDeviation = 0.5;
  const isReasonable = (val: number) => {
    return !isNaN(val) && val > 0 && Math.abs(val - fallbackPrice) / fallbackPrice <= maxDeviation;
  };

  const lines = decisionText.split("\n");
  for (const line of lines) {
    const lowerLine = line.toLowerCase();
    
    // 라인 내 유효 가격 숫자 추출 ($ 표기, 천단위 콤마 정화)
    const matches = line.matchAll(/(?:\$|₩)?\s*([0-9,]+(?:\.[0-9]+)?)/gi);
    const candidates: number[] = [];
    for (const m of matches) {
      const val = parseFloat(m[1].replace(/,/g, ""));
      if (isReasonable(val)) candidates.push(val);
    }

    if (candidates.length > 0) {
      const bestCandidate = candidates.reduce((prev, curr) => 
        Math.abs(curr - fallbackPrice) < Math.abs(prev - fallbackPrice) ? curr : prev
      );

      // 키워드 검사 및 타겟 바인딩
      if (lowerLine.includes("매수") || lowerLine.includes("진입") || lowerLine.includes("entry")) {
        entry = bestCandidate;
      }
      if (lowerLine.includes("목표") || lowerLine.includes("익절") || lowerLine.includes("target")) {
        target = bestCandidate;
      }
      if (lowerLine.includes("손절") || lowerLine.includes("stop loss") || lowerLine.includes("sl")) {
        stopLoss = bestCandidate;
      }
    }
  }
  return { entry, target, stopLoss };
};
```

* **동적 가격선 렌더링**: 이렇게 추출된 세 가격 수준(`entry`, `target`, `stopLoss`)은 `createPriceLine` 라이브러리 함수를 통해 차트 위에 실시간으로 오버레이 점선으로 동적 렌더링되어 사용자가 시각적으로 거래 전략 범위를 인지하도록 돕습니다.
