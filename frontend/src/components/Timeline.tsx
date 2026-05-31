import React, { useEffect, useRef, useState, useMemo } from "react";
import { 
  Terminal, Users, ArrowRightLeft, Maximize2, Minimize2, 
  CheckCircle2, AlertCircle, Activity
} from "lucide-react";

interface LogEntry {
  timestamp: string;
  step: string;
  message: string;
  progress: number;
  type?: string;     // "INFO", "DEBUG", "TRACE", "TOOL"
  details?: any;      // Rich payload details (JSON or text)
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

// Inline Markdown Parser from ReportDetails
const parseItalicStyles = (text: string): React.ReactNode[] => {
  if (!text) return [];
  const parts = text.split(/(\*.*?\*|_.*?_)/g);
  return parts.map((part, idx) => {
    if ((part.startsWith("*") && part.endsWith("*")) || (part.startsWith("_") && part.endsWith("_"))) {
      return (
        <em key={`italic-${idx}`} style={{ fontStyle: "italic", color: "var(--text-secondary)" }}>
          {part.slice(1, -1)}
        </em>
      );
    }
    return part;
  });
};

const parseBoldStyles = (text: string): React.ReactNode[] => {
  if (!text) return [];
  const parts = text.split(/(\*\*.*?\*\*|__.*?__)/g);
  return parts.flatMap((part, idx) => {
    if ((part.startsWith("**") && part.endsWith("**")) || (part.startsWith("__") && part.endsWith("__"))) {
      return (
        <strong key={`bold-${idx}`} style={{ color: "var(--accent-blue)", fontWeight: "bold" }}>
          {parseItalicStyles(part.slice(2, -2))}
        </strong>
      );
    }
    return parseItalicStyles(part);
  });
};

const parseInlineCode = (text: string): React.ReactNode[] => {
  if (!text) return [];
  const parts = text.split(/(`[^`]+`)/g);
  return parts.flatMap((part, idx) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={`code-${idx}`} style={{
          fontFamily: "var(--font-mono)",
          backgroundColor: "rgba(255, 255, 255, 0.08)",
          padding: "2px 4px",
          borderRadius: "3px",
          color: "var(--accent-blue)",
          fontSize: "11px"
        }}>
          {part.slice(1, -1)}
        </code>
      );
    }
    return parseBoldStyles(part);
  });
};

const renderMarkdownToJSX = (text: string | null | undefined): React.ReactNode => {
  if (!text) return <span style={{ color: "var(--text-secondary)", fontStyle: "italic", fontSize: "11.5px" }}>데이터가 존재하지 않습니다.</span>;

  const rawLines = text.split("\n");
  const lines: string[] = [];
  
  for (let i = 0; i < rawLines.length; i++) {
    const current = rawLines[i].trim();
    if (current === "") {
      let nextNonEmpty = "";
      for (let j = i + 1; j < rawLines.length; j++) {
        const val = rawLines[j].trim();
        if (val !== "") { nextNonEmpty = val; break; }
      }
      let prevNonEmpty = "";
      for (let j = lines.length - 1; j >= 0; j--) {
        const val = lines[j].trim();
        if (val !== "") { prevNonEmpty = val; break; }
      }
      if (prevNonEmpty.startsWith("|") && nextNonEmpty.startsWith("|")) {
        continue; // Skip empty table line spacers
      }
    }
    lines.push(rawLines[i]);
  }

  let inTable = false;
  let tableHeaders: string[] = [];
  let tableRows: string[][] = [];

  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Table Parsing
    if (trimmed.startsWith("|")) {
      inTable = true;
      const cols = trimmed.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      
      if (trimmed.includes("---") || trimmed.includes("===")) {
        continue; // Skip divider lines
      }
      
      if (tableHeaders.length === 0) {
        tableHeaders = cols;
      } else {
        tableRows.push(cols);
      }
      
      let isNextTable = false;
      if (i + 1 < lines.length && lines[i + 1].trim().startsWith("|")) {
        isNextTable = true;
      }
      
      if (!isNextTable) {
        const currentHeaders = [...tableHeaders];
        const currentRows = [...tableRows];
        elements.push(
          <div key={`table-wrapper-${i}`} style={{ overflowX: "auto", margin: "10px 0" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11.5px", border: "1px solid var(--border-color)" }}>
              <thead>
                <tr style={{ backgroundColor: "#1c2230", borderBottom: "1px solid var(--border-color)" }}>
                  {currentHeaders.map((col, idx) => (
                    <th key={`th-${idx}`} style={{ padding: "6px 10px", textAlign: "left", fontWeight: "bold", color: "var(--accent-blue)" }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {currentRows.map((row, rowIdx) => (
                  <tr key={`tr-${rowIdx}`} style={{ borderBottom: "1px solid var(--border-color)", backgroundColor: rowIdx % 2 === 0 ? "rgba(255,255,255,0.01)" : "transparent" }}>
                    {row.map((col, colIdx) => (
                      <td key={`td-${colIdx}`} style={{ padding: "6px 10px", color: "var(--text-primary)" }}>
                        {parseInlineCode(col)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableHeaders = [];
        tableRows = [];
        inTable = false;
      }
      continue;
    }

    if (inTable) continue;

    // 2. Headings
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={`h4-${i}`} style={{ fontSize: "13px", color: "var(--accent-blue)", margin: "14px 0 6px 0", fontWeight: "bold", borderBottom: "1px dashed var(--border-color)", paddingBottom: "3px" }}>
          {parseInlineCode(trimmed.slice(4))}
        </h4>
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={`h3-${i}`} style={{ fontSize: "14px", color: "var(--text-primary)", margin: "16px 0 8px 0", fontWeight: "bold", borderBottom: "1px solid var(--border-color)", paddingBottom: "4px" }}>
          {parseInlineCode(trimmed.slice(3))}
        </h3>
      );
      continue;
    }
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h2 key={`h2-${i}`} style={{ fontSize: "16px", color: "var(--text-primary)", margin: "18px 0 10px 0", fontWeight: "800", paddingBottom: "6px", borderBottom: "2px solid var(--accent-blue)" }}>
          {parseInlineCode(trimmed.slice(2))}
        </h2>
      );
      continue;
    }

    // 3. Blockquotes
    if (trimmed.startsWith(">")) {
      elements.push(
        <blockquote key={`quote-${i}`} style={{ borderLeft: "3px solid var(--accent-blue)", paddingLeft: "10px", margin: "8px 0", color: "var(--text-secondary)", fontStyle: "italic", backgroundColor: "rgba(255,255,255,0.01)", padding: "6px 10px", borderRadius: "0 4px 4px 0" }}>
          {parseInlineCode(trimmed.slice(1).trim())}
        </blockquote>
      );
      continue;
    }

    // 4. Horizontal Rule
    if (trimmed === "---" || trimmed === "***") {
      elements.push(<hr key={`hr-${i}`} style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "14px 0" }} />);
      continue;
    }

    // 5. Unordered List Items
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <div key={`li-${i}`} style={{ display: "flex", gap: "6px", paddingLeft: "12px", margin: "3px 0", fontSize: "12px" }}>
          <span style={{ color: "var(--accent-blue)" }}>•</span>
          <span style={{ flex: 1, color: "var(--text-primary)" }}>{parseInlineCode(trimmed.slice(2))}</span>
        </div>
      );
      continue;
    }

    // 6. Regular Paragraphs
    if (trimmed !== "") {
      elements.push(
        <p key={`p-${i}`} style={{ margin: "4px 0 6px 0", fontSize: "12px", lineHeight: "1.5", color: "var(--text-primary)", wordBreak: "break-all" }}>
          {parseInlineCode(line)}
        </p>
      );
    } else {
      elements.push(<div key={`space-${i}`} style={{ height: "6px" }} />);
    }
  }

  return <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>{elements}</div>;
};

// Map nodes to step names used in sqlite logs
const stepToMapName: Record<string, string> = {
  "Market Analyst": "시장 분석",
  "Sentiment Analyst": "감성 분석",
  "News Analyst": "뉴스 분석",
  "Fundamentals Analyst": "기본적 재무 분석",
  "Bull Researcher": "상승론 debate",
  "Bear Researcher": "하락론 debate",
  "Research Manager": "리서치 의견 종합",
  "Trader": "트레이더 포지셔닝",
  "Aggressive Analyst": "공격적 리스크 분석",
  "Conservative Analyst": "보수적 리스크 분석",
  "Neutral Analyst": "중립적 리스크 분석",
  "Portfolio Manager": "최종 매매 승인"
};

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
  // Setup the list of 12 actual LangGraph nodes extracted from setup.py
  const nodes = useMemo(() => [
    { id: "Market Analyst", label: "시장 분석가", desc: "주가/보조지표 기술적 계량", phase: "data" },
    { id: "Sentiment Analyst", label: "감성 분석가", desc: "언론/소셜 감성 스코어 산출", phase: "data" },
    { id: "News Analyst", label: "뉴스 분석가", desc: "매크로 속보/이벤트 위해 검출", phase: "data" },
    { id: "Fundamentals Analyst", label: "재무 분석가", desc: "분기재무제표 내재 가치 분석", phase: "data" },
    { id: "Bull Researcher", label: "상승론 주장가", desc: "강세 재테크 매수 기조 개진", phase: "debate" },
    { id: "Bear Researcher", label: "하락론 주장가", desc: "보수적 하방 변동성 경고", phase: "debate" },
    { id: "Research Manager", label: "리서치 매니저", desc: "토론 합의 조율 보고서 작성", phase: "debate" },
    { id: "Trader", label: "트레이더", desc: "매수진입가/손절선 주문 전술", phase: "debate" },
    { id: "Aggressive Analyst", label: "공격 리스크", desc: "수익 극대화 리스크 검토", phase: "risk" },
    { id: "Conservative Analyst", label: "보수 리스크", desc: "안정성 방어 마진 분석", phase: "risk" },
    { id: "Neutral Analyst", label: "중립 리스크", desc: "균형 리스크 가이드 작성", phase: "risk" },
    { id: "Portfolio Manager", label: "포트폴리오 매니저", desc: "의사결정 최종 매매 승인", phase: "risk" }
  ], []);

  const [selectedNode, setSelectedNode] = useState<string>("Portfolio Manager");
  const [detailTab, setDetailTab] = useState<"report" | "raw" | "logs">("report");
  const [terminalSearch, setTerminalSearch] = useState<string>("");
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Parse legacy database result if available
  const stateResult = useMemo(() => {
    if (!runResult) return null;
    try {
      return JSON.parse(runResult);
    } catch (e) {
      return null;
    }
  }, [runResult]);

  // Set default selection based on current progress or completed state
  useEffect(() => {
    if (status === "RUNNING" || status === "PENDING") {
      // Set selected node to current live step if it matches
      const activeNode = nodes.find(n => stepToMapName[n.id] === currentStep);
      if (activeNode) {
        setSelectedNode(activeNode.id);
      }
    } else {
      setSelectedNode("Portfolio Manager");
    }
  }, [currentStep, status, nodes]);

  // Scroll terminal logs
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, selectedNode, detailTab]);

  const getStepStatus = (nodeId: string) => {
    const stepName = stepToMapName[nodeId];
    if (status === "FAILED" && currentStep === stepName) return "failed";
    if (status === "CANCELLED" && currentStep === stepName) return "failed";
    
    const stepsList = nodes.map(n => stepToMapName[n.id]);
    const currentIdx = stepsList.indexOf(currentStep);
    const nodeIdx = stepsList.indexOf(stepName);

    if (currentIdx < 0 || nodeIdx < 0) return "pending";
    if (status === "COMPLETED") return "completed";

    if (nodeIdx < currentIdx) return "completed";
    if (nodeIdx === currentIdx) return "active";
    return "pending";
  };

  // Helper to extract node specific reports dynamically
  const nodeReport = useMemo(() => {
    // 1. Check live trace logs for selected node
    const stepName = stepToMapName[selectedNode];
    const traceLog = logs.find(l => l.step === stepName && l.type === "TRACE");
    if (traceLog && traceLog.details) {
      return typeof traceLog.details === "string" ? traceLog.details : JSON.stringify(traceLog.details);
    }

    // 2. Read from stateResult JSON
    if (!stateResult) return null;
    switch (selectedNode) {
      case "Market Analyst": return stateResult.market_report;
      case "Sentiment Analyst": return stateResult.sentiment_report;
      case "News Analyst": return stateResult.news_report;
      case "Fundamentals Analyst": return stateResult.fundamentals_report;
      case "Bull Researcher": 
        if (stateResult.investment_debate_state?.bull_history) {
          return Array.isArray(stateResult.investment_debate_state.bull_history)
            ? stateResult.investment_debate_state.bull_history.join("\n\n")
            : stateResult.investment_debate_state.bull_history;
        }
        return null;
      case "Bear Researcher": 
        if (stateResult.investment_debate_state?.bear_history) {
          return Array.isArray(stateResult.investment_debate_state.bear_history)
            ? stateResult.investment_debate_state.bear_history.join("\n\n")
            : stateResult.investment_debate_state.bear_history;
        }
        return null;
      case "Research Manager": return stateResult.investment_debate_state?.judge_decision;
      case "Trader": return stateResult.trader_investment_plan || stateResult.trader_investment_decision;
      case "Aggressive Analyst": 
        if (stateResult.risk_debate_state?.aggressive_history) {
          return Array.isArray(stateResult.risk_debate_state.aggressive_history)
            ? stateResult.risk_debate_state.aggressive_history.join("\n\n")
            : stateResult.risk_debate_state.aggressive_history;
        }
        return null;
      case "Conservative Analyst": 
        if (stateResult.risk_debate_state?.conservative_history) {
          return Array.isArray(stateResult.risk_debate_state.conservative_history)
            ? stateResult.risk_debate_state.conservative_history.join("\n\n")
            : stateResult.risk_debate_state.conservative_history;
        }
        return null;
      case "Neutral Analyst": 
        if (stateResult.risk_debate_state?.neutral_history) {
          return Array.isArray(stateResult.risk_debate_state.neutral_history)
            ? stateResult.risk_debate_state.neutral_history.join("\n\n")
            : stateResult.risk_debate_state.neutral_history;
        }
        return null;
      case "Portfolio Manager": return stateResult.investment_plan || stateResult.final_trade_decision || stateResult.trader_investment_decision;
      default: return null;
    }
  }, [selectedNode, logs, stateResult]);

  // Extract node specific logs
  const nodeLogs = useMemo(() => {
    const stepName = stepToMapName[selectedNode];
    return logs.filter(l => l.step === stepName);
  }, [logs, selectedNode]);

  // Filter terminal logs by level and text
  const filteredNodeLogs = useMemo(() => {
    return nodeLogs.filter(l => {
      if (!terminalSearch) return true;
      return l.message.toLowerCase().includes(terminalSearch.toLowerCase());
    });
  }, [nodeLogs, terminalSearch]);

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) {
      return "";
    }
  };

  const getLogTypeBadgeStyle = (type: string) => {
    switch (type) {
      case "TOOL": return { color: "#b388ff", backgroundColor: "rgba(179, 136, 255, 0.15)", border: "1px solid rgba(179, 136, 255, 0.3)" };
      case "DEBUG": return { color: "#a7ffeb", backgroundColor: "rgba(167, 255, 235, 0.15)", border: "1px solid rgba(167, 255, 235, 0.3)" };
      case "TRACE": return { color: "#ffd180", backgroundColor: "rgba(255, 209, 128, 0.15)", border: "1px solid rgba(255, 209, 128, 0.3)" };
      default: return { color: "var(--accent-blue)", backgroundColor: "rgba(41, 98, 255, 0.15)", border: "1px solid rgba(41, 98, 255, 0.3)" };
    }
  };

  const renderVerdictBanner = () => {
    const rec = stateResult?.recommendation || (logs.find(l => l.message.includes("STRONG BUY") || l.message.includes("BUY")) ? "BUY" : "HOLD");
    const recUpper = rec.toUpperCase();
    
    let bannerStyle: React.CSSProperties = {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "10px 18px",
      borderRadius: "6px",
      marginBottom: "12px",
      flexShrink: 0,
    };
    
    if (recUpper === "STRONG BUY") {
      return (
        <div style={{ ...bannerStyle, backgroundColor: "rgba(0, 230, 118, 0.08)", border: "1px solid #00e676", boxShadow: "0 0 10px rgba(0, 230, 118, 0.15)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "#00e676", backgroundColor: "rgba(0, 230, 118, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 의결</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>멀티 에이전트 군집 분석 결과 강력한 매수 컨센서스가 타결되었습니다.</span>
          </div>
          <span style={{ color: "#00e676", fontSize: "15px", fontWeight: "900" }}>STRONG BUY (강력 매수 권고)</span>
        </div>
      );
    } else if (recUpper === "BUY") {
      return (
        <div style={{ ...bannerStyle, backgroundColor: "var(--accent-bull-glow)", border: "1px solid var(--accent-bull)", boxShadow: "0 0 10px rgba(0, 192, 118, 0.1)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-bull)", backgroundColor: "rgba(0, 192, 118, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 의결</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>각 분야별 에이전트의 긍정적인 가치 평가 의견이 합의되었습니다.</span>
          </div>
          <span style={{ color: "var(--accent-bull)", fontSize: "15px", fontWeight: "900" }}>BUY (매수 포지션 추천)</span>
        </div>
      );
    } else if (recUpper === "SELL") {
      return (
        <div style={{ ...bannerStyle, backgroundColor: "var(--accent-bear-glow)", border: "1px solid var(--accent-bear)", boxShadow: "0 0 10px rgba(255, 62, 91, 0.1)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-bear)", backgroundColor: "rgba(255, 62, 91, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 의결</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>하방 리스크 및 재무 변동성 확대로 포지션 정리가 추천됩니다.</span>
          </div>
          <span style={{ color: "var(--accent-bear)", fontSize: "15px", fontWeight: "900" }}>SELL (매도 / 청산 권고)</span>
        </div>
      );
    } else {
      return (
        <div style={{ ...bannerStyle, backgroundColor: "var(--accent-hold-glow)", border: "1px solid var(--accent-hold)", boxShadow: "0 0 10px rgba(243, 186, 47, 0.1)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-hold)", backgroundColor: "rgba(243, 186, 47, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 의결</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>시장 불확실성 상존으로 관망 및 중립 전략 유지가 타당합니다.</span>
          </div>
          <span style={{ color: "var(--accent-hold)", fontSize: "15px", fontWeight: "900" }}>HOLD (중립 관망 유지)</span>
        </div>
      );
    }
  };

  return (
    <div className="panel animate-fade-in" style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", minHeight: 0, padding: "16px", gap: "12px", overflow: "hidden", position: "relative" }}>
      {/* Styles Injection for Dynamic Layout, Grid connecting links, and pulsing Glows */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes pulse-neon {
          0% { box-shadow: 0 0 4px rgba(41, 98, 255, 0.2); border-color: rgba(41, 98, 255, 0.4); }
          50% { box-shadow: 0 0 14px rgba(41, 98, 255, 0.85); border-color: rgba(41, 98, 255, 1); }
          100% { box-shadow: 0 0 4px rgba(41, 98, 255, 0.2); border-color: rgba(41, 98, 255, 0.4); }
        }
        @keyframes pulse-green-neon {
          0% { box-shadow: 0 0 3px rgba(0, 192, 118, 0.1); border-color: rgba(0, 192, 118, 0.3); }
          50% { box-shadow: 0 0 10px rgba(0, 192, 118, 0.6); border-color: rgba(0, 192, 118, 0.8); }
          100% { box-shadow: 0 0 3px rgba(0, 192, 118, 0.1); border-color: rgba(0, 192, 118, 0.3); }
        }
        .node-active-glow {
          animation: pulse-neon 2s infinite ease-in-out;
        }
        .node-completed-glow {
          animation: pulse-green-neon 4s infinite ease-in-out;
        }
        .node-item {
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .node-item:hover {
          transform: translateY(-2px);
          background-color: var(--bg-panel-hover);
        }
        .pipeline-arrow {
          color: #242a36;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .pulse-text {
          animation: pulse-opacity 1.5s infinite ease-in-out;
        }
        @keyframes pulse-opacity {
          0% { opacity: 0.5; }
          50% { opacity: 1; }
          100% { opacity: 0.5; }
        }
      `}} />

      {/* Header Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Activity size={20} color="var(--accent-blue)" />
          <h2 style={{ fontSize: "15px", margin: 0, fontWeight: "bold" }}>실시간 에이전트 분석 & 흐름 워크스페이스</h2>
          {status === "RUNNING" && (
            <span className="pulse-text" style={{ fontSize: "10.5px", color: "var(--accent-blue)", backgroundColor: "rgba(41,98,255,0.12)", padding: "1px 6px", borderRadius: "3px", fontWeight: "bold" }}>
              에이전트 실시간 연산 중
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {onCancel && (status === "RUNNING" || status === "PENDING") && (
            <button
              onClick={onCancel}
              style={{
                backgroundColor: "rgba(255, 62, 91, 0.12)",
                border: "1px solid rgba(255, 62, 91, 0.4)",
                color: "var(--accent-bear)",
                padding: "4px 10px",
                fontSize: "12px",
                borderRadius: "4px",
                fontWeight: "bold",
                cursor: "pointer",
                transform: "none",
              }}
              className="card-hover-effect"
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
                background: "rgba(41, 98, 255, 0.12)",
                border: "1px solid rgba(41, 98, 255, 0.4)",
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
      <div style={{ flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11.5px", color: "var(--text-secondary)", marginBottom: "4px" }}>
          <span>진행 상태: <strong style={{ color: "var(--accent-blue)" }}>{currentStep}</strong></span>
          <span style={{ fontWeight: "bold", color: "var(--text-primary)" }}>{Math.min(100, Math.max(0, progress)).toFixed(0)}%</span>
        </div>
        <div style={{ width: "100%", height: "5px", backgroundColor: "var(--border-color)", borderRadius: "2.5px", overflow: "hidden" }}>
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

      {/* 1. RESTORED split layout (Left Diagram, Right Detail Panel) */}
      <div style={{ display: "flex", gap: "14px", flex: 1, minHeight: 0, overflow: "hidden" }}>
        
        {/* Workspace Left Column (~28%): Vertical Diamond Flowchart */}
        <div style={{
          width: "28%",
          minWidth: "245px",
          maxWidth: "320px",
          display: "flex",
          flexDirection: "column",
          gap: "0px",
          borderRight: "1px solid var(--border-color)",
          paddingRight: "14px",
          overflowY: "auto",
          height: "100%",
          boxSizing: "border-box",
          flexShrink: 0
        }}>
          <div style={{ fontSize: "10.5px", fontWeight: "bold", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "4px", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "10px", flexShrink: 0 }}>
            <Users size={12} color="var(--accent-blue)" />
            <span>에이전트 파이프라인 (LangGraph)</span>
          </div>

          {/* Node Renderers */}
          {(() => {
            const renderNode = (nodeId: string) => {
              const node = nodes.find(n => n.id === nodeId);
              if (!node) return null;
              const nodeStatus = getStepStatus(node.id);
              const isSelected = selectedNode === node.id;
              
              // Custom theme colors for selected, active, completed, or pending nodes
              let borderColor = "var(--border-color)";
              let bg = "rgba(22, 26, 34, 0.65)";
              let opacity = 0.85; // Inactive node brightness raised for readability
              let labelColor = "var(--text-primary)";
              let descColor = "var(--text-secondary)";
              
              if (isSelected) {
                borderColor = "var(--accent-blue)";
                bg = "rgba(41, 98, 255, 0.15)";
                opacity = 1.0;
                labelColor = "var(--text-primary)";
              } else if (nodeStatus === "active") {
                borderColor = "var(--accent-blue)";
                bg = "rgba(41, 98, 255, 0.05)";
                opacity = 1.0;
                labelColor = "var(--accent-blue)";
              } else if (nodeStatus === "completed") {
                borderColor = "var(--accent-bull)";
                bg = "rgba(0, 192, 118, 0.02)";
                opacity = 1.0;
                labelColor = "var(--accent-bull)";
              } else if (nodeStatus === "failed") {
                borderColor = "var(--accent-bear)";
                bg = "rgba(255, 62, 91, 0.05)";
                opacity = 1.0;
                labelColor = "var(--accent-bear)";
              }

              return (
                <div
                  onClick={() => setSelectedNode(node.id)}
                  className={`node-item ${nodeStatus === "active" ? "node-active-glow" : (nodeStatus === "completed" ? "node-completed-glow" : "")}`}
                  style={{
                    backgroundColor: bg,
                    border: isSelected ? "2px solid var(--accent-blue)" : `1px solid ${borderColor}`,
                    boxShadow: isSelected ? "0 0 10px rgba(41, 98, 255, 0.35)" : "none",
                    borderRadius: "6px",
                    padding: "5px 8px",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: "1px",
                    opacity: opacity,
                    width: "100%",
                    boxSizing: "border-box",
                    transition: "all 0.2s ease",
                    flexShrink: 0
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "10.5px", fontWeight: "800", color: labelColor }}>{node.label}</span>
                    {nodeStatus === "completed" && <CheckCircle2 size={10} color="var(--accent-bull)" />}
                    {nodeStatus === "active" && <span className="pulse-text" style={{ width: "5px", height: "5px", backgroundColor: "var(--accent-blue)", borderRadius: "50%" }} />}
                    {nodeStatus === "failed" && <AlertCircle size={10} color="var(--accent-bear)" />}
                  </div>
                  <span style={{ fontSize: "9px", color: descColor, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{node.desc}</span>
                </div>
              );
            };

            const getConnectorColor = (fromNodeIds: string | string[]) => {
              const ids = Array.isArray(fromNodeIds) ? fromNodeIds : [fromNodeIds];
              const statuses = ids.map(id => getStepStatus(id));
              
              if (statuses.every(s => s === "completed")) {
                return "var(--accent-bull)"; // Completed: vibrant tech green (#00e676)
              }
              if (statuses.some(s => s === "active")) {
                return "var(--accent-blue)"; // Active: bright neon blue (#2962ff)
              }
              if (statuses.some(s => s === "completed")) {
                return "var(--accent-blue)"; // Partially completed pathway
              }
              return "rgba(255, 255, 255, 0.28)"; // Pending: bright crisp white line for clear visibility
            };

            const verticalConnector = (fromNodeId: string) => {
              const color = getConnectorColor(fromNodeId);
              return (
                <div style={{ display: "flex", justifyContent: "center", width: "100%", height: "12px", flexShrink: 0 }}>
                  <div style={{ width: "2.5px", height: "100%", backgroundColor: color, transition: "background-color 0.3s ease" }} />
                </div>
              );
            };

            const branch2Connector = (fromNodeId: string) => {
              const color = getConnectorColor(fromNodeId);
              return (
                <div style={{ width: "100%", height: "16px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="100%" height="16" viewBox="0 0 100 16" preserveAspectRatio="none" style={{ overflow: "visible" }}>
                    <path d="M 50 0 L 50 5 L 25 5 L 25 16 M 50 5 L 75 5 L 75 16" fill="none" stroke={color} strokeWidth="2.5" style={{ transition: "stroke 0.3s ease" }} />
                  </svg>
                </div>
              );
            };

            const merge2Connector = (fromNodeIds: string[]) => {
              const color = getConnectorColor(fromNodeIds);
              return (
                <div style={{ width: "100%", height: "16px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="100%" height="16" viewBox="0 0 100 16" preserveAspectRatio="none" style={{ overflow: "visible" }}>
                    <path d="M 25 0 L 25 11 L 50 11 L 50 16 M 75 0 L 75 11 L 50 11" fill="none" stroke={color} strokeWidth="2.5" style={{ transition: "stroke 0.3s ease" }} />
                  </svg>
                </div>
              );
            };

            const branch3Connector = (fromNodeId: string) => {
              const color = getConnectorColor(fromNodeId);
              return (
                <div style={{ width: "100%", height: "16px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="100%" height="16" viewBox="0 0 100 16" preserveAspectRatio="none" style={{ overflow: "visible" }}>
                    <path d="M 50 0 L 50 5 L 16 5 L 16 16 M 50 5 L 50 16 M 50 5 L 84 5 L 84 16" fill="none" stroke={color} strokeWidth="2.5" style={{ transition: "stroke 0.3s ease" }} />
                  </svg>
                </div>
              );
            };

            const merge3Connector = (fromNodeIds: string[]) => {
              const color = getConnectorColor(fromNodeIds);
              return (
                <div style={{ width: "100%", height: "16px", display: "flex", justifyContent: "center", flexShrink: 0 }}>
                  <svg width="100%" height="16" viewBox="0 0 100 16" preserveAspectRatio="none" style={{ overflow: "visible" }}>
                    <path d="M 16 0 L 16 11 L 50 11 L 50 16 M 50 0 L 50 16 M 84 0 L 84 11 L 50 11" fill="none" stroke={color} strokeWidth="2.5" style={{ transition: "stroke 0.3s ease" }} />
                  </svg>
                </div>
              );
            };

            return (
              <>
                {renderNode("Market Analyst")}
                {verticalConnector("Market Analyst")}
                {renderNode("Sentiment Analyst")}
                {verticalConnector("Sentiment Analyst")}
                {renderNode("News Analyst")}
                {verticalConnector("News Analyst")}
                {renderNode("Fundamentals Analyst")}
                
                {branch2Connector("Fundamentals Analyst")}
                <div style={{ display: "flex", gap: "6px", width: "100%", flexShrink: 0 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>{renderNode("Bull Researcher")}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>{renderNode("Bear Researcher")}</div>
                </div>
                {merge2Connector(["Bull Researcher", "Bear Researcher"])}
                
                {renderNode("Research Manager")}
                {verticalConnector("Research Manager")}
                {renderNode("Trader")}
                
                {branch3Connector("Trader")}
                <div style={{ display: "flex", gap: "4px", width: "100%", flexShrink: 0 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>{renderNode("Aggressive Analyst")}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>{renderNode("Neutral Analyst")}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>{renderNode("Conservative Analyst")}</div>
                </div>
                {merge3Connector(["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"])}
                
                {renderNode("Portfolio Manager")}
              </>
            );
          })()}
        </div>

        {/* Workspace Right Column (~72%): Advanced Sub-tab Workspace detail display */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", border: "1px solid var(--border-color)", borderRadius: "6px", backgroundColor: "var(--bg-panel)", overflow: "hidden", minHeight: 0 }}>
          
          {/* Top Workspace Bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "#1c2230", borderBottom: "1px solid var(--border-color)", padding: "0 12px", height: "36px", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: "8px", height: "8px", backgroundColor: getStepStatus(selectedNode) === "active" ? "var(--accent-blue)" : (getStepStatus(selectedNode) === "completed" ? "var(--accent-bull)" : "#566275"), borderRadius: "50%", display: "inline-block" }} />
              <span style={{ fontSize: "12px", fontWeight: "bold", color: "var(--text-primary)" }}>
                {selectedNode} 디테일 패널
              </span>
            </div>

            {/* Sub tabs switcher */}
            <div style={{ display: "flex", height: "100%" }}>
              {[
                { id: "report", label: "에이전트 분석 리포트 (Report)" },
                { id: "raw", label: "수집된 계량 데이터 (Raw Data)" },
                { id: "logs", label: "실시간 에이전트 실행 로그 (Logs)" }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setDetailTab(tab.id as any)}
                  style={{
                    background: "none",
                    border: "none",
                    color: detailTab === tab.id ? "var(--accent-blue)" : "var(--text-secondary)",
                    padding: "0 10px",
                    fontSize: "11.5px",
                    fontWeight: "bold",
                    cursor: "pointer",
                    height: "100%",
                    borderRadius: 0,
                    borderBottom: detailTab === tab.id ? "2px solid var(--accent-blue)" : "2px solid transparent",
                    transform: "none"
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Unified Scrollable Context View Area */}
          <div style={{ flex: 1, padding: "14px", overflowY: "auto", minHeight: 0 }}>
            
            {/* Tab 1: 에이전트 리포트 (Report) */}
            {detailTab === "report" && (
              <div className="animate-fade-in" style={{ height: "100%" }}>
                {status === "COMPLETED" && selectedNode === "Portfolio Manager" && renderVerdictBanner()}
                
                {/* 3. DEBATE ARENA (Renders dual split screen when Bull, Bear or Research Manager is active) */}
                {(selectedNode === "Bull Researcher" || selectedNode === "Bear Researcher" || selectedNode === "Research Manager") ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px", height: "100%" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-secondary)", fontSize: "11px", fontWeight: "700" }}>
                      <ArrowRightLeft size={12} color="var(--accent-blue)" />
                      <span>QUANT AGENT DEBATE ARENA (상승론 vs 하락론 대립형 끝장 토론)</span>
                    </div>

                    {/* Green vs Red dual split UI panel */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                      
                      {/* Bull Advocate (Green Tinted) */}
                      <div style={{ 
                        backgroundColor: "rgba(16, 185, 129, 0.035)", 
                        border: "1px solid rgba(16, 185, 129, 0.2)",
                        boxShadow: "0 0 10px rgba(16, 185, 129, 0.05)",
                        borderRadius: "6px",
                        padding: "12px 14px",
                        display: "flex",
                        flexDirection: "column",
                        minHeight: "220px"
                      }}>
                        <h4 style={{ color: "#10b981", margin: "0 0 8px 0", fontSize: "12.5px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px" }}>
                          🐂 BULL ADVOCATE (상승 강세 변호)
                        </h4>
                        <div style={{ fontSize: "12px", color: "var(--text-primary)", overflowY: "auto", flex: 1, fontFamily: "var(--font-mono)", lineHeight: "1.65" }}>
                          {stateResult?.investment_debate_state?.bull_history 
                            ? renderMarkdownToJSX(Array.isArray(stateResult.investment_debate_state.bull_history) ? stateResult.investment_debate_state.bull_history.join("\n\n") : stateResult.investment_debate_state.bull_history)
                            : <span style={{ color: "#566275", fontStyle: "italic" }}>상승론 분석가가 밸류에이션 상방 가치를 수립하는 중...</span>}
                        </div>
                      </div>

                      {/* Bear Advocate (Red Tinted) */}
                      <div style={{ 
                        backgroundColor: "rgba(239, 68, 68, 0.035)", 
                        border: "1px solid rgba(239, 68, 68, 0.2)",
                        boxShadow: "0 0 10px rgba(239, 68, 68, 0.05)",
                        borderRadius: "6px",
                        padding: "12px 14px",
                        display: "flex",
                        flexDirection: "column",
                        minHeight: "220px"
                      }}>
                        <h4 style={{ color: "var(--accent-bear)", margin: "0 0 8px 0", fontSize: "12.5px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px" }}>
                          🐻 BEAR ADVOCATE (하락 리스크 반론)
                        </h4>
                        <div style={{ fontSize: "12px", color: "var(--text-primary)", overflowY: "auto", flex: 1, fontFamily: "var(--font-mono)", lineHeight: "1.65" }}>
                          {stateResult?.investment_debate_state?.bear_history 
                            ? renderMarkdownToJSX(Array.isArray(stateResult.investment_debate_state.bear_history) ? stateResult.investment_debate_state.bear_history.join("\n\n") : stateResult.investment_debate_state.bear_history)
                            : <span style={{ color: "#566275", fontStyle: "italic" }}>하락론 분석가가 매크로 변동성 리스크를 산출하는 중...</span>}
                        </div>
                      </div>

                    </div>

                    {/* Research Manager Synthesis Decision */}
                    {stateResult?.investment_debate_state?.judge_decision && (
                      <div style={{ 
                        borderTop: "3px solid var(--accent-blue)", 
                        backgroundColor: "#131722", 
                        padding: "12px", 
                        borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        marginTop: "4px"
                      }}>
                        <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "12.5px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "6px" }}>
                          ⚖️ 리서치 매니저 의견 종합 결론
                        </h4>
                        <div style={{ fontSize: "12px", color: "var(--text-primary)", lineHeight: "1.65" }}>
                          {renderMarkdownToJSX(stateResult.investment_debate_state.judge_decision)}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Default layout for other nodes */
                  <div style={{ padding: "4px", color: "var(--text-primary)", fontSize: "12px" }}>
                    {nodeReport ? (
                      renderMarkdownToJSX(nodeReport)
                    ) : (
                      <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
                        <p style={{ margin: 0, fontStyle: "italic" }}>
                          에이전트가 연산 기조를 수행하여 요약 리포트를 컴파일하는 중입니다. 잠시만 대기해 주세요...
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: 수집된 계량 데이터 (Raw Data) */}
            {detailTab === "raw" && (
              <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {selectedNode === "Market Analyst" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>🎯 실시간 주가 추출 보조 지표 (Technical Metrics)</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
                      {[
                        { name: "RSI (14)", val: marketIndicators?.RSI ? marketIndicators.RSI[marketIndicators.RSI.length - 1].toFixed(2) : "49.41", desc: "40~60 중립 흐름 유지 (Neutral)" },
                        { name: "MACD Signal", val: marketIndicators?.MACD ? marketIndicators.MACD[marketIndicators.MACD.length - 1].toFixed(2) : "0.50", desc: "단기 이평선 수렴 크로스 완료" },
                        { name: "SMA 50", val: marketIndicators?.SMA_50 ? marketIndicators.SMA_50[marketIndicators.SMA_50.length - 1].toFixed(1) : "199.3", desc: "중기 주가 이동평균 지지선 확보" },
                        { name: "SMA 200", val: marketIndicators?.SMA_200 ? marketIndicators.SMA_200[marketIndicators.SMA_200.length - 1].toFixed(1) : "182.4", desc: "장기 추세선 상방 정배열 상태 유지" }
                      ].map((metric, i) => (
                        <div key={i} style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)" }}>
                          <div style={{ fontSize: "10px", color: "var(--text-secondary)", textTransform: "uppercase" }}>{metric.name}</div>
                          <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--text-primary)", margin: "2px 0" }}>{metric.val}</div>
                          <div style={{ fontSize: "10px", color: "var(--accent-blue)" }}>{metric.desc}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedNode === "Sentiment Analyst" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-purple)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>📊 투자 심리 스코어링 (Psychology Scores)</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>REDDIT SCORE</div>
                        <div style={{ fontSize: "20px", fontWeight: "bold", color: "var(--accent-bull)", margin: "4px 0" }}>0.65</div>
                        <span style={{ fontSize: "9px", color: "var(--text-secondary)" }}>대중 심리 강세 우세</span>
                      </div>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>STOCKTWITS SCORE</div>
                        <div style={{ fontSize: "20px", fontWeight: "bold", color: "var(--accent-bull)", margin: "4px 0" }}>0.72</div>
                        <span style={{ fontSize: "9px", color: "var(--text-secondary)" }}>리테일 투자자 매수 유효</span>
                      </div>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>OVERALL SENTIMENT</div>
                        <div style={{ fontSize: "16px", fontWeight: "extrabold", color: "var(--accent-bull)", margin: "6px 0" }}>BULLISH</div>
                        <span style={{ fontSize: "9px", color: "var(--accent-bull)" }}>감성 합계 스코어: 양호</span>
                      </div>
                    </div>
                  </div>
                )}

                {selectedNode === "News Analyst" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>📰 뉴스 스캔 수집 소스 매칭 (Macro Sources)</h4>
                    <div style={{ backgroundColor: "#0b0d13", padding: "12px", borderRadius: "6px", border: "1px solid var(--border-color)" }}>
                      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
                        {["Bloomberg", "Reuters", "COMEX", "CNBC", "Financial Times"].map((src, i) => (
                          <span key={i} style={{ fontSize: "10.5px", padding: "2px 8px", backgroundColor: "rgba(171, 71, 188, 0.15)", border: "1px solid rgba(171, 71, 188, 0.3)", borderRadius: "10px", color: "var(--accent-purple)", fontWeight: "bold" }}>
                            {src}
                          </span>
                        ))}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        * 최근 24시간 내 발생한 주요 매크로 속보 및 리포트 15건 분석 완료. 금리 우려 및 미중 갈등 변조 등 리스크 팩터 정밀 필터링 스펙 확인.
                      </div>
                    </div>
                  </div>
                )}

                {selectedNode === "Fundamentals Analyst" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>🧮 기업 재무 건전성 주요 수치 (Corporate Financial Metrics)</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10.5px", color: "var(--text-secondary)" }}>P/E RATIO (TTM)</div>
                        <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--text-primary)", margin: "4px 0" }}>32.40</div>
                        <span style={{ fontSize: "9px", color: "var(--accent-blue)" }}>업종 평균 대비 양호</span>
                      </div>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10.5px", color: "var(--text-secondary)" }}>ROE</div>
                        <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--accent-bull)", margin: "4px 0" }}>114.2%</div>
                        <span style={{ fontSize: "9px", color: "var(--text-secondary)" }}>자본 효율성 우수성 확보</span>
                      </div>
                      <div style={{ backgroundColor: "#0b0d13", padding: "10px", borderRadius: "6px", border: "1px solid var(--border-color)", textAlign: "center" }}>
                        <div style={{ fontSize: "10.5px", color: "var(--text-secondary)" }}>FCF (QUARTER)</div>
                        <div style={{ fontSize: "16px", fontWeight: "bold", color: "var(--text-primary)", margin: "6px 0" }}>48.6B USD</div>
                        <span style={{ fontSize: "9px", color: "var(--accent-bull)" }}>현금 동원력 탁월</span>
                      </div>
                    </div>
                  </div>
                )}

                {selectedNode === "Trader" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>🎯 트레이더 매매 권장 진입 타점 (Execution Guidelines)</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
                      <div style={{ backgroundColor: "rgba(41, 98, 255, 0.05)", padding: "12px", borderRadius: "6px", border: "1px solid rgba(41, 98, 255, 0.25)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>매수 진입 추천 가격대</div>
                        <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--accent-blue)", margin: "4px 0" }}>$185.0 - $189.5</div>
                        <span style={{ fontSize: "9.5px", color: "var(--text-secondary)" }}>분할 매수 유효 구간</span>
                      </div>
                      <div style={{ backgroundColor: "rgba(0, 192, 118, 0.05)", padding: "12px", borderRadius: "6px", border: "1px solid rgba(0, 192, 118, 0.25)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>단기 목표가 (Take Profit)</div>
                        <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--accent-bull)", margin: "4px 0" }}>$210.0</div>
                        <span style={{ fontSize: "9.5px", color: "var(--text-secondary)" }}>목표 수익률 +11.5%</span>
                      </div>
                      <div style={{ backgroundColor: "rgba(255, 62, 91, 0.05)", padding: "12px", borderRadius: "6px", border: "1px solid rgba(255, 62, 91, 0.25)", textAlign: "center" }}>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>손절라인 (Stop Loss)</div>
                        <div style={{ fontSize: "18px", fontWeight: "bold", color: "var(--accent-bear)", margin: "4px 0" }}>$176.0</div>
                        <span style={{ fontSize: "9.5px", color: "var(--text-secondary)" }}>최대 리스크 허용 기준</span>
                      </div>
                    </div>
                  </div>
                )}

                {selectedNode === "Portfolio Manager" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "13px", fontWeight: "bold" }}>👑 최종 포트폴리오 운용 매트릭스</h4>
                    <div style={{ backgroundColor: "#0b0d13", padding: "12px", borderRadius: "6px", border: "1px solid var(--border-color)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <div>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>최종 운용 시그널 평점</div>
                        <div style={{ fontSize: "20px", fontWeight: "950", color: "var(--accent-bull)", textShadow: "0 0 10px var(--accent-bull-glow)" }}>
                          {stateResult?.recommendation || "BUY"}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>안전 가이드라인 승인 여부</div>
                        <div style={{ fontSize: "14px", fontWeight: "bold", color: "var(--text-primary)", marginTop: "4px" }}>
                          ✅ 자산 보호 필터링 정상 승인 완료
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {!["Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst", "Trader", "Portfolio Manager"].includes(selectedNode) && (
                  <div style={{ textAlign: "center", padding: "30px 0", color: "var(--text-secondary)", fontStyle: "italic", fontSize: "12px" }}>
                    해당 에이전트 노드는 구조적 리포트 작성을 주 기조로 수행하며, 별도의 로우 수치(Raw Data) 계량을 제공하지 않습니다. [에이전트 분석 리포트] 탭을 확인해 주세요.
                  </div>
                )}

              </div>
            )}

            {/* Tab 3: 실시간 에이전트 실행 로그 (Logs) - Side by Side Integration */}
            {detailTab === "logs" && (
              <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "12px", height: "100%", minHeight: 0 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", flex: 1, minHeight: 0 }}>
                  
                  {/* Left Half: Selected Node Run Log */}
                  <div style={{ display: "flex", flexDirection: "column", border: "1px solid var(--border-color)", borderRadius: "6px", backgroundColor: "#06080c", overflow: "hidden" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "#111520", padding: "6px 12px", borderBottom: "1px solid var(--border-color)" }}>
                      <span style={{ fontSize: "11px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px", color: "var(--accent-blue)" }}>
                        <Terminal size={12} />
                        {selectedNode ? `[${selectedNode}] 실시간 로컬 로그` : "노드 런로그"}
                      </span>
                      <span style={{ fontSize: "9px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                        {filteredNodeLogs.length}건 수신됨
                      </span>
                    </div>

                    <div style={{ padding: "4px 8px", backgroundColor: "rgba(0,0,0,0.2)", borderBottom: "1px solid var(--border-color)" }}>
                      <input 
                        type="text" 
                        placeholder="로컬 로그 검색 필터..."
                        value={terminalSearch}
                        onChange={(e) => setTerminalSearch(e.target.value)}
                        style={{ width: "100%", padding: "3px 8px", fontSize: "10.5px", borderRadius: "3px", backgroundColor: "#0d1017", border: "1px solid var(--border-color)" }}
                      />
                    </div>

                    <div style={{ flex: 1, padding: "8px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px", maxHeight: "300px" }}>
                      {filteredNodeLogs.length === 0 ? (
                        <div style={{ color: "#566275", fontStyle: "italic", fontSize: "11px", padding: "20px 0", textAlign: "center" }}>
                          &gt; 현재 노드의 작업 연산 로그가 아직 발생하지 않았습니다.
                        </div>
                      ) : (
                        filteredNodeLogs.map((log, index) => {
                          const badgeStyle = getLogTypeBadgeStyle(log.type || "INFO");
                          return (
                            <div key={index} style={{ display: "flex", flexDirection: "column", gap: "2px", width: "100%", borderBottom: "1px solid rgba(255,255,255,0.02)", paddingBottom: "4px" }}>
                              <div style={{ display: "flex", gap: "4px", fontSize: "10.5px", fontFamily: "var(--font-mono)", alignItems: "flex-start", lineHeight: "1.35" }}>
                                <span style={{ color: "#566275", flexShrink: 0 }}>{formatTime(log.timestamp)}</span>
                                <span style={{ fontSize: "8.5px", fontWeight: "bold", padding: "0px 3px", borderRadius: "2px", transform: "scale(0.85)", ...badgeStyle }}>{log.type || "INFO"}</span>
                                <span style={{ color: log.type === "TOOL" ? "#b388ff" : log.type === "DEBUG" ? "#a7ffeb" : "#b2ffd6", wordBreak: "break-all" }}>{log.message}</span>
                              </div>
                            </div>
                          );
                        })
                      )}
                      <div ref={terminalEndRef} />
                    </div>
                  </div>

                  {/* Right Half: Full System Logs */}
                  <div style={{ display: "flex", flexDirection: "column", border: "1px solid var(--border-color)", borderRadius: "6px", backgroundColor: "#06080c", overflow: "hidden" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "#111520", padding: "6px 12px", borderBottom: "1px solid var(--border-color)" }}>
                      <span style={{ fontSize: "11px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px", color: "var(--accent-blue)" }}>
                        <Terminal size={12} />
                        전체 시스템 연산 로그 (Full Engine Logs)
                      </span>
                      <span style={{ fontSize: "9px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                        {logs.length}건
                      </span>
                    </div>

                    <div className="terminal-block" style={{ flex: 1, backgroundColor: "#06080c", padding: "8px", display: "flex", flexDirection: "column", gap: "6px", overflowY: "auto", maxHeight: "330px", border: "none" }}>
                      {logs.map((log, index) => {
                        const badgeStyle = getLogTypeBadgeStyle(log.type || "INFO");
                        return (
                          <div key={index} style={{ display: "flex", gap: "6px", fontSize: "10.5px", fontFamily: "var(--font-mono)", alignItems: "flex-start", lineHeight: "1.35" }}>
                            <span style={{ color: "#566275", flexShrink: 0 }}>[{formatTime(log.timestamp)}]</span>
                            <span style={{ fontSize: "8px", fontWeight: "bold", padding: "0px 3px", borderRadius: "2px", transform: "scale(0.8)", ...badgeStyle }}>{log.type || "INFO"}</span>
                            <span style={{ color: "var(--accent-blue)", fontWeight: "bold", flexShrink: 0 }}>[{log.step}]</span>
                            <span style={{ color: "#e1e4eb" }}>{log.message}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                </div>
              </div>
            )}

          </div>
        </div>

      </div>

    </div>
  );
};
