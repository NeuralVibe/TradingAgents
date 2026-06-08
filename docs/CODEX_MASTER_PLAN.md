# TradingAgents AI-Quant 고도화 마스터 플랜

작성일: 2026-06-07  
대상: TradingAgents 프로젝트  
사용 목적: Codex가 이 문서를 기준으로 전체 개선 방향을 이해하고, 단계별로 안전하게 분석·수정·검증을 진행하도록 한다.

---

## 0. 핵심 결론

현재 TradingAgents 프로젝트의 방향은 좋다. 멀티 에이전트 구조를 통해 시장, 뉴스, 감성, 펀더멘털, Bull/Bear 토론, Trader, Risk, Portfolio Manager 흐름을 갖추고 있다.

하지만 현재 구조는 아직 **“AI 투자 리포트 생성기”에 가깝고, “백테스트 가능한 정량 매매 신호 생성기”로는 약하다.**

앞으로의 핵심 개선 방향은 다음이다.

```text
AI는 시장의 이야기를 읽고 해석한다.
결정론적 Quant Engine은 가격, 손절, 목표가, 리스크/리워드, 포지션 비중을 계산한다.
Signal Gate는 AI thesis와 정량 조건을 함께 검증한다.
Backtest Engine은 이 신호가 실제로 통하는지 엄격히 검증한다.
```

즉, AI가 “좋은 뉴스다”, “전망이 좋다”고 판단해도, 현재 가격이 비싸거나 risk/reward가 나쁘면 최종 신호는 `BUY`가 아니라 `WAIT`, `HOLD`, `WAIT_FOR_PULLBACK`이 되어야 한다.

---

## 1. 이 마스터 플랜의 전제

### 1.1 이번 개선의 목적

이 프로젝트의 목표는 다음이다.

1. AI가 주식을 분석하는 과정의 정확성 향상
2. AI 분석 결과를 백테스트 가능한 정량 신호로 변환
3. 매수가, 손절가, 목표가, 보유기간, 포지션 비중 산출의 금융공학적 타당성 강화
4. 현재 가격이 이미 비싼지, 적정한지, 눌림목을 기다려야 하는지 판단
5. look-ahead bias, data leakage, LLM hallucination, 임의 confidence score 위험 감소
6. 더 높은 위험조정수익률과 hit rate를 기대할 수 있는 검증 가능한 구조 구축

### 1.2 이번 개선의 제외 범위

다음은 이번 마스터 플랜에서 제외한다.

- 실제 브로커 API 연동
- 실제 주문 집행
- 계좌 잔고 조회
- 실시간 체결 처리
- 부분 체결 처리
- live trading adapter
- 실전 주문 실패 재시도
- 실거래용 kill switch
- 자동 매매 배포

단, 백테스트/시뮬레이션 정확도를 위한 다음 항목은 포함한다.

- next-bar execution
- 수수료
- 슬리피지
- stop_loss / take_profit
- trailing_stop
- position sizing
- volatility-adjusted sizing
- risk/reward filtering
- paper-style simulation

---

## 2. 핵심 설계 철학

### 2.1 AI와 결정론적 계산을 분리한다

LLM/AI는 비결정론적이다. 같은 입력에도 약간 다른 표현이나 판단을 낼 수 있다. 따라서 다음 영역은 AI가 담당해도 된다.

| 영역 | AI 적합도 | 이유 |
|---|---:|---|
| 뉴스 요약 | 높음 | 비정형 텍스트 해석에 강함 |
| 호재/악재 분류 | 높음 | 문맥과 뉘앙스 해석 가능 |
| 실적 발표 해석 | 높음 | 숫자와 설명을 함께 분석 가능 |
| 펀더멘털 thesis 생성 | 중~높음 | 여러 근거를 연결 가능 |
| Bull/Bear 시나리오 생성 | 높음 | 반대 논거 탐색에 유용 |
| 리스크 요인 발굴 | 높음 | 정성적 리스크 탐색에 강함 |
| 최종 설명문 생성 | 높음 | 사용자가 이해하기 쉬운 보고서 생성 가능 |

반대로 다음은 AI에게 단독으로 맡기면 안 된다.

| 영역 | AI 단독 판단 위험도 | 이유 |
|---|---:|---|
| 정확한 매수가 산출 | 매우 높음 | 실제 OHLCV, 지지/저항, 변동성 기반이어야 함 |
| 손절가 산출 | 매우 높음 | ATR, 최근 저점, 변동성 기반이어야 함 |
| 목표가 산출 | 매우 높음 | 저항선, risk/reward 기반이어야 함 |
| 포지션 비중 | 매우 높음 | 손절폭과 리스크 예산 기반이어야 함 |
| confidence 산출 | 높음 | LLM 말투가 아니라 데이터 조건 충족도 기반이어야 함 |
| 백테스트 성과 판단 | 매우 높음 | 체결 가정, 비용, 누수 방지 필요 |

따라서 최종 구조는 다음과 같아야 한다.

```text
AI Analysis Layer
    - 뉴스/감성/펀더멘털/시나리오 해석
    - 투자 thesis 생성
    - 리스크 요인 설명

Deterministic Quant Layer
    - 가격 위치 계산
    - 추세/변동성/거래량 점수 계산
    - entry/stop/take-profit 계산
    - risk/reward 계산
    - position size 계산

Signal Gate
    - AI thesis와 quant score 결합
    - risk/reward 불충족 시 BUY 차단
    - 가격 과열 시 WAIT_FOR_PULLBACK
    - 데이터 품질 부족 시 HOLD

Backtest Engine
    - next-bar execution
    - 수수료/슬리피지
    - stop/take-profit/trailing stop
    - 성과 지표
    - walk-forward validation
```

---

## 3. 현재 프로젝트에 대한 핵심 진단

Codex 1차 분석 결과 기준, 현재 프로젝트는 다음 한계를 갖는다.

### 3.1 AI 리포트와 정량 신호 사이의 손실

현재 Trader 단계에서 `entry_price`, `stop_loss`, `position_sizing` 같은 필드가 있을 수 있지만, DB와 백테스트까지 안정적으로 보존되지 않는다.

문제는 다음과 같다.

```text
AI가 매수가/손절가/포지션 비중을 말함
→ markdown/free-text로 렌더링됨
→ 일부만 regex/heuristic으로 추출됨
→ DB에는 side/confidence/horizon/price_target 정도만 저장됨
→ 백테스트는 실제 entry/stop/position_sizing을 거의 사용하지 않음
```

결과적으로 AI가 가격 제안을 잘했는지 나쁘게 했는지 검증하기 어렵다.

### 3.2 백테스트 신뢰성 문제

Codex 분석상 현재 백테스트에는 다음 P0 문제가 있다.

1. 신호일과 체결일 분리 없음
2. `bfill()` 사용으로 미래 가격이 과거로 누수될 가능성
3. stop_loss / take_profit 미반영
4. confidence fallback이 임의적
5. BUY 계열만 long 진입하고 SELL/UNDERWEIGHT는 충분히 평가하지 못함

특히 다음 두 가지는 최우선으로 수정해야 한다.

```text
1. next-bar execution
2. bfill 제거
```

백테스트가 미래 정보를 사용하면 이후 어떤 전략을 추가해도 성과 검증이 무의미해진다.

### 3.3 “좋은 뉴스”와 “좋은 매수 가격”이 구분되지 않음

AI가 긍정적인 뉴스를 해석하더라도, 현재 가격이 이미 과도하게 상승했다면 매수하면 안 된다.

예시:

```text
뉴스: 긍정적
현재가: 120
지지선: 110
저항선: 125
손절가: 108
목표가: 125

risk = 120 - 108 = 12
reward = 125 - 120 = 5
risk/reward = 0.42

결론:
뉴스는 긍정적이지만 현재 가격은 매수 매력이 낮다.
최종 신호는 BUY가 아니라 WAIT 또는 WAIT_FOR_PULLBACK이어야 한다.
```

이 판단을 하려면 AI가 아니라 결정론적 가격 계산 레이어가 필요하다.

---

## 4. 최종 목표 아키텍처

### 4.1 계층 구조

```text
[1] Data Layer
    - OHLCV
    - adjusted price
    - technical indicators
    - news
    - sentiment
    - fundamentals
    - benchmark / sector ETF
    - trading calendar

[2] AI Analysis Layer
    - Market Analyst
    - News Analyst
    - Sentiment Analyst
    - Fundamentals Analyst
    - Bull/Bear Researchers
    - Research Manager
    - Risk Analysts
    - Portfolio Manager

[3] Deterministic Quant Layer
    - price location
    - trend score
    - volatility regime
    - volume confirmation
    - ATR
    - support/resistance
    - entry zone
    - stop loss
    - take profit
    - risk/reward
    - position size
    - signal quality score

[4] Signal Gate
    - AI thesis validation
    - price attractiveness validation
    - risk/reward validation
    - volatility filter
    - liquidity filter
    - data quality filter
    - action conversion

[5] Structured Signal Layer
    - TradeSignal
    - SignalEvidence
    - SignalRisk
    - deterministic calculation fields
    - AI explanation fields

[6] Backtest Engine
    - next-bar execution
    - fee/slippage
    - stop/take-profit
    - trailing stop
    - max holding days
    - exposure/turnover
    - performance metrics
    - walk-forward validation
```

### 4.2 핵심 원칙

1. AI는 숫자를 “창작”하지 않는다.
2. AI가 숫자를 제안할 경우 반드시 근거 필드를 함께 남긴다.
3. 가격 관련 핵심 수치는 결정론적 계산 함수에서 산출한다.
4. AI의 BUY 의견은 Signal Gate를 통과해야만 최종 BUY가 된다.
5. risk/reward가 나쁘면 AI가 긍정적이어도 매수하지 않는다.
6. 데이터 품질이 부족하면 confidence를 낮추거나 HOLD 처리한다.
7. 백테스트는 항상 신호일 다음 거래일 체결을 기본값으로 한다.
8. 미래 가격 또는 미래 뉴스가 과거 판단에 들어가면 안 된다.
9. 모든 개선은 테스트를 동반한다.
10. Codex는 한 번에 대규모 리팩토링하지 않고 단계별로 진행한다.

---

## 5. Codex 작업 방식 공통 규칙

Codex는 각 단계마다 다음 절차를 따른다.

```text
1. 관련 파일을 먼저 읽는다.
2. 현재 구조를 요약한다.
3. 최소 변경 범위를 제안한다.
4. 해당 단계의 범위 밖 파일은 수정하지 않는다.
5. 코드를 수정한다.
6. 테스트를 추가한다.
7. 관련 테스트를 실행한다.
8. 변경 결과와 남은 한계를 보고한다.
```

### 5.1 공통 금지 사항

- 실제 매매 API 구현 금지
- 브로커 연동 코드 작성 금지
- 불필요한 대규모 구조 변경 금지
- 기존 UI/DB를 한 번에 크게 깨는 변경 금지
- 테스트 없는 대규모 리팩토링 금지
- 수익률 보장 표현 금지
- “AI가 판단했으므로 매수” 같은 구조 금지
- 가격 수치를 LLM 자유 생성에 의존하는 구조 금지

### 5.2 공통 완료 보고 형식

각 Codex 작업은 다음 형식으로 보고한다.

```markdown
## 작업 요약
## 수정한 파일
## 수정한 함수/클래스
## 변경 전 문제
## 변경 후 동작
## 추가/수정한 테스트
## 실행한 테스트 명령
## 테스트 결과
## 남은 한계
## 다음 단계 제안
```

---

# Phase 1. 백테스트 신뢰성 확보

## 1.1 목표

백테스트가 미래 정보를 사용하지 않도록 최소한의 신뢰성 기반을 만든다.

## 1.2 핵심 문제

현재 백테스트는 신호일과 체결일이 분리되어 있지 않을 가능성이 있다.  
또한 `bfill()` 사용으로 미래 가격이 과거 날짜로 채워질 가능성이 있다.

## 1.3 작업 범위

수정 대상 후보:

```text
backend/app/quant_engine.py
tests/test_quant_backtest.py
```

## 1.4 구현 요구사항

### next-bar execution

신호가 `date=D`에 생성되면 같은 날짜 가격으로 진입하지 않는다.

```text
기존:
D일 신호 → D일 가격으로 진입

개선:
D일 신호 → 가격 데이터상 다음 거래일 D+1에 진입
```

규칙:

- 다음 거래일이 없으면 진입하지 않는다.
- `entry_date`는 실제 진입일로 기록한다.
- `entry_price`는 실제 진입일 가격으로 기록한다.
- 신호일과 진입일을 구분한다.
- 기존 summary metric 인터페이스는 유지한다.

### bfill 제거

`fetch_price_history()`에서 미래 가격을 과거로 채우는 처리를 제거한다.

```python
# 위험한 방식
df = df.ffill().bfill()

# 개선 방향
df = df.ffill()
```

단, 첫 유효가격 이전 구간은 거래 불가로 처리해야 한다.

## 1.5 테스트 요구사항

다음 테스트를 추가한다.

1. 신호일 당일에는 진입하지 않는지
2. 다음 거래일 가격으로 `entry_date`가 기록되는지
3. 다음 거래일 가격으로 `entry_price`가 기록되는지
4. 마지막 거래일 신호는 진입하지 않는지
5. 첫 유효가격 이전 결측이 미래 가격으로 채워져 거래되지 않는지
6. 기존 테스트가 깨질 경우, 기존 테스트가 잘못된 동작에 의존했는지 설명

## 1.6 완료 조건

- 백테스트가 신호일 당일 진입하지 않는다.
- `bfill()`로 미래 가격이 과거로 들어가지 않는다.
- 관련 테스트가 통과한다.
- DB schema, UI, Trader/PM schema는 변경하지 않는다.

## 1.7 Codex 프롬프트

```text
다음 작업에서는 코드 수정을 수행하라.

목표:
백테스트의 look-ahead 가능성을 줄이기 위해 next-bar execution을 구현하고, 가격 결측 처리에서 미래 가격이 과거 날짜로 채워지지 않도록 수정하라.

수정 대상:
- backend/app/quant_engine.py
- tests/test_quant_backtest.py

요구사항:
- 신호가 date=D에 생성되면 같은 날짜에 진입하지 말고, 가격 데이터상 다음 거래일에 진입하도록 변경하라.
- 마지막 거래일이라 다음 거래일이 없으면 해당 신호는 진입하지 않는다.
- trades 결과의 entry_date는 실제 진입일, 즉 다음 거래일로 기록되어야 한다.
- entry_price도 실제 진입일의 가격을 사용해야 한다.
- fetch_price_history()에서 bfill()을 제거하라.
- 결측 가격은 미래 가격으로 과거를 채우지 말라.
- 첫 유효가격 이전에는 해당 종목을 거래하지 말라.
- 기존 fixed/confidence sizing 동작은 유지하라.
- 기존 summary metric 계산 인터페이스는 유지하라.
- DB schema, API schema, UI, Trader/PM schema는 이번 작업에서 변경하지 말라.
- 실제 주문 API 또는 브로커 API 관련 코드는 작성하지 말라.

테스트를 추가하라:
- 신호일 당일에는 진입하지 않는지
- 다음 거래일 가격으로 entry_date/entry_price가 기록되는지
- 마지막 거래일 신호는 진입하지 않는지
- 첫 유효가격 이전 결측이 미래 가격으로 채워져 거래되지 않는지
- 기존 테스트가 실패하면 기존 테스트가 잘못된 동작에 의존한 것인지 설명하고 최소 수정하라.

작업 후 보고:
- 변경한 파일
- 변경한 함수
- 테스트 결과
- 기존 백테스트 결과 해석이 어떻게 달라지는지
- 남은 한계
```

---

# Phase 2. stop_loss / take_profit 백테스트 반영

## 2.1 목표

AI 또는 결정론적 엔진이 산출한 손절가와 목표가가 실제 백테스트 성과에 반영되도록 한다.

현재 문제:

```text
AI가 stop_loss / price_target을 말해도
백테스트는 horizon_days 도달 시점에만 청산
```

이 구조에서는 손절/목표가의 품질을 검증할 수 없다.

## 2.2 작업 범위

수정 대상 후보:

```text
backend/app/quant_engine.py
backend/app/schemas.py
tests/test_quant_backtest.py
```

초기에는 DB migration 없이 signal dict optional field로 시작한다.

## 2.3 설계 방향

### 입력 signal 확장

백테스트 signal dict가 다음 optional field를 받을 수 있게 한다.

```python
{
    "ticker": "AAPL",
    "date": "2026-06-01",
    "side": "BUY",
    "confidence": 0.7,
    "horizon_days": 10,
    "entry_price": 100.0,
    "stop_loss": 95.0,
    "take_profit": 110.0,
    "trailing_stop_pct": None
}
```

### OHLC 필요성

close-only 가격만으로는 장중 손절/목표가 도달 여부를 정확히 판단하기 어렵다.  
가능하면 OHLC 데이터를 사용한다.

필요 컬럼:

```text
Open
High
Low
Close
```

### 보수적 체결 규칙

일봉 데이터에서 같은 날 stop_loss와 take_profit이 모두 닿으면 어느 것이 먼저인지 알 수 없다.

보수적 기본 규칙:

```text
같은 날 stop_loss와 take_profit이 모두 닿으면 stop_loss 우선 처리
```

이는 성과 과대평가를 막기 위한 기본값이다.

## 2.4 청산 규칙

long-only 기준:

```text
if low <= stop_loss:
    exit at stop_loss adjusted by slippage
elif high >= take_profit:
    exit at take_profit adjusted by slippage
elif horizon_days reached:
    exit at close adjusted by slippage
```

추후 short 지원 시 별도 규칙을 추가한다.

## 2.5 테스트 요구사항

1. stop_loss 도달 시 조기 청산
2. take_profit 도달 시 조기 청산
3. 같은 날 stop/take-profit 동시 도달 시 stop 우선
4. horizon_days 도달 시 청산
5. stop/take-profit 없으면 기존 방식 유지
6. 슬리피지 반영 확인

## 2.6 완료 조건

- stop_loss가 백테스트에 반영된다.
- take_profit이 백테스트에 반영된다.
- 보수적 동시 도달 규칙이 테스트된다.
- 기존 백테스트 API 응답 구조는 가능한 유지한다.

---

# Phase 3. 결정론적 가격 계산 레이어 도입

## 3.1 목표

AI가 매수가/손절가/목표가를 임의로 생성하지 않도록, 가격 관련 핵심 수치를 결정론적 함수로 계산한다.

## 3.2 신규 모듈 후보

Codex는 실제 코드 구조를 확인한 뒤 가장 자연스러운 위치를 선택한다.

후보:

```text
backend/app/quant_signals.py
backend/app/price_evaluator.py
tradingagents/quant/price_evaluation.py
tradingagents/dataflows/price_features.py
```

권장 방향:

- 백엔드 백테스트와 AI 파이프라인이 함께 써야 한다면 `tradingagents/quant/` 하위 신규 모듈을 검토
- 우선 백엔드 백테스트만 쓰는 계산이면 `backend/app/quant_signals.py`부터 시작 가능

## 3.3 필수 함수

다음 함수를 구현한다.

```python
def calculate_atr(ohlcv, period: int = 14) -> float:
    pass

def calculate_trend_score(ohlcv) -> float:
    pass

def calculate_volatility_regime(ohlcv) -> str:
    pass

def calculate_volume_score(ohlcv) -> float:
    pass

def detect_support_resistance(ohlcv, lookback: int = 60) -> dict:
    pass

def calculate_entry_zone(ohlcv, strategy: str = "pullback_or_breakout") -> dict:
    pass

def calculate_stop_loss(entry_price: float, atr: float, support: float | None = None) -> dict:
    pass

def calculate_take_profit(entry_price: float, stop_loss: float, resistance: float | None = None) -> dict:
    pass

def calculate_risk_reward(entry_price: float, stop_loss: float, take_profit: float) -> float:
    pass

def calculate_position_size_pct(
    entry_price: float,
    stop_loss: float,
    account_risk_pct: float = 0.01,
    max_position_pct: float = 0.15
) -> float:
    pass

def evaluate_price_attractiveness(ohlcv, entry_price, stop_loss, take_profit) -> dict:
    pass
```

## 3.4 ATR 계산

ATR은 변동성 지표다. 방향성을 말하지 않고 가격의 평균 변동 폭을 측정한다.

True Range:

```text
TR = max(
    high - low,
    abs(high - previous_close),
    abs(low - previous_close)
)
```

ATR:

```text
ATR = rolling_mean(TR, period)
```

활용:

```text
stop_loss = entry_price - ATR * 1.5
take_profit = entry_price + (entry_price - stop_loss) * target_rr
```

## 3.5 추세 점수

예시:

```text
현재가 > SMA20 > SMA50 > SMA200  → 강한 상승 추세
현재가 > SMA50 > SMA200         → 상승 추세
현재가 < SMA50 < SMA200         → 하락 추세
그 외                              → 중립/혼조
```

점수 예시:

```text
strong_uptrend = 1.0
uptrend = 0.7
neutral = 0.5
downtrend = 0.2
strong_downtrend = 0.0
```

## 3.6 가격 위치 점수

현재가가 너무 비싼지 판단한다.

검토 요소:

```text
현재가 / 20일 고점
현재가 / 60일 고점
현재가 / Bollinger upper band
현재가와 최근 저항선 거리
현재가와 최근 지지선 거리
최근 n일 상승률
갭 상승 여부
```

예시:

```text
if current_price >= recent_resistance * 0.98:
    price_location = "near_resistance"
    attractiveness -= 0.3

if current_price > bollinger_upper:
    price_location = "overextended"
    attractiveness -= 0.4
```

## 3.7 risk/reward 계산

```text
risk = entry_price - stop_loss
reward = take_profit - entry_price
risk_reward_ratio = reward / risk
```

기본 판단:

```text
risk_reward_ratio < 1.2 → BUY 금지
1.2 <= rr < 1.8 → 낮은 confidence
1.8 <= rr < 2.5 → 정상 매수 후보
rr >= 2.5 → 우수 후보
```

## 3.8 포지션 사이징

confidence 기반 단순 비중보다 손절폭 기반 리스크 예산 방식이 우선되어야 한다.

```text
account_risk_pct = 1%
trade_risk_pct = abs(entry_price - stop_loss) / entry_price
raw_position_pct = account_risk_pct / trade_risk_pct
position_size_pct = min(raw_position_pct, max_position_pct)
```

예시:

```text
entry = 100
stop = 95
trade_risk_pct = 5%
account_risk_pct = 1%
raw_position_pct = 1 / 5 = 20%
max_position_pct = 15%
position_size_pct = 15%
```

## 3.9 완료 조건

- 가격 관련 수치가 LLM 없이 계산된다.
- 각 함수에 단위 테스트가 있다.
- 결측 데이터 또는 짧은 데이터 구간에서 안전하게 동작한다.
- 수치 산출 근거가 dict 형태로 반환된다.
- AI가 후속 단계에서 이 값을 해석할 수 있다.

---

# Phase 4. TradeSignal 구조화 레이어 도입

## 4.1 목표

AI 자연어 리포트와 백테스트 가능한 정량 신호를 분리한다.

현재 문제:

```text
최종 판단이 markdown/free-text로 저장됨
→ regex로 일부 추출
→ 정보 손실
→ 백테스트와 리포트가 분리되지 않음
```

## 4.2 설계 방향

기존 `TraderProposal`, `PortfolioDecision`을 무리하게 깨지 말고, 하위 호환성을 유지한다.

우선 다음 중 하나를 선택한다.

1. 기존 Pydantic schema에 optional field 추가
2. 신규 `TradeSignal` schema 추가
3. 백엔드 내부용 `ParsedTradeSignal` schema 추가

Codex는 실제 의존성을 확인하고 가장 안전한 방식을 선택한다.

## 4.3 권장 TradeSignal 필드

```python
class TradeSignal(BaseModel):
    ticker: str
    as_of_date: str
    action: Literal[
        "BUY",
        "SELL",
        "HOLD",
        "OVERWEIGHT",
        "UNDERWEIGHT",
        "WAIT",
        "WAIT_FOR_PULLBACK"
    ]

    # AI thesis
    ai_thesis_score: Optional[float] = None
    ai_summary: Optional[str] = None
    bullish_factors: list[str] = []
    bearish_factors: list[str] = []

    # deterministic price fields
    current_price: Optional[float] = None
    entry_price: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    expected_holding_days: int = 5

    # risk/return fields
    risk_reward_ratio: Optional[float] = None
    max_loss_pct: Optional[float] = None
    position_size_pct: Optional[float] = None

    # scores
    confidence: float
    signal_quality_score: Optional[float] = None
    trend_score: Optional[float] = None
    momentum_score: Optional[float] = None
    volatility_score: Optional[float] = None
    volume_score: Optional[float] = None
    price_attractiveness_score: Optional[float] = None
    data_quality_score: Optional[float] = None

    # regime
    market_regime: Optional[str] = None
    volatility_regime: Optional[str] = None

    # validation and audit
    invalidation_condition: Optional[str] = None
    evidence: list[str] = []
    risk_flags: list[str] = []
    calculation_basis: dict = {}
```

## 4.4 핵심 원칙

- 자연어 보고서는 사용자 이해용이다.
- `TradeSignal`은 백테스트/성과 분석용이다.
- 백테스트는 free-text보다 `TradeSignal`을 우선 사용한다.
- free-text parser는 fallback으로만 유지한다.
- 한국어/영어 출력에 따른 regex drift를 줄인다.

## 4.5 완료 조건

- 최종 신호를 구조화된 형태로 보존할 수 있다.
- 기존 markdown 리포트 출력은 유지된다.
- 백테스트가 구조화 필드를 사용할 준비가 된다.
- 기존 UI가 깨지지 않는다.

---

# Phase 5. AI 판단과 결정론적 계산 결합

## 5.1 목표

AI가 매수 여부를 단독으로 결정하지 않도록 한다.  
AI thesis와 결정론적 계산 결과를 결합한 최종 의사결정 구조를 만든다.

## 5.2 Trader 역할 재정의

기존 Trader가 직접 가격을 만들어내는 구조에서 벗어난다.

기존:

```text
AI Trader가 entry_price, stop_loss, position_sizing을 직접 제안
```

개선:

```text
Quant Engine이 entry/stop/target/size를 계산
AI Trader는 그 계산 결과가 투자 thesis와 일치하는지 해석
AI Trader는 BUY/WAIT/HOLD의 설명을 생성
```

## 5.3 AI에게 제공할 입력

Trader 또는 Portfolio Manager prompt에는 다음 정량 계산 결과를 넣는다.

```text
current_price
entry_zone
stop_loss
take_profit
risk_reward_ratio
position_size_pct
trend_score
volatility_regime
price_attractiveness_score
volume_score
data_quality_score
```

## 5.4 AI에게 금지할 것

AI prompt에 다음 규칙을 넣는다.

```text
- 제공된 정량 계산값을 임의로 변경하지 말라.
- 새로운 매수가/손절가/목표가를 창작하지 말라.
- 가격 수치가 불충분하면 None 또는 확인 필요로 표시하라.
- 좋은 뉴스라도 risk/reward가 낮으면 BUY를 내지 말라.
- 현재 가격이 과열이면 WAIT_FOR_PULLBACK을 검토하라.
```

## 5.5 예시 최종 판단

```text
뉴스와 펀더멘털은 긍정적입니다.
하지만 현재가는 최근 저항선의 98% 구간에 있으며 risk/reward가 0.9로 낮습니다.
따라서 즉시 BUY가 아니라 WAIT_FOR_PULLBACK입니다.
권장 진입 구간은 112~115, 손절가는 106, 목표가는 128입니다.
```

## 5.6 완료 조건

- AI는 정량 결과를 설명하고 해석한다.
- 가격 관련 핵심 숫자는 결정론적 계산에서 나온다.
- AI가 긍정적이어도 Signal Gate 조건을 만족하지 않으면 BUY가 나오지 않는다.

---

# Phase 6. Signal Gate 도입

## 6.1 목표

최종 BUY/HOLD/WAIT 판단을 룰 기반 gate로 검증한다.

## 6.2 Signal Gate 기본 구조

```python
def apply_signal_gate(ai_result, quant_result) -> dict:
    action = ai_result.action

    if quant_result.data_quality_score < 0.7:
        return HOLD_OR_WAIT("Insufficient data quality")

    if quant_result.risk_reward_ratio is None:
        return HOLD_OR_WAIT("Missing risk/reward")

    if quant_result.risk_reward_ratio < 1.2:
        return WAIT("Poor risk/reward")

    if quant_result.price_location == "overextended":
        return WAIT_FOR_PULLBACK("Price overextended")

    if quant_result.volatility_regime == "extreme":
        reduce_position_size()

    if ai_result.thesis_score < 0.5:
        return HOLD("Weak AI thesis")

    return validated_signal
```

## 6.3 권장 Gate 조건

| 조건 | 처리 |
|---|---|
| data_quality_score < 0.7 | HOLD |
| risk_reward_ratio < 1.2 | WAIT |
| price overextended | WAIT_FOR_PULLBACK |
| near resistance and low reward | WAIT |
| volatility extreme | position_size 축소 |
| volume insufficient | confidence 하향 |
| trend bearish and AI BUY | HOLD 또는 낮은 confidence |
| stop_loss 없음 | BUY 금지 |
| take_profit 없음 | BUY 금지 |
| position_size_pct 없음 | 기본 보수 비중 적용 |

## 6.4 완료 조건

- AI가 BUY를 냈더라도 Gate를 통과하지 못하면 BUY가 차단된다.
- Gate 결과와 차단 사유가 기록된다.
- 백테스트에서 Gate 적용 전/후 성과 비교가 가능하다.

---

# Phase 7. confidence calibration 개선

## 7.1 목표

현재 confidence가 LLM 문장 또는 rating fallback 값에 과도하게 의존하지 않도록 한다.

## 7.2 현재 문제

예상 문제:

```text
STRONG BUY → 0.90
BUY → 0.80
OVERWEIGHT → 0.65
HOLD → 0.50
```

이런 방식은 너무 낙관적일 수 있다.  
특히 confidence가 포지션 비중에 직접 사용되면 위험하다.

## 7.3 개선 방향

confidence는 다음 요소로 계산 또는 보정한다.

```text
ai_thesis_score
agent_consensus_score
trend_score
volume_score
volatility_score
price_attractiveness_score
risk_reward_score
data_quality_score
historical_calibration_score
```

초기 버전 예시:

```python
confidence = 0.50
confidence += 0.10 * trend_score
confidence += 0.10 * volume_score
confidence += 0.15 * risk_reward_score
confidence += 0.10 * price_attractiveness_score
confidence += 0.10 * ai_thesis_score
confidence -= volatility_penalty
confidence -= data_quality_penalty
confidence = clamp(confidence, 0.0, 1.0)
```

## 7.4 보수적 fallback

명시 confidence가 없을 때 기본값은 낮게 잡는다.

예시:

```text
STRONG BUY fallback: 0.70
BUY fallback: 0.60
OVERWEIGHT fallback: 0.55
HOLD fallback: 0.50
UNDERWEIGHT fallback: 0.45
SELL fallback: 0.40
```

기존 0.8~0.9 fallback은 과신 위험이 있다.

## 7.5 완료 조건

- confidence가 단순 regex/rating fallback에만 의존하지 않는다.
- confidence 산출 근거가 기록된다.
- position_size는 confidence만이 아니라 손절폭 기반 risk budget을 우선한다.
- confidence 변경 전/후 백테스트 비교가 가능하다.

---

# Phase 8. 백테스트 고도화

## 8.1 목표

전략 성과를 더 현실적으로 검증한다.

## 8.2 개선 항목

### 비용 반영

```text
fee_rate
slippage
tax 또는 market-specific cost
```

### 청산 로직

```text
stop_loss
take_profit
trailing_stop
max_holding_days
opposite signal exit
UNDERWEIGHT/SELL exit
```

### 포지션 제한

```text
max_positions
max_position_pct
max_sector_exposure
max_total_exposure
```

### 성과 지표

필수 지표:

```text
cumulative_return
CAGR
MDD
Sharpe
Sortino
Calmar
win_rate
profit_factor
average_win
average_loss
payoff_ratio
turnover
exposure
alpha
beta
slippage_adjusted_return
fee_adjusted_return
```

## 8.3 SELL/UNDERWEIGHT 처리

초기에는 short을 구현하지 않는다.

대신 다음처럼 처리한다.

```text
SELL:
    기존 long 포지션이 있으면 청산
    신규 long 진입 금지

UNDERWEIGHT:
    기존 long 포지션이 있으면 일부 축소 또는 청산 후보
    신규 long 진입 금지

HOLD:
    신규 진입 없음
    기존 포지션 유지 또는 horizon 규칙 따름
```

## 8.4 완료 조건

- stop/take-profit 기반 성과가 측정된다.
- SELL/UNDERWEIGHT가 long-only 백테스트에서 의미 있게 반영된다.
- 비용 반영 전/후 성과를 비교할 수 있다.
- 성과 지표가 NaN 없이 산출된다.

---

# Phase 9. AI 에이전트 구조 고도화

## 9.1 목표

각 에이전트가 자연어 리포트만 생성하지 않고, 구조화된 판단 점수를 함께 남기도록 한다.

## 9.2 에이전트별 개선 방향

| 에이전트 | 현재 역할 | 개선 방향 |
|---|---|---|
| Market Analyst | 기술적 분석 리포트 | trend_score, momentum_score, volatility_score 출력 |
| Sentiment Analyst | 감성 리포트 | sentiment_score, sentiment_confidence 출력 |
| News Analyst | 뉴스 요약 | news_impact_score, event_risk_score 출력 |
| Fundamentals Analyst | 재무 분석 | fundamental_score, valuation_risk_score 출력 |
| Bull Researcher | 상승 논거 | bullish_score, key_bull_factors 출력 |
| Bear Researcher | 하락 논거 | bearish_score, key_bear_factors 출력 |
| Research Manager | 논거 종합 | ai_thesis_score, disagreement_level 출력 |
| Trader | 매매 제안 | 정량 계산값 해석, BUY/WAIT/HOLD 설명 |
| Risk Analysts | 리스크 검토 | risk_flags, risk_penalty_score 출력 |
| Portfolio Manager | 최종 판단 | structured TradeSignal 생성 또는 승인 |

## 9.3 Agent Consensus Score

구조화 점수가 쌓이면 consensus를 계산한다.

```text
agent_consensus_score =
    weighted_average(
        market_score,
        news_score,
        sentiment_score,
        fundamental_score,
        risk_adjusted_score
    )
```

초기에는 모든 에이전트에 강제하지 말고, Market/Research Manager/PM부터 시작한다.

## 9.4 완료 조건

- 최소 일부 에이전트가 구조화 점수를 출력한다.
- 자연어 리포트와 정량 점수가 함께 저장된다.
- consensus score를 confidence 보정에 사용할 수 있다.

---

# Phase 10. 데이터 품질과 point-in-time 통제

## 10.1 목표

과거 백테스트에서 미래 정보가 들어가지 않도록 한다.

## 10.2 문제 영역

```text
yfinance info
Alpha Vantage OVERVIEW
뉴스 데이터
StockTwits/Reddit 최신 데이터
LLM의 사전학습 지식
재무제표 공시 시점
```

## 10.3 개선 방향

### 데이터별 as_of_date 강제

모든 데이터 함수는 가능하면 `as_of_date`를 받는다.

```python
get_news(ticker, as_of_date)
get_fundamentals(ticker, as_of_date)
get_sentiment(ticker, as_of_date)
get_indicators(ticker, as_of_date)
```

### point-in-time 불확실성 표시

확실하지 않은 데이터는 risk flag로 남긴다.

```text
risk_flags:
- fundamentals_not_point_in_time
- social_data_current_only
- news_timestamp_missing
- llm_parametric_lookahead_risk
```

### 백테스트 모드에서 최신 데이터 사용 금지

과거 날짜 분석 시 최신 소셜/뉴스 데이터를 쓰면 안 된다.  
해당 provider가 과거 조회를 지원하지 않으면 다음 중 하나로 처리한다.

```text
1. 해당 데이터 소스 제외
2. data_quality_score 하향
3. risk_flag 기록
4. confidence 하향
```

## 10.4 완료 조건

- 데이터 출처별 point-in-time 가능 여부가 명시된다.
- 백테스트에서 최신 데이터가 과거 판단에 섞이지 않도록 방어한다.
- 불확실한 데이터는 confidence를 낮춘다.

---

# Phase 11. 검증 체계 고도화

## 11.1 목표

전략이 과거 데이터에만 맞춰지는 것을 방지한다.

## 11.2 검증 단계

```text
1. 단일 백테스트
2. 종목별 성과 분해
3. 기간별 성과 분해
4. 상승장/하락장/횡보장 성과 분해
5. 비용 민감도 분석
6. 파라미터 민감도 분석
7. walk-forward validation
8. out-of-sample validation
9. paper simulation
```

## 11.3 walk-forward validation

기본 구조:

```text
Train window: 12개월
Test window: 3개월
Roll forward: 3개월
반복
```

각 window에서 다음을 저장한다.

```text
best parameters
test return
test MDD
test Sharpe
test Sortino
win rate
profit factor
trade count
```

## 11.4 parameter sweep

검증할 파라미터 예시:

```text
ATR period: 10, 14, 20
ATR stop multiple: 1.5, 2.0, 2.5
target risk/reward: 1.5, 2.0, 2.5
trend filter: on/off
volume filter: on/off
max position pct: 5%, 10%, 15%
```

## 11.5 완료 조건

- 단일 결과가 아니라 구간별/파라미터별 안정성을 평가한다.
- 특정 기간에만 성과가 좋은 전략을 구분한다.
- 최종 전략 변경은 out-of-sample 성과를 기준으로 판단한다.

---

# Phase 12. 문서화와 Codex 운영 체계

## 12.1 AGENTS.md 또는 CODEX_GUIDE.md 작성

Codex가 반복 작업을 안정적으로 수행하도록 repository-level instruction 파일을 만든다.

후보 파일:

```text
AGENTS.md
CODEX_GUIDE.md
docs/CODEX_MASTER_PLAN.md
```

내용:

```text
프로젝트 구조
테스트 명령
금지 사항
단계별 개발 원칙
백테스트 주의사항
AI/Quant 역할 분리 원칙
작업 완료 보고 형식
```

## 12.2 작업 단위

Codex 작업은 반드시 작은 단위로 나눈다.

권장 단위:

```text
작업 1: next-bar execution
작업 2: bfill 제거
작업 3: stop/take-profit 백테스트
작업 4: ATR 계산 함수
작업 5: risk/reward 함수
작업 6: position sizing 함수
작업 7: TradeSignal schema
작업 8: Signal Gate
작업 9: confidence calibration
```

## 12.3 완료 조건

- Codex가 매번 같은 개발 원칙을 따른다.
- 각 작업은 테스트와 함께 완료된다.
- 큰 리팩토링은 반드시 사전 분석 후 진행한다.

---

# 전체 단계별 우선순위 요약

| 순위 | Phase | 작업 | 이유 |
|---:|---|---|---|
| 1 | Phase 1 | next-bar execution + bfill 제거 | 백테스트 누수 제거 |
| 2 | Phase 2 | stop_loss/take_profit 백테스트 반영 | 리스크/수익 구조 검증 |
| 3 | Phase 3 | 결정론적 가격 계산 레이어 | AI 가격 hallucination 방지 |
| 4 | Phase 4 | TradeSignal 구조화 | 정량 신호 보존 |
| 5 | Phase 5 | AI + Quant 결합 | 좋은 뉴스와 좋은 가격 구분 |
| 6 | Phase 6 | Signal Gate | 불리한 가격의 BUY 차단 |
| 7 | Phase 7 | confidence calibration | 포지션 비중 근거 강화 |
| 8 | Phase 8 | 백테스트 고도화 | 현실성 강화 |
| 9 | Phase 9 | 에이전트 구조화 점수 | AI 판단 안정화 |
| 10 | Phase 10 | point-in-time 통제 | 미래 정보 누수 방지 |
| 11 | Phase 11 | walk-forward validation | 과최적화 방지 |
| 12 | Phase 12 | Codex 운영 문서화 | 반복 작업 안정화 |

---

# 핵심 판단 예시

## 잘못된 구조

```text
뉴스 긍정
AI가 BUY라고 판단
현재가로 매수
```

## 목표 구조

```text
뉴스 긍정
펀더멘털 양호
AI thesis score 높음

하지만:
현재가가 저항선 근처
risk/reward = 0.9
최근 5일 급등
ATR 대비 stop 폭 큼

최종:
BUY 금지
WAIT_FOR_PULLBACK
진입 후보 가격: 112~115
손절가: 106
목표가: 128
포지션 비중: 6%
```

---

# Codex가 항상 기억해야 할 최종 원칙

```text
좋은 기업은 좋은 매매가 아니다.
좋은 뉴스는 좋은 진입가가 아니다.
AI의 긍정 판단은 BUY의 필요조건일 수 있지만 충분조건은 아니다.
BUY는 반드시 가격, 손절, 목표가, risk/reward, 포지션 비중, 백테스트 가능성을 통과해야 한다.
```

---

# 참고 근거

이 마스터 플랜은 다음 일반 원칙을 반영한다.

1. AI 코딩 에이전트는 저장소를 읽고 수정하고 테스트를 실행할 수 있지만, 단계별 지시와 테스트가 중요하다.
2. 금융 LLM 백테스트에서는 모델이 과거 사건을 이미 알고 있을 수 있는 parametric look-ahead bias가 문제가 될 수 있다.
3. 금융 백테스트에서는 look-ahead bias, data leakage, in-sample overfitting을 피해야 한다.
4. ATR은 방향성 지표가 아니라 변동성 지표이며, stop-loss와 position sizing에 활용될 수 있다.
5. position sizing은 confidence만이 아니라 계좌 리스크, 손절폭, 변동성, 최대 비중을 고려해야 한다.
6. walk-forward validation은 전략이 과거 데이터에만 맞춰졌는지 확인하는 데 유용하다.

참고 자료:
- OpenAI Codex / coding agent 관련 공식·공개 설명
- Investopedia: Position Sizing, ATR, Volatility Stops
- Walk-forward optimization 관련 공개 설명
- Financial LLM look-ahead bias 관련 연구
- AI coding agents와 AGENTS.md 활용 관련 연구
