import { useState, useEffect, useRef, useMemo } from "react";
import { Activity, ShieldAlert, Cpu, LayoutDashboard, LineChart, Settings, X, Newspaper, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { RunForm } from "./components/RunForm";
import { ChartPanel } from "./components/ChartPanel";
import { Timeline } from "./components/Timeline";
import { BacktestDashboard } from "./components/BacktestDashboard";

// API Base URL - Configured to point to FastAPI backend
const API_BASE = "http://localhost:8080/api";

interface LogEntry {
  timestamp: string;
  step: string;
  message: string;
  progress: number;
  type?: string;
  details?: any;
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

interface TradeSignal {
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  price_target?: number | null;
  current_price?: number | null;
}

// News data structure
interface NewsItem {
  time: string;
  title: string;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
  summary: string;
  url?: string;
}

// Regex-based simple markdown renderer for AI news interpretations
const renderInterpretationMarkdown = (text: string) => {
  if (!text) return null;
  const lines = text.split("\n");
  return lines.map((line, idx) => {
    let content: React.ReactNode = line;
    
    // Bold parsing (**text**)
    if (line.includes("**")) {
      const parts = line.split(/\*\*(.*?)\*\*/g);
      content = parts.map((part, pIdx) => pIdx % 2 === 1 ? <strong key={pIdx} style={{ color: "var(--accent-blue)", fontWeight: "bold" }}>{part}</strong> : part);
    }
    
    // Bullet list item
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      const cleanLine = line.trim().substring(2);
      let parsedClean: React.ReactNode = cleanLine;
      if (cleanLine.includes("**")) {
        const parts = cleanLine.split(/\*\*(.*?)\*\*/g);
        parsedClean = parts.map((part, pIdx) => pIdx % 2 === 1 ? <strong key={pIdx} style={{ color: "var(--accent-blue)", fontWeight: "bold" }}>{part}</strong> : part);
      }
      return (
        <div key={idx} style={{ display: "flex", gap: "6px", paddingLeft: "6px", margin: "3px 0", fontSize: "10.5px", color: "var(--text-primary)", alignItems: "flex-start", width: "100%", boxSizing: "border-box" }}>
          <span style={{ color: "var(--accent-blue)", marginTop: "1px", flexShrink: 0 }}>•</span>
          <span style={{ flex: 1, wordBreak: "break-all", whiteSpace: "normal", minWidth: 0 }}>{parsedClean}</span>
        </div>
      );
    }
    
    return (
      <p key={idx} style={{ margin: "3px 0 5px 0", fontSize: "10.5px", lineHeight: "1.4", color: "var(--text-primary)", wordBreak: "break-all", whiteSpace: "normal" }}>
        {content}
      </p>
    );
  });
};

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
  const [activeView, setActiveView] = useState<"simulation" | "backtest">("simulation");
  const [isLoading, setIsLoading] = useState(false);
  
  const sseRef = useRef<EventSource | null>(null);
  const [expandedSection, setExpandedSection] = useState<"chart" | "reports" | null>(null);

  // Global Settings Modal States with LocalStorage retention
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [llmProvider, setLlmProvider] = useState(() => localStorage.getItem("ta_llm_provider") || "local");
  const [llmModel, setLlmModel] = useState(() => localStorage.getItem("ta_llm_model") || "qwen3.6-27b-uncensored-heretic-v2-native-mtp-preserved");
  const [llmBaseUrl, setLlmBaseUrl] = useState(() => localStorage.getItem("ta_llm_base_url") || "http://localhost:8000/api/v1/chat");
  const [llmApiKey, setLlmApiKey] = useState("lm-studio");
  const [debateRounds, setDebateRounds] = useState(() => Number(localStorage.getItem("ta_debate_rounds") || "1"));
  const [riskRounds, setRiskRounds] = useState(() => Number(localStorage.getItem("ta_risk_rounds") || "1"));
  const [newsFeed, setNewsFeed] = useState<NewsItem[]>([]);
  
  // click accordion state
  const [expandedNewsIdx, setExpandedNewsIdx] = useState<number | null>(null);
  const [newsInterpretations, setNewsInterpretations] = useState<Record<number, string>>({});
  const [newsInterpretationLoading, setNewsInterpretationLoading] = useState<Record<number, boolean>>({});

  // handle interpret AI news impact
  const handleInterpretNews = async (idx: number, newsItem: NewsItem) => {
    if (newsInterpretationLoading[idx]) return;
    
    setNewsInterpretationLoading(prev => ({ ...prev, [idx]: true }));
    try {
      const response = await fetch(`${API_BASE}/news/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: activeTicker,
          news_title: newsItem.title,
          news_summary: newsItem.summary,
          provider: llmProvider,
          base_url: llmBaseUrl,
          api_key: llmApiKey,
          model_name: llmModel
        })
      });
      if (response.ok) {
        const data = await response.json();
        setNewsInterpretations(prev => ({ ...prev, [idx]: data.interpretation }));
      } else {
        setNewsInterpretations(prev => ({ ...prev, [idx]: "AI 해설을 가져오는 데 실패했습니다." }));
      }
    } catch (e) {
      setNewsInterpretations(prev => ({ ...prev, [idx]: "네트워크 오류가 발생했습니다." }));
    } finally {
      setNewsInterpretationLoading(prev => ({ ...prev, [idx]: false }));
    }
  };

  // Helper to render label with high-fidelity tooltip
  const renderTooltipLabel = (label: string, tooltipText: string) => {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "bold" }}>{label}</span>
        <div 
          className="tooltip-container"
          style={{ 
            position: "relative", 
            display: "inline-block", 
            cursor: "help", 
            color: "var(--accent-blue)",
            fontSize: "11px",
            lineHeight: "1"
          }}
        >
          ❓
          <div 
            className="tooltip-content"
            style={{
              visibility: "hidden",
              width: "210px",
              backgroundColor: "rgba(22, 26, 34, 0.98)",
              color: "var(--text-primary)",
              textAlign: "left",
              borderRadius: "6px",
              padding: "8px 10px",
              position: "absolute",
              zIndex: 99999,
              bottom: "130%",
              left: "50%",
              marginLeft: "-105px",
              opacity: 0,
              transition: "opacity 0.2s ease, visibility 0.2s ease",
              fontSize: "10.5px",
              lineHeight: "1.45",
              border: "1px solid var(--accent-blue)",
              boxShadow: "0 6px 20px rgba(0, 0, 0, 0.75)",
              backdropFilter: "blur(6px)",
              pointerEvents: "none",
              wordBreak: "break-word",
              whiteSpace: "normal"
            }}
          >
            {tooltipText}
          </div>
        </div>
      </div>
    );
  };

  // 1. Initial Load: Get Simulation Runs History
  useEffect(() => {
    loadHistory(true);
    loadNewsFeed("AAPL");
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
    loadNewsFeed(run.ticker);

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

  // Load News Feed from API
  const loadNewsFeed = async (ticker: string) => {
    try {
      const response = await fetch(`${API_BASE}/market/${ticker}/news`);
      if (response.ok) {
        const data = await response.json();
        setNewsFeed(data.news || []);
      } else {
        setNewsFeed([]);
      }
    } catch (e) {
      setNewsFeed([]);
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
          llm_provider: llmProvider,
          llm_model: llmModel,
          max_debate_rounds: debateRounds,
          max_risk_discuss_rounds: riskRounds,
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
      loadNewsFeed(run.ticker);

      // Connect to SSE stream
      connectSSE(run.id, run.ticker, run.trade_date);
    } catch (e: any) {
      alert(`오류 발생: ${e.message}`);
      setIsLoading(false);
    }
  };

  // Helper to fetch matching news list for current active ticker
  const activeTicker = activeRun?.ticker || "AAPL";
  const currentNewsFeed = newsFeed;
  const activeTradeSignal = useMemo<TradeSignal | null>(() => {
    if (!activeRun?.result) return null;
    try {
      const parsed = JSON.parse(activeRun.result) as { trade_signal?: TradeSignal };
      return parsed.trade_signal || null;
    } catch {
      return null;
    }
  }, [activeRun?.result]);

  const getSentimentIcon = (sentiment: string) => {
    if (sentiment === "BULLISH") return <TrendingUp size={12} color="#00c076" />;
    if (sentiment === "BEARISH") return <TrendingDown size={12} color="#ff3e5b" />;
    return <Minus size={12} color="#f3ba2f" />;
  };

  const getSentimentStyle = (sentiment: string) => {
    if (sentiment === "BULLISH") return { color: "#00c076", backgroundColor: "rgba(0, 192, 118, 0.08)", border: "1px solid rgba(0, 192, 118, 0.25)" };
    if (sentiment === "BEARISH") return { color: "#ff3e5b", backgroundColor: "rgba(255, 62, 91, 0.08)", border: "1px solid rgba(255, 62, 91, 0.25)" };
    return { color: "#f3ba2f", backgroundColor: "rgba(243, 186, 47, 0.08)", border: "1px solid rgba(243, 186, 47, 0.25)" };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", backgroundColor: "var(--bg-main)", overflow: "hidden" }}>
      {/* Tooltip Hover Styles Injection */}
      <style dangerouslySetInnerHTML={{__html: `
        .tooltip-container:hover .tooltip-content {
          visibility: visible !important;
          opacity: 1 !important;
        }
      `}} />
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
          boxShadow: "0 2px 10px rgba(0, 0, 0, 0.4)"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Cpu size={24} color="var(--accent-blue)" className="pulse-animation" />
          <h1 style={{ fontSize: "18px", margin: 0, fontWeight: "800", color: "var(--text-primary)" }}>
            TradingAgents Platform <span style={{ color: "var(--accent-blue)", fontSize: "12px", fontWeight: "normal" }}>v0.2.5 Enterprise</span>
          </h1>
        </div>

        {/* View Switcher Tabs & Settings Gear */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={() => setActiveView("simulation")}
              className="tab-btn"
              style={{
                padding: "6px 14px",
                fontSize: "13px",
                background: activeView === "simulation" ? "rgba(41, 98, 255, 0.15)" : "none",
                border: "1px solid " + (activeView === "simulation" ? "var(--accent-blue)" : "var(--border-color)"),
                color: activeView === "simulation" ? "var(--text-primary)" : "var(--text-secondary)",
                borderRadius: "4px",
                height: "auto",
                transform: "none",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontWeight: "bold",
                cursor: "pointer"
              }}
            >
              <LayoutDashboard size={14} />
              실시간 에이전트 분석
            </button>
            <button
              onClick={() => setActiveView("backtest")}
              className="tab-btn"
              style={{
                padding: "6px 14px",
                fontSize: "13px",
                background: activeView === "backtest" ? "rgba(41, 98, 255, 0.15)" : "none",
                border: "1px solid " + (activeView === "backtest" ? "var(--accent-blue)" : "var(--border-color)"),
                color: activeView === "backtest" ? "var(--text-primary)" : "var(--text-secondary)",
                borderRadius: "4px",
                height: "auto",
                transform: "none",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontWeight: "bold",
                cursor: "pointer"
              }}
            >
              <LineChart size={14} />
              포트폴리오 백테스트 & 성과
            </button>
          </div>

          {/* Settings Modular Gear Icon */}
          <button
            onClick={() => setShowSettingsModal(true)}
            style={{
              background: "none",
              border: "1px solid var(--border-color)",
              color: "var(--text-secondary)",
              padding: "6px",
              borderRadius: "4px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s ease"
            }}
            title="글로벌 엔진 환경 설정"
            className="settings-gear-btn"
          >
            <Settings size={18} />
          </button>
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
      {activeView === "simulation" ? (
        <div className="dashboard-grid">
          {/* Left Column: Form & History List (15~20% - Scrollable inside) */}
          <div style={{ height: "100%", overflowY: "auto" }}>
            <RunForm
              onSubmit={handleStartSimulation}
              isLoading={isLoading}
              history={history}
              activeRunId={activeRun?.id || null}
              onSelectRun={(id) => selectRun(id)}
              onDeleteRun={handleDeleteRun}
            />
          </div>

          {/* Center Column: Chart & dynamic progress timeline (60~65% - Main Workspace) */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", height: "100%", overflowY: "hidden", flex: 1 }}>
            {/* Top Panel: Chart view (always visible unless reports is expanded) */}
            {expandedSection !== "reports" && (
              marketLoading ? (
                <div className="panel" style={{ flex: 1, minHeight: "340px", justifyContent: "center", alignItems: "center" }}>
                  <span className="pulse-animation" style={{ width: "16px", height: "16px", borderRadius: "50%", backgroundColor: "var(--accent-blue)", display: "inline-block", marginBottom: "8px" }} />
                  <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>yfinance 시장 데이터를 분석하여 캔들스틱 및 보조지표를 계산하는 중...</p>
                </div>
              ) : marketError ? (
                <div className="panel" style={{ flex: 1, minHeight: "340px", justifyContent: "center", alignItems: "center" }}>
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
                  tradeSignal={activeTradeSignal}
                  isExpanded={expandedSection === "chart"}
                  onToggleExpand={() => setExpandedSection(expandedSection === "chart" ? null : "chart")}
                />
              ) : (
                <div className="panel" style={{ flex: 1, minHeight: "340px", justifyContent: "center", alignItems: "center" }}>
                  <Activity size={36} color="var(--text-secondary)" style={{ marginBottom: "8px" }} />
                  <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>왼쪽 패널에서 매매 분석을 실행하거나 완료된 시뮬레이션을 선택하세요.</p>
                </div>
              )
            )}

            {/* Bottom Panel: Unified Agent Workspace displaying Pipeline Flowchart & Details Panel */}
            {expandedSection !== "chart" && (
              <div style={{ flex: 1.2, overflowY: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
                {activeRun ? (
                  <Timeline
                    currentStep={activeRun.current_step}
                    progress={activeRun.progress}
                    status={activeRun.status}
                    logs={activeLogs}
                    onCancel={(activeRun.status === "RUNNING" || activeRun.status === "PENDING") ? () => handleDeleteRun(activeRun.id) : undefined}
                    marketIndicators={marketIndicators}
                    runResult={activeRun.result}
                    isExpanded={expandedSection === "reports"}
                    onToggleExpand={() => setExpandedSection(expandedSection === "reports" ? null : "reports")}
                  />
                ) : (
                  <div className="panel" style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
                    <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>선택된 에이전트 상세 보고서 및 끝장 토론 기록이 없습니다.</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Live News & Macro Feed (15~20% - Scrollable inside) */}
          <div className="panel" style={{ width: "100%", maxWidth: "260px", boxSizing: "border-box", height: "100%", overflowY: "auto", overflowX: "hidden", display: "flex", flexDirection: "column", gap: "10px", padding: "12px" }}>
            <h2 style={{ fontSize: "13px", fontWeight: "800", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "6px", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px", flexShrink: 0, margin: 0 }}>
              <Newspaper size={14} color="var(--accent-blue)" />
              실시간 뉴스 & 시황 피드
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", width: "100%", boxSizing: "border-box" }}>
              {currentNewsFeed.length === 0 ? (
                <p style={{ fontSize: "11px", color: "var(--text-secondary)", fontStyle: "italic", textAlign: "center", margin: "20px 0" }}>
                  가용한 최신 뉴스가 없습니다.
                </p>
              ) : (
                currentNewsFeed.map((news, idx) => {
                  const isExpanded = expandedNewsIdx === idx;
                  const interpretation = newsInterpretations[idx];
                  const isInterpreting = newsInterpretationLoading[idx];

                  return (
                    <div
                      key={idx}
                      onClick={() => setExpandedNewsIdx(isExpanded ? null : idx)}
                      style={{
                        backgroundColor: isExpanded ? "rgba(30, 34, 45, 0.9)" : "#1e222d",
                        border: isExpanded ? "1px solid var(--accent-blue)" : "1px solid var(--border-color)",
                        borderRadius: "6px",
                        padding: "10px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        cursor: "pointer",
                        transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                        boxShadow: isExpanded ? "0 0 8px rgba(41, 98, 255, 0.15)" : "none",
                        width: "100%",
                        boxSizing: "border-box",
                        overflowX: "hidden"
                      }}
                      className="news-card"
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", boxSizing: "border-box" }}>
                        <span style={{ fontSize: "10px", color: "var(--text-secondary)", fontWeight: "500" }}>{news.time}</span>
                        <span
                          style={{
                            fontSize: "8px",
                            fontWeight: "800",
                            padding: "1px 5px",
                            borderRadius: "3px",
                            display: "flex",
                            alignItems: "center",
                            gap: "3px",
                            ...getSentimentStyle(news.sentiment)
                          }}
                        >
                          {getSentimentIcon(news.sentiment)}
                          {news.sentiment}
                        </span>
                      </div>
                      <h4 style={{ 
                        fontSize: "11.5px", 
                        fontWeight: "bold", 
                        margin: 0, 
                        color: isExpanded ? "var(--accent-blue)" : "var(--text-primary)", 
                        lineHeight: "1.35",
                        wordBreak: "break-all",
                        whiteSpace: "normal"
                      }}>
                        {news.title}
                      </h4>

                      {/* Accordion Expanded Details */}
                      {isExpanded ? (
                        <div 
                          onClick={(e) => e.stopPropagation()} // Prevent collapse when clicking details
                          style={{ display: "flex", flexDirection: "column", gap: "8px", borderTop: "1px dashed var(--border-color)", paddingTop: "8px", marginTop: "4px", width: "100%", boxSizing: "border-box" }}
                        >
                          <p style={{ 
                            fontSize: "10.5px", 
                            color: "var(--text-primary)", 
                            margin: 0, 
                            lineHeight: "1.4",
                            wordBreak: "break-all",
                            whiteSpace: "normal"
                          }}>
                            {news.summary || "기사 요약이 제공되지 않았습니다."}
                          </p>

                          {/* Interactive Row */}
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", alignItems: "center", marginTop: "4px", width: "100%", boxSizing: "border-box" }}>
                            {news.url && (
                              <a
                                href={news.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                  fontSize: "9.5px",
                                  color: "var(--accent-blue)",
                                  backgroundColor: "rgba(41, 98, 255, 0.12)",
                                  border: "1px solid rgba(41, 98, 255, 0.3)",
                                  padding: "2px 6px",
                                  borderRadius: "3px",
                                  textDecoration: "none",
                                  fontWeight: "bold",
                                  maxWidth: "100%",
                                  boxSizing: "border-box",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis"
                                }}
                                className="card-hover-effect"
                              >
                                🔗 원문 기사 보기
                              </a>
                            )}
                            {news.title !== "실시간 뉴스를 불러올 수 없습니다" && (
                              <button
                                onClick={() => handleInterpretNews(idx, news)}
                                disabled={isInterpreting}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                  fontSize: "9.5px",
                                  color: "#00e676",
                                  backgroundColor: "rgba(0, 230, 118, 0.12)",
                                  border: "1px solid rgba(0, 230, 118, 0.3)",
                                  padding: "2px 6px",
                                  borderRadius: "3px",
                                  cursor: isInterpreting ? "not-allowed" : "pointer",
                                  fontWeight: "bold",
                                  maxWidth: "100%",
                                  boxSizing: "border-box",
                                  whiteSpace: "nowrap",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis"
                                }}
                                className="card-hover-effect"
                              >
                                {isInterpreting ? "🤖 해설 요청 중..." : "🤖 AI 해설 요청"}
                              </button>
                            )}
                          </div>

                          {/* AI Interpretation Display */}
                          {(interpretation || isInterpreting) && (
                            <div style={{ 
                              backgroundColor: "rgba(41, 98, 255, 0.04)", 
                              border: "1px dashed rgba(41, 98, 255, 0.25)", 
                              borderRadius: "4px", 
                              padding: "8px", 
                              marginTop: "4px",
                              display: "flex",
                              flexDirection: "column",
                              gap: "4px",
                              width: "100%",
                              boxSizing: "border-box"
                            }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "9.5px", color: "var(--accent-blue)", fontWeight: "bold", borderBottom: "1px solid rgba(41, 98, 255, 0.15)", paddingBottom: "2px", marginBottom: "4px" }}>
                                <span>🤖 AI 시장 영향 분석</span>
                              </div>
                              {isInterpreting ? (
                                <div style={{ display: "flex", gap: "6px", alignItems: "center", fontSize: "10px", color: "var(--text-secondary)", fontStyle: "italic" }}>
                                  <span className="pulse-text">LLM이 시장 파급 효과 분석서를 집필하는 중...</span>
                                </div>
                              ) : (
                                <div style={{ fontSize: "10.5px", width: "100%", boxSizing: "border-box" }}>
                                  {renderInterpretationMarkdown(interpretation)}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ) : (
                        <p style={{ 
                          fontSize: "10.5px", 
                          color: "var(--text-secondary)", 
                          margin: 0, 
                          lineHeight: "1.4",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          wordBreak: "break-word",
                          whiteSpace: "normal"
                        }}>
                          {news.summary || "기사 요약이 제공되지 않았습니다."}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, padding: "16px", overflowY: "hidden", display: "flex", flexDirection: "column", height: "calc(100vh - 60px)" }}>
          <BacktestDashboard apiBase={API_BASE} />
        </div>
      )}

      {/* Global Settings Modal Overlay */}
      {showSettingsModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(8px)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 9999,
          }}
        >
          <div
            className="panel animate-fade-in"
            style={{
              width: "460px",
              padding: "20px",
              backgroundColor: "var(--bg-panel)",
              border: "1px solid var(--border-color)",
              borderRadius: "8px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              boxShadow: "0 10px 40px rgba(0, 0, 0, 0.6)"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Settings size={18} color="var(--accent-blue)" />
                <h3 style={{ fontSize: "15px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>글로벌 멀티 에이전트 엔진 설정</h3>
              </div>
              <button
                onClick={() => setShowSettingsModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-secondary)",
                  padding: "4px",
                  display: "flex"
                }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                {renderTooltipLabel("LLM Provider (제공자)", "OpenAI, Anthropic, 또는 LMStudio/Ollama 같은 로컬 환경을 선택합니다.")}
                <select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                  style={{ width: "100%", padding: "8px", fontSize: "13px", backgroundColor: "#0b0e11" }}
                >
                  <option value="local">Local LLM Engine (로컬 허브)</option>
                  <option value="openai">OpenAI GPT-4o / 3.5</option>
                  <option value="anthropic">Anthropic Claude 3.5 Sonnet</option>
                  <option value="google">Google Gemini 1.5 Pro</option>
                </select>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                {renderTooltipLabel("API Base URL (엔드포인트 주소)", "LLM 서버의 주소입니다. (예: 로컬 LMStudio의 경우 http://localhost:1234/v1 입력 )")}
                <input
                  type="text"
                  value={llmBaseUrl}
                  onChange={(e) => setLlmBaseUrl(e.target.value)}
                  placeholder="예: http://localhost:8000/api/v1/chat"
                  style={{ width: "100%", padding: "8px", fontSize: "12.5px", backgroundColor: "#0b0e11", boxSizing: "border-box" }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                {renderTooltipLabel("API Key (인증 키)", "클라우드 API 사용 시 발급받은 키를 입력합니다. 로컬 환경이면 'lm-studio' 등을 입력하거나 비워둡니다.")}
                <input
                  type="password"
                  value={llmApiKey}
                  onChange={(e) => setLlmApiKey(e.target.value)}
                  placeholder="로컬 환경인 경우 lm-studio 입력 가능"
                  style={{ width: "100%", padding: "8px", fontSize: "12.5px", backgroundColor: "#0b0e11", boxSizing: "border-box" }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                {renderTooltipLabel("LLM 모델 명칭 (Model Name)", "사용할 정확한 모델 ID를 입력합니다. (예: gpt-4o, qwen3.6-27b 등)")}
                <input
                  type="text"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  placeholder="예: qwen3.6-27b-uncensored"
                  style={{ width: "100%", padding: "8px", fontSize: "12.5px", backgroundColor: "#0b0e11", boxSizing: "border-box" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {renderTooltipLabel("토론 진행 횟수 (Debate)", "상승론자와 하락론자가 의견을 교환하는 횟수입니다. 높을수록 심도 있는 분석이 가능하지만 시간이 오래 걸립니다.")}
                  <select
                    value={debateRounds}
                    onChange={(e) => setDebateRounds(Number(e.target.value))}
                    style={{ width: "100%", padding: "8px", fontSize: "13px", backgroundColor: "#0b0e11" }}
                  >
                    <option value={1}>1 Round (빠른 분석)</option>
                    <option value={2}>2 Rounds (균형 분석)</option>
                    <option value={3}>3 Rounds (끝장 토론)</option>
                  </select>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {renderTooltipLabel("리스크 필터 검토 횟수", "최종 매매 결정 전, 리스크 관리자가 포트폴리오 안정성을 재검토하는 횟수입니다.")}
                  <select
                    value={riskRounds}
                    onChange={(e) => setRiskRounds(Number(e.target.value))}
                    style={{ width: "100%", padding: "8px", fontSize: "13px", backgroundColor: "#0b0e11" }}
                  >
                    <option value={1}>1 Round (일반 필터)</option>
                    <option value={2}>2 Rounds (이중 안정 장치)</option>
                  </select>
                </div>
              </div>

              <div style={{ fontSize: "11px", color: "var(--accent-blue)", backgroundColor: "rgba(41, 98, 255, 0.08)", padding: "8px 12px", borderRadius: "4px", lineHeight: "1.45" }}>
                💡 <strong>알림:</strong> 설정된 모델 매개변수는 신규 실행되는 모든 백테스트 및 개별 시뮬레이션 군집 추론 연산에 전역 적용됩니다.
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "4px" }}>
              <button
                onClick={() => setShowSettingsModal(false)}
                style={{
                  backgroundColor: "transparent",
                  border: "1px solid var(--border-color)",
                  color: "var(--text-secondary)",
                  padding: "8px 16px",
                  fontSize: "12.5px"
                }}
              >
                닫기
              </button>
              <button
                onClick={() => {
                  localStorage.setItem("ta_llm_provider", llmProvider);
                  localStorage.setItem("ta_llm_model", llmModel);
                  localStorage.setItem("ta_llm_base_url", llmBaseUrl);
                  localStorage.removeItem("ta_llm_api_key");
                  localStorage.setItem("ta_debate_rounds", String(debateRounds));
                  localStorage.setItem("ta_risk_rounds", String(riskRounds));
                  setShowSettingsModal(false);
                }}
                style={{
                  backgroundColor: "var(--accent-blue)",
                  color: "white",
                  padding: "8px 16px",
                  fontSize: "12.5px"
                }}
              >
                설정 저장 및 적용
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
