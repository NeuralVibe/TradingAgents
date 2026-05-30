import { useState, useEffect, useRef } from "react";
import { Activity, ShieldAlert, Cpu } from "lucide-react";
import { RunForm } from "./components/RunForm";
import { ChartPanel } from "./components/ChartPanel";
import { Timeline } from "./components/Timeline";
import { ReportDetails } from "./components/ReportDetails";

// API Base URL - Configured to point to FastAPI backend
const API_BASE = "http://localhost:8080/api";

interface LogEntry {
  timestamp: string;
  step: string;
  message: string;
  progress: number;
}

interface RunResponse {
  id: string;
  ticker: string;
  trade_date: string;
  status: string;
  progress: number;
  current_step: string;
  logs: string;
  result: string | null;
  decision: string | null;
  recommendation: string;
  created_at: string;
  updated_at: string;
}

function App() {
  const [history, setHistory] = useState<RunResponse[]>([]);
  const [activeRun, setActiveRun] = useState<RunResponse | null>(null);
  
  // Market data for charting
  const [marketData, setMarketData] = useState<any[]>([]);
  const [marketIndicators, setMarketIndicators] = useState<any>(null);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  
  // Active run states
  const [activeLogs, setActiveLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const sseRef = useRef<EventSource | null>(null);
  const [expandedSection, setExpandedSection] = useState<"chart" | "reports" | null>(null);

  // 1. Initial Load: Get Simulation Runs History
  useEffect(() => {
    loadHistory();
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, []);

  const loadHistory = async (selectFirst = false) => {
    try {
      const response = await fetch(`${API_BASE}/runs`);
      if (!response.ok) throw new Error("분석 이력을 로드하지 못했습니다.");
      const data = await response.json();
      setHistory(data);
      
      if (selectFirst && data.length > 0) {
        selectRun(data[0].id, data);
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  // 2. Select and Load details of a specific simulation run
  const selectRun = async (runId: string, customHistory?: RunResponse[]) => {
    // Close existing SSE stream connection if any
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }

    const runsList = customHistory || history;
    const run = runsList.find((r) => r.id === runId);
    if (!run) return;

    setActiveRun(run);
    
    // Parse current logs from JSON string
    try {
      const parsedLogs = JSON.parse(run.logs || "[]");
      setActiveLogs(parsedLogs);
    } catch (e) {
      setActiveLogs([]);
    }

    // Trigger market price loading for the selected ticker and trade date
    loadMarketData(run.ticker, run.trade_date);

    // If selected run is still RUNNING or PENDING, hook up to the SSE live stream!
    if (run.status === "RUNNING" || run.status === "PENDING") {
      setIsLoading(true);
      connectSSE(run.id, run.ticker, run.trade_date);
    } else {
      setIsLoading(false);
    }
  };

  // 3. Load Market Historical Price & Indicators from API
  const loadMarketData = async (ticker: string, tradeDate: string) => {
    setMarketLoading(true);
    setMarketError(null);
    try {
      // Lookback 180 days from target trade_date to draw charts
      const response = await fetch(
        `${API_BASE}/market/${ticker}?end_date=${tradeDate}&lookback_days=180`
      );
      if (!response.ok) {
        throw new Error(`${ticker} 종목의 차트 데이터를 수집하지 못했습니다.`);
      }
      const data = await response.json();
      setMarketData(data.data);
      setMarketIndicators(data.indicators);
    } catch (e: any) {
      setMarketError(e.message);
      setMarketData([]);
      setMarketIndicators(null);
    } finally {
      setMarketLoading(false);
    }
  };

  // 4. Establish SSE EventSource stream connection
  const connectSSE = (runId: string, _ticker: string, _tradeDate: string) => {
    if (sseRef.current) sseRef.current.close();

    const eventSource = new EventSource(`${API_BASE}/runs/${runId}/stream`);
    sseRef.current = eventSource;

    eventSource.addEventListener("progress", (event: any) => {
      try {
        const data = JSON.parse(event.data);
        if (data.run_id !== runId) return;

        setActiveRun((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            status: "RUNNING",
            current_step: data.current_step,
            progress: data.progress,
          };
        });

        setActiveLogs((prev) => {
          const exists = prev.some(
            (l) => l.step === data.log.step && l.message === data.log.message
          );
          if (exists) return prev;
          return [...prev, data.log];
        });
      } catch (e) {
        console.error("Error parsing progress SSE event:", e);
      }
    });

    eventSource.addEventListener("completed", (event: any) => {
      try {
        const data = JSON.parse(event.data);
        if (data.run_id !== runId) return;

        setActiveRun((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            status: "COMPLETED",
            current_step: "분석 완료",
            progress: 100.0,
            decision: data.decision,
            recommendation: data.recommendation,
            result: JSON.stringify(data.result),
          };
        });

        setActiveLogs((prev) => {
          const exists = prev.some((l) => l.step === data.log.step);
          if (exists) return prev;
          return [...prev, data.log];
        });

        setIsLoading(false);
        eventSource.close();
        loadHistory(); // Refresh history
      } catch (e) {
        console.error("Error parsing completed SSE event:", e);
      }
    });

    eventSource.addEventListener("failed", (event: any) => {
      try {
        const data = JSON.parse(event.data);
        if (data.run_id !== runId) return;

        setActiveRun((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            status: "FAILED",
            current_step: "오류 발생",
            progress: data.progress,
          };
        });

        setActiveLogs((prev) => [...prev, data.log]);
        setIsLoading(false);
        eventSource.close();
        loadHistory(); // Refresh history
      } catch (e) {
        console.error("Error parsing failed SSE event:", e);
      }
    });

    eventSource.onerror = (err) => {
      console.error("SSE connection error:", err);
      // Fail gracefully and keep polling or loading history
    };
  };

  // 5. Cancel or Delete a simulation run from sidebar or timeline
  const handleDeleteRun = async (runId: string) => {
    const run = history.find((r) => r.id === runId);
    if (!run) return;

    const confirmMsg = (run.status === "RUNNING" || run.status === "PENDING")
      ? `[경고] ${run.ticker} 분석 시뮬레이션 작업을 정말 취소하시겠습니까?\n취소 시 현재 단계에서 분석을 긴급 중단합니다.`
      : `${run.ticker} (${run.trade_date}) 분석 실행 기록을 정말 삭제하시겠습니까?`;
      
    if (!window.confirm(confirmMsg)) return;

    try {
      const response = await fetch(`${API_BASE}/runs/${runId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("작업 처리(삭제/취소)에 실패했습니다.");
      }

      // Close SSE socket if active selected run was deleted or cancelled
      if (activeRun?.id === runId) {
        if (sseRef.current) {
          sseRef.current.close();
          sseRef.current = null;
        }
        setActiveRun(null);
        setActiveLogs([]);
        setMarketData([]);
        setMarketIndicators(null);
        setIsLoading(false);
      }

      // Reload list
      loadHistory();
    } catch (e: any) {
      alert(`오류 발생: ${e.message}`);
    }
  };

  // 6. Submit Action: Request a new multi-agent simulation run
  const handleStartSimulation = async (params: {
    ticker: string;
    date: string;
    provider: string;
    model: string;
    debateRounds: number;
  }) => {
    setIsLoading(true);
    setMarketError(null);
    try {
      const response = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: params.ticker,
          trade_date: params.date,
          llm_provider: params.provider,
          llm_model: params.model,
          max_debate_rounds: params.debateRounds,
          max_risk_discuss_rounds: 1,
        }),
      });

      if (!response.ok) {
        throw new Error("분석을 생성하는 데 실패했습니다.");
      }

      const run = await response.json();
      
      // Update UI with pending run
      setHistory((prev) => [run, ...prev]);
      setActiveRun(run);
      setActiveLogs([]);
      loadMarketData(run.ticker, run.trade_date);

      // Connect to SSE stream
      connectSSE(run.id, run.ticker, run.trade_date);
    } catch (e: any) {
      alert(`오류 발생: ${e.message}`);
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", backgroundColor: "var(--bg-main)" }}>
      {/* Dynamic Bloomberg Theme Header */}
      <header
        style={{
          height: "60px",
          backgroundColor: "var(--bg-panel)",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0 20px",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Cpu size={24} color="var(--accent-blue)" className="pulse-animation" />
          <h1 style={{ fontSize: "18px", margin: 0, fontWeight: "800", color: "var(--text-primary)" }}>
            TradingAgents Platform <span style={{ color: "var(--accent-blue)", fontSize: "12px", fontWeight: "normal" }}>v0.2.5 Enterprise</span>
          </h1>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {isLoading && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--accent-blue)" }}>
              <span className="pulse-animation" style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "var(--accent-blue)", display: "inline-block" }} />
              에이전트 군집 추론 활성화 중...
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary)" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--accent-bull)", display: "inline-block" }} />
            로컬 LLM 서버 연결: 정상
          </div>
        </div>
      </header>

      {/* Main Grid Body Area */}
      <div className="dashboard-grid">
        {/* Left Column: Form & History List */}
        <RunForm
          onSubmit={handleStartSimulation}
          isLoading={isLoading}
          history={history}
          activeRunId={activeRun?.id || null}
          onSelectRun={(id) => selectRun(id)}
          onDeleteRun={handleDeleteRun}
        />

        {/* Right Column: Chart & dynamic progress timeline or reports */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "hidden", flex: 1 }}>
          {/* Top Panel: Chart view (always visible unless reports is expanded) */}
          {expandedSection !== "reports" && (
            marketLoading ? (
              <div className="panel" style={{ flex: 1, minHeight: "380px", justifyContent: "center", alignItems: "center" }}>
                <span className="pulse-animation" style={{ width: "16px", height: "16px", borderRadius: "50%", backgroundColor: "var(--accent-blue)", display: "inline-block", marginBottom: "8px" }} />
                <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>yfinance 시장 데이터를 분석하여 캔들스틱 및 보조지표를 계산하는 중...</p>
              </div>
            ) : marketError ? (
              <div className="panel" style={{ flex: 1, minHeight: "380px", justifyContent: "center", alignItems: "center" }}>
                <ShieldAlert size={36} color="var(--accent-bear)" style={{ marginBottom: "8px" }} />
                <p style={{ color: "var(--accent-bear)", fontSize: "13px" }}>{marketError}</p>
              </div>
            ) : marketData.length > 0 ? (
              <ChartPanel
                ticker={activeRun?.ticker || "AAPL"}
                data={marketData}
                indicators={marketIndicators}
                tradeDate={activeRun?.trade_date}
                recommendation={activeRun?.recommendation}
                decisionText={activeRun?.decision}
                isExpanded={expandedSection === "chart"}
                onToggleExpand={() => setExpandedSection(expandedSection === "chart" ? null : "chart")}
              />
            ) : (
              <div className="panel" style={{ flex: 1, minHeight: "380px", justifyContent: "center", alignItems: "center" }}>
                <Activity size={36} color="var(--text-secondary)" style={{ marginBottom: "8px" }} />
                <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>왼쪽 패널에서 매매 분석을 실행하거나 완료된 시뮬레이션을 선택하세요.</p>
              </div>
            )
          )}

          {/* Bottom Panel: Dynamic content shifting between Timeline (during running) and Reports (completed) */}
          {expandedSection !== "chart" && (
            <div style={{ flex: 1.2, overflowY: "hidden", display: "flex", height: "100%" }}>
              {activeRun ? (
                activeRun.status === "RUNNING" || activeRun.status === "PENDING" ? (
                  <Timeline
                    currentStep={activeRun.current_step}
                    progress={activeRun.progress}
                    status={activeRun.status}
                    logs={activeLogs}
                    onCancel={() => handleDeleteRun(activeRun.id)}
                    marketIndicators={marketIndicators}
                    runResult={activeRun.result}
                    isExpanded={expandedSection === "reports"}
                    onToggleExpand={() => setExpandedSection(expandedSection === "reports" ? null : "reports")}
                  />
                ) : (
                  <ReportDetails
                    run={activeRun}
                    isExpanded={expandedSection === "reports"}
                    onToggleExpand={() => setExpandedSection(expandedSection === "reports" ? null : "reports")}
                  />
                )
              ) : (
                <div className="panel" style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
                  <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>선택된 에이전트 상세 보고서 및 끝장 토론 기록이 없습니다.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
