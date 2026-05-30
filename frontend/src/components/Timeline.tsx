import React, { useEffect, useRef } from "react";
import { Clock, Terminal, ShieldCheck, Maximize2, Minimize2 } from "lucide-react";

interface LogEntry {
  timestamp: string;
  step: string;
  message: string;
  progress: number;
}

interface TimelineProps {
  currentStep: string;
  progress: number;
  status: string;
  logs: LogEntry[];
  onCancel?: () => void;
  marketIndicators?: any;
  runResult?: string | null;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  currentStep,
  progress,
  status,
  logs,
  onCancel,
  marketIndicators,
  runResult,
  isExpanded = false,
  onToggleExpand,
}) => {
  const [activeSubTab, setActiveSubTab] = React.useState<"stream" | "intake">("stream");
  const parsedResult = React.useMemo(() => {
    if (!runResult) return null;
    try {
      return JSON.parse(runResult);
    } catch (e) {
      return null;
    }
  }, [runResult]);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  const steps = [
    "시뮬레이션 초기화",
    "시장 분석",
    "뉴스 분석",
    "기본적 재무 분석",
    "상승론 debate",
    "하락론 debate",
    "리서치 의견 종합",
    "트레이더 포지셔닝",
    "최종 매매 승인",
    "분석 완료"
  ];

  // Auto-scroll terminal to bottom when new logs arrive
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  const getStepStatus = (step: string) => {
    if (status === "FAILED" && currentStep === step) {
      return "failed";
    }
    if (status === "CANCELLED" && currentStep === step) {
      return "failed";
    }
    
    const currentIdx = steps.indexOf(currentStep);
    const stepIdx = steps.indexOf(step);

    if (stepIdx < 0 || currentIdx < 0) {
      return "pending";
    }

    if (status === "COMPLETED") {
      return "completed";
    }

    if (stepIdx < currentIdx) {
      return "completed";
    } else if (stepIdx === currentIdx) {
      return "active";
    } else {
      return "pending";
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) {
      return "";
    }
  };

  return (
    <div className="panel" style={{ flex: 1, height: isExpanded ? "calc(100vh - 100px)" : "auto", maxHeight: isExpanded ? "calc(100vh - 100px)" : "100%", display: "flex", flexDirection: "column" }}>
      {/* Panel Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Clock size={20} color="var(--accent-blue)" />
          <h2 style={{ fontSize: "16px", margin: 0 }}>실시간 에이전트 분석 진행 현황</h2>
        </div>
        
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          {/* Cancel Button */}
          {onCancel && (status === "RUNNING" || status === "PENDING") && (
            <button
              onClick={onCancel}
              style={{
                backgroundColor: "rgba(255, 62, 91, 0.15)",
                border: "1px solid var(--accent-bear)",
                color: "var(--accent-bear)",
                padding: "4px 10px",
                fontSize: "12px",
                borderRadius: "4px",
                fontWeight: "600",
                cursor: "pointer",
                transform: "none",
              }}
              className="cancel-btn"
            >
              시뮬레이션 취소
            </button>
          )}
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              className="tab-btn"
              style={{
                padding: "4px 10px",
                fontSize: "12px",
                background: "rgba(41, 98, 255, 0.15)",
                border: "1px solid var(--accent-blue)",
                color: "var(--accent-blue)",
                borderRadius: "4px",
                height: "auto",
                transform: "none",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontWeight: "bold",
                cursor: "pointer"
              }}
            >
              {isExpanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              {isExpanded ? "축소" : "확대"}
            </button>
          )}
        </div>
      </div>

      {/* Main Progress Bar */}
      <div style={{ marginBottom: "16px", flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px" }}>
          <span>전체 진행 상태: {currentStep}</span>
          <span style={{ fontWeight: "bold", color: "var(--text-primary)" }}>{Math.min(100, Math.max(0, progress)).toFixed(0)}%</span>
        </div>
        <div style={{ width: "100%", height: "6px", backgroundColor: "var(--border-color)", borderRadius: "3px", overflow: "hidden" }}>
          <div 
            style={{ 
              width: `${Math.min(100, Math.max(0, progress))}%`, 
              height: "100%", 
              backgroundColor: 
                status === "FAILED" ? "var(--accent-bear)" : 
                status === "CANCELLED" ? "var(--accent-hold)" : "var(--accent-blue)",
              transition: "width 0.4s ease-out" 
            }} 
          />
        </div>
      </div>

      {/* Double Column Grid: Checklist (Left) & Real-time Active Terminal (Right) */}
      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "16px", flex: 1, overflow: "hidden" }}>
        
        {/* Left Column: Sequential Step List */}
        <div style={{ overflowY: "auto", paddingRight: "4px", borderRight: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: "2px" }}>
          {steps.map((step) => {
            const stepStatus = getStepStatus(step);
            
            return (
              <div 
                key={step} 
                className={`timeline-item ${stepStatus}`}
                style={{ opacity: stepStatus === "pending" ? 0.4 : 1, paddingBottom: "16px" }}
              >
                <div 
                  className={`timeline-dot ${stepStatus === "active" ? "pulse-animation" : ""}`}
                  style={{
                    backgroundColor: 
                      stepStatus === "completed" ? "var(--accent-bull)" :
                      stepStatus === "failed" ? "var(--accent-bear)" :
                      stepStatus === "active" ? "var(--accent-blue)" : "var(--border-color)",
                  }}
                />
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span 
                    style={{ 
                      fontSize: "12.5px", 
                      fontWeight: stepStatus === "active" ? "bold" : "500",
                      color: stepStatus === "active" ? "var(--accent-blue)" : "var(--text-primary)"
                    }}
                  >
                    {step}
                  </span>
                  
                  {stepStatus === "active" && (
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: "1.3" }}>
                      진행 중...
                    </span>
                  )}
                  {stepStatus === "completed" && (
                    <span style={{ fontSize: "10px", color: "var(--accent-bull)", fontWeight: "600" }}>
                      ✓ 완료됨
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Active Quant Terminal Feed & Live Intake Monitor */}
        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Sub Tab Headers */}
          <div style={{ display: "flex", gap: "8px", marginBottom: "8px", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px", flexShrink: 0 }}>
            <button
              onClick={() => setActiveSubTab("stream")}
              style={{
                background: "none",
                border: "none",
                color: activeSubTab === "stream" ? "var(--accent-blue)" : "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: "bold",
                padding: "4px 8px",
                borderBottom: activeSubTab === "stream" ? "2px solid var(--accent-blue)" : "2px solid transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                transform: "none"
              }}
            >
              <Terminal size={13} />
              실시간 에이전트 스트림
            </button>
            <button
              onClick={() => setActiveSubTab("intake")}
              style={{
                background: "none",
                border: "none",
                color: activeSubTab === "intake" ? "var(--accent-blue)" : "var(--text-secondary)",
                fontSize: "12px",
                fontWeight: "bold",
                padding: "4px 8px",
                borderBottom: activeSubTab === "intake" ? "2px solid var(--accent-blue)" : "2px solid transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                transform: "none"
              }}
            >
              <Clock size={13} />
              수집 수치 & 뉴스 모니터 (Live Intake)
            </button>
          </div>

          {activeSubTab === "stream" ? (
            <div 
              className="terminal-block" 
              style={{ 
                flex: 1, 
                maxHeight: "100%", 
                backgroundColor: "#06080c", 
                border: "1px solid #1c2230", 
                borderRadius: "4px",
                padding: "10px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                overflowY: "auto"
              }}
            >
              {logs.length === 0 ? (
                <div style={{ color: "#566275", fontStyle: "italic", fontSize: "12px" }}>
                  &gt; 에이전트 소켓 스트림 대기 중... 초기화를 수신하는 즉시 터미널 피드가 갱신됩니다.
                </div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} style={{ display: "flex", gap: "8px", fontSize: "12.5px", fontFamily: "var(--font-mono)", alignItems: "flex-start", lineHeight: "1.4" }}>
                    <span style={{ color: "#566275", flexShrink: 0 }}>[{formatTime(log.timestamp)}]</span>
                    <span style={{ color: "var(--accent-blue)", fontWeight: "bold", flexShrink: 0 }}>[{log.step}]</span>
                    <span style={{ color: log.step === "오류 발생" ? "var(--accent-bear)" : log.step === "작업 취소됨" ? "var(--accent-hold)" : "#b2ffd6" }}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              
              {/* Auto-scroll anchor */}
              <div ref={terminalEndRef} />
            </div>
          ) : (
            // Live Intake Monitor View
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* 1. Technical Indicators Grid */}
              <div className="card" style={{ padding: "12px", borderLeft: "4px solid var(--accent-blue)", backgroundColor: "#111520" }}>
                <h3 style={{ margin: "0 0 10px 0", fontSize: "13px", color: "var(--accent-blue)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <Terminal size={14} />
                  수집된 시장 보조 지표 (Technical Price Metrics)
                </h3>
                
                {marketIndicators ? (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
                    <div style={{ backgroundColor: "#0b0d13", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color)" }}>
                      <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>RSI (14)</div>
                      <div style={{ fontSize: "16px", fontWeight: "bold", color: marketIndicators.RSI ? (marketIndicators.RSI[marketIndicators.RSI.length - 1] > 70 ? "var(--accent-bear)" : marketIndicators.RSI[marketIndicators.RSI.length - 1] < 30 ? "var(--accent-bull)" : "var(--text-primary)") : "var(--text-secondary)" }}>
                        {marketIndicators.RSI ? marketIndicators.RSI[marketIndicators.RSI.length - 1].toFixed(2) : "N/A"}
                      </div>
                      <span style={{ fontSize: "9px", color: "var(--text-secondary)" }}>
                        {marketIndicators.RSI ? (marketIndicators.RSI[marketIndicators.RSI.length - 1] > 70 ? "과매수 (Overbought)" : marketIndicators.RSI[marketIndicators.RSI.length - 1] < 30 ? "과매도 (Oversold)" : "중립 (Neutral)") : ""}
                      </span>
                    </div>

                    <div style={{ backgroundColor: "#0b0d13", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color)" }}>
                      <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>MACD Signal</div>
                      <div style={{ fontSize: "16px", fontWeight: "bold", color: "var(--text-primary)" }}>
                        {marketIndicators.MACD ? marketIndicators.MACD[marketIndicators.MACD.length - 1].toFixed(2) : "N/A"}
                      </div>
                      <span style={{ fontSize: "9px", color: "var(--text-secondary)" }}>
                        Hist: {marketIndicators.MACD_hist ? marketIndicators.MACD_hist[marketIndicators.MACD_hist.length - 1].toFixed(2) : "N/A"}
                      </span>
                    </div>

                    <div style={{ backgroundColor: "#0b0d13", padding: "8px", borderRadius: "4px", border: "1px solid var(--border-color)" }}>
                      <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>SMA (50/200)</div>
                      <div style={{ fontSize: "14px", fontWeight: "bold", color: "var(--text-primary)", whiteSpace: "nowrap" }}>
                        {marketIndicators.SMA_50 ? marketIndicators.SMA_50[marketIndicators.SMA_50.length - 1].toFixed(0) : "N/A"}
                      </div>
                      <span style={{ fontSize: "9px", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        SMA200: {marketIndicators.SMA_200 ? marketIndicators.SMA_200[marketIndicators.SMA_200.length - 1].toFixed(0) : "N/A"}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "#566275", fontStyle: "italic", fontSize: "11px" }}>
                    시장 분석가 에이전트가 주가 수치를 로드하는 중입니다...
                  </div>
                )}
              </div>

              {/* 2. Macro News Header intake 피드 */}
              <div className="card" style={{ padding: "12px", flex: 1, display: "flex", flexDirection: "column", borderLeft: "4px solid var(--accent-purple)", backgroundColor: "#111520", minHeight: "160px" }}>
                <h3 style={{ margin: "0 0 10px 0", fontSize: "13px", color: "var(--accent-purple)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <ShieldCheck size={14} />
                  수집된 실시간 매크로 뉴스 (Macro News Intake Monitor)
                </h3>
                
                <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
                  {logs.filter(l => l.step === "뉴스 분석" || l.message.includes("뉴스") || l.message.includes("헤드라인") || l.message.includes("언론")).length === 0 && !parsedResult?.news_report ? (
                    <div style={{ color: "#566275", fontStyle: "italic", fontSize: "11px", padding: "10px 0" }}>
                      &gt; 뉴스 리서처 에이전트가 거시 헤드라인 및 언론 미디어를 인테이크하는 즉시 수집 피드가 활성화됩니다.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {parsedResult?.news_report && (
                        <div style={{ padding: "6px 8px", backgroundColor: "#0b0d13", border: "1px solid var(--accent-purple)", borderRadius: "4px", fontSize: "11.5px", marginBottom: "6px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", color: "var(--accent-purple)", fontSize: "10px", marginBottom: "2px", fontWeight: "bold" }}>
                            <span>[최종 뉴스 요약 분석안]</span>
                          </div>
                          <div style={{ color: "#e1e4eb", lineHeight: "1.4" }}>
                            {parsedResult.news_report}
                          </div>
                        </div>
                      )}
                      
                      {logs
                        .filter(l => l.step === "뉴스 분석" || l.message.includes("뉴스") || l.message.includes("헤드라인") || l.message.includes("언론"))
                        .map((log, i) => (
                          <div key={i} style={{ padding: "6px 8px", backgroundColor: "#0b0d13", border: "1px solid #1c2230", borderRadius: "4px", fontSize: "11.5px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)", fontSize: "10px", marginBottom: "2px" }}>
                              <span style={{ color: "var(--accent-purple)" }}>[Intake: Web Media Feed]</span>
                              <span>{formatTime(log.timestamp)}</span>
                            </div>
                            <div style={{ color: "#e1e4eb", lineHeight: "1.4", fontFamily: "var(--font-mono)" }}>
                              {log.message.replace("뉴스 리서처가 ", "").replace("분석하는 중...", "")}
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
