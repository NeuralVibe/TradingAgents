import React from "react";
import { Shield, Sparkles, TrendingUp, DollarSign, Users, Award, BookOpen, MessageSquare, ArrowRightLeft, ShieldAlert, Maximize2, Minimize2 } from "lucide-react";

interface ReportDetailsProps {
  run: {
    ticker: string;
    trade_date: string;
    status: string;
    recommendation: string;
    decision: string | null;
    result: string | null;
  };
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

// *italic* 인라인 마크다운 파서 헬퍼
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

// **bold** 강조 및 중첩 *italic* 인라인 마크다운 파서 헬퍼
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

// `inline code` 백틱 인라인 마크다운 파서 헬퍼
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

// 줄 단위 및 블록 단위(테이블, 인용구, 구분선) 마크다운을 HTML JSX 노드로 정밀 렌더링하는 만능 렌더러 헬퍼 함수
const renderMarkdownToJSX = (text: string | null | undefined): React.ReactNode => {
  if (!text) return <span style={{ color: "var(--text-secondary)", fontStyle: "italic", fontSize: "12px" }}>분석 데이터가 존재하지 않습니다.</span>;

  // 1. 테이블 내 빈 줄 제거를 위한 전처리
  const rawLines = text.split("\n");
  const lines: string[] = [];
  
  for (let i = 0; i < rawLines.length; i++) {
    const current = rawLines[i].trim();
    if (current === "") {
      let nextNonEmpty = "";
      for (let j = i + 1; j < rawLines.length; j++) {
        const val = rawLines[j].trim();
        if (val !== "") {
          nextNonEmpty = val;
          break;
        }
      }
      let prevNonEmpty = "";
      for (let j = lines.length - 1; j >= 0; j--) {
        const val = lines[j].trim();
        if (val !== "") {
          prevNonEmpty = val;
          break;
        }
      }
      
      // 이전 줄과 다음 줄 모두 '|'로 시작한다면 테이블 데이터 사이의 빈 줄이므로 건너뜀
      if (prevNonEmpty.startsWith("|") && nextNonEmpty.startsWith("|")) {
        continue;
      }
    }
    lines.push(rawLines[i]);
  }

  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. 코드 블록 파싱 (```)
    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // closing ``` 건너뜀
      elements.push(
        <pre key={`codeblock-${i}`} style={{
          backgroundColor: "#0b0e14",
          border: "1px solid var(--border-color)",
          borderRadius: "4px",
          padding: "10px",
          overflowX: "auto",
          margin: "10px 0",
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          color: "#e1e4eb"
        }}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // 2. 테이블 마크다운 파싱 (|)
    if (trimmed.startsWith("|")) {
      const tableRows: string[][] = [];
      let tableAlignments: string[] = [];
      
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i].split("|").slice(1, -1);
        
        // 구분선 라인 매칭인지 확인 (예: |:---|:---| or |---|)
        const isSeparator = cells.every(cell => {
          const c = cell.trim();
          return c.startsWith(":") || c.startsWith("-") || c === "";
        });
        
        if (isSeparator) {
          tableAlignments = cells.map(cell => {
            const c = cell.trim();
            if (c.startsWith(":") && c.endsWith(":")) return "center";
            if (c.endsWith(":")) return "right";
            return "left";
          });
        } else {
          tableRows.push(cells);
        }
        i++;
      }

      if (tableRows.length > 0) {
        const headerRow = tableRows[0];
        const bodyRows = tableRows.slice(1);
        elements.push(
          <div key={`table-${i}`} style={{ overflowX: "auto", margin: "10px 0", border: "1px solid var(--border-color)", borderRadius: "4px", backgroundColor: "#0b0e14" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", fontFamily: "var(--font-mono)" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border-color)", backgroundColor: "#111520" }}>
                  {headerRow.map((cell, idx) => (
                    <th key={`th-${idx}`} style={{ padding: "8px 12px", textAlign: (tableAlignments[idx] as any) || "left", color: "var(--accent-blue)", fontWeight: "bold", borderRight: "1px solid var(--border-color)" }}>
                      {parseInlineCode(cell.trim())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rIdx) => (
                  <tr key={`tr-${rIdx}`} style={{ borderBottom: "1px solid var(--border-color)", backgroundColor: rIdx % 2 === 0 ? "transparent" : "#0e1117" }}>
                    {row.map((cell, cIdx) => (
                      <td key={`td-${cIdx}`} style={{ padding: "6px 12px", textAlign: (tableAlignments[cIdx] as any) || "left", color: "var(--text-primary)", borderRight: "1px solid var(--border-color)" }}>
                        {parseInlineCode(cell.trim())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }

    // 3. 인용구 마크다운 파싱 (>)
    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        const content = lines[i].trim().substring(1).trim();
        quoteLines.push(content);
        i++;
      }
      elements.push(
        <blockquote key={`quote-${i}`} style={{
          margin: "8px 0",
          padding: "8px 12px",
          backgroundColor: "rgba(41, 98, 255, 0.05)",
          borderLeft: "4px solid var(--accent-blue)",
          borderRadius: "0 4px 4px 0",
          fontSize: "12px",
          fontStyle: "italic",
          color: "var(--text-primary)",
          lineHeight: "1.45"
        }}>
          {quoteLines.map((lineContent, lineIdx) => (
            <div key={`ql-${lineIdx}`} style={{ minHeight: "14px" }}>
              {parseInlineCode(lineContent)}
            </div>
          ))}
        </blockquote>
      );
      continue;
    }

    // 4. 구분선 마크다운 파싱 (-- 또는 ---)
    if (trimmed === "--" || trimmed === "---" || trimmed === "***" || trimmed === "* * *") {
      elements.push(
        <hr key={`hr-${i}`} style={{
          borderColor: "var(--border-color)",
          margin: "12px 0",
          borderStyle: "solid",
          borderWidth: "1px 0 0 0",
          flexShrink: 0
        }} />
      );
      i++;
      continue;
    }

    // 5. 헤더 마크다운 파싱 (#, ##, ###, ####)
    if (trimmed.startsWith("####")) {
      elements.push(
        <h5 key={`h5-${i}`} style={{ color: "var(--text-secondary)", marginTop: "8px", marginBottom: "4px", fontSize: "12px", fontWeight: "600" }}>
          {parseInlineCode(trimmed.substring(4).trim())}
        </h5>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("###")) {
      elements.push(
        <h4 key={`h4-${i}`} style={{ color: "var(--accent-blue)", marginTop: "12px", marginBottom: "6px", fontSize: "13px", fontWeight: "600" }}>
          {parseInlineCode(trimmed.substring(3).trim())}
        </h4>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("##")) {
      elements.push(
        <h3 key={`h3-${i}`} style={{ color: "var(--text-primary)", marginTop: "16px", marginBottom: "8px", fontSize: "14px", fontWeight: "700", borderBottom: "1px solid #242a36", paddingBottom: "2px" }}>
          {parseInlineCode(trimmed.substring(2).trim())}
        </h3>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith("#")) {
      elements.push(
        <h2 key={`h2-${i}`} style={{ color: "var(--text-primary)", marginTop: "20px", marginBottom: "10px", fontSize: "16px", fontWeight: "800" }}>
          {parseInlineCode(trimmed.substring(1).trim())}
        </h2>
      );
      i++;
      continue;
    }

    // 6. 리스트 마크다운 파싱 (- 또는 * 또는 1. 2.)
    const isUnorderedList = trimmed.startsWith("- ") || trimmed.startsWith("* ");
    const isOrderedList = /^\d+\.\s/.test(trimmed);
    
    if (isUnorderedList || isOrderedList) {
      const listItems: { text: string; ordered: boolean; num?: number }[] = [];
      while (i < lines.length) {
        const currTrim = lines[i].trim();
        const isCurrUnordered = currTrim.startsWith("- ") || currTrim.startsWith("* ");
        const isCurrOrdered = /^\d+\.\s/.test(currTrim);
        
        if (isCurrUnordered) {
          listItems.push({ text: currTrim.substring(2).trim(), ordered: false });
          i++;
        } else if (isCurrOrdered) {
          const match = currTrim.match(/^(\d+)\.\s(.*)/);
          if (match) {
            listItems.push({ text: match[2].trim(), ordered: true, num: parseInt(match[1]) });
          } else {
            listItems.push({ text: currTrim.substring(currTrim.indexOf(".") + 1).trim(), ordered: true });
          }
          i++;
        } else {
          break;
        }
      }

      elements.push(
        <ul key={`list-${i}`} style={{ paddingLeft: "16px", margin: "6px 0", listStyleType: "none" }}>
          {listItems.map((item, itemIdx) => (
            <li key={`li-${itemIdx}`} style={{
              position: "relative",
              paddingLeft: "12px",
              marginBottom: "4px",
              color: "var(--text-primary)",
              fontSize: "12px",
              lineHeight: "1.45"
            }}>
              <span style={{
                position: "absolute",
                left: 0,
                color: "var(--accent-blue)",
                fontWeight: "bold",
                fontSize: "11px"
              }}>
                {item.ordered ? `${item.num || (itemIdx + 1)}.` : "•"}
              </span>
              {parseInlineCode(item.text)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // 7. 빈 줄 처리
    if (trimmed === "") {
      elements.push(<div key={`empty-${i}`} style={{ height: "6px" }} />);
      i++;
      continue;
    }

    // 8. 일반 단락 파싱 (빈 줄이나 다른 블록으로 구분될 때까지 연속된 줄을 하나의 p 태그로 묶음)
    const paragraphLines: string[] = [];
    while (i < lines.length) {
      const currLine = lines[i];
      const currTrim = currLine.trim();
      
      if (currTrim === "") break;
      
      // 다른 블록 시작 패턴을 만나면 종료
      if (currTrim.startsWith("```") ||
          currTrim.startsWith("|") ||
          currTrim.startsWith(">") ||
          currTrim.startsWith("- ") ||
          currTrim.startsWith("* ") ||
          /^\d+\.\s/.test(currTrim) ||
          currTrim.startsWith("#") ||
          currTrim === "--" ||
          currTrim === "---" ||
          currTrim === "***" ||
          currTrim === "* * *") {
        break;
      }
      
      paragraphLines.push(currTrim);
      i++;
    }

    if (paragraphLines.length > 0) {
      const textVal = paragraphLines.join(" ");
      elements.push(
        <p key={`p-${i}`} style={{ margin: "0 0 6px 0", color: "var(--text-primary)", lineHeight: "1.45", fontSize: "12px" }}>
          {parseInlineCode(textVal)}
        </p>
      );
    }
  }

  return elements;
};

export const ReportDetails: React.FC<ReportDetailsProps> = ({
  run,
  isExpanded = false,
  onToggleExpand,
}) => {
  if (!run.decision && !run.result) {
    return (
      <div className="panel" style={{ flex: 1, justifyContent: "center", alignItems: "center", minHeight: "500px" }}>
        <p style={{ color: "var(--text-secondary)" }}>시뮬레이션 완료 시 고도화된 에이전트 대립 분석 데이터가 여기에 표시됩니다.</p>
      </div>
    );
  }

  // Parse state result JSON if available
  let stateResult: any = null;
  if (run.result) {
    try {
      stateResult = JSON.parse(run.result);
    } catch (e) {
      console.error("Error parsing run results JSON:", e);
    }
  }

  // 슬림하고 세련된 네온 가로 한 줄 Verdict Banner 렌더러
  const renderVerdictBanner = () => {
    const rec = run.recommendation;
    let bannerStyle: React.CSSProperties = {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "10px 18px",
      borderRadius: "6px",
      marginBottom: "12px",
      flexShrink: 0,
    };
    
    if (rec === "BUY") {
      return (
        <div style={{
          ...bannerStyle,
          backgroundColor: "var(--accent-bull-glow)",
          border: "1px solid var(--accent-bull)",
          boxShadow: "0 0 10px rgba(0, 192, 118, 0.1)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-bull)", backgroundColor: "rgba(0, 192, 118, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 결론</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>{run.ticker}에 대한 군집 분석이 타결되었습니다.</span>
          </div>
          <span style={{ color: "var(--accent-bull)", fontSize: "16px", fontWeight: "900", letterSpacing: "-0.01em" }}>STRONG BUY (강력 매수 권고)</span>
        </div>
      );
    } else if (rec === "SELL") {
      return (
        <div style={{
          ...bannerStyle,
          backgroundColor: "var(--accent-bear-glow)",
          border: "1px solid var(--accent-bear)",
          boxShadow: "0 0 10px rgba(255, 62, 91, 0.1)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-bear)", backgroundColor: "rgba(255, 62, 91, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 결론</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>{run.ticker}에 대한 리스크가 가시화되었습니다.</span>
          </div>
          <span style={{ color: "var(--accent-bear)", fontSize: "16px", fontWeight: "900", letterSpacing: "-0.01em" }}>STRONG SELL (강력 매도 권고)</span>
        </div>
      );
    } else {
      return (
        <div style={{
          ...bannerStyle,
          backgroundColor: "var(--accent-hold-glow)",
          border: "1px solid var(--accent-hold)",
          boxShadow: "0 0 10px rgba(243, 186, 47, 0.1)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "10px", fontWeight: "bold", color: "var(--accent-hold)", backgroundColor: "rgba(243, 186, 47, 0.15)", padding: "2px 6px", borderRadius: "3px", letterSpacing: "0.05em" }}>최종 결론</span>
            <span style={{ color: "#ffffff", fontSize: "13px", fontWeight: "600" }}>{run.ticker}에 대한 중립 성향이 대립하고 있습니다.</span>
          </div>
          <span style={{ color: "var(--accent-hold)", fontSize: "16px", fontWeight: "900", letterSpacing: "-0.01em" }}>HOLD (중립 관망 권고)</span>
        </div>
      );
    }
  };

  return (
    <div className="panel" style={{ flex: 1, maxHeight: isExpanded ? "calc(100vh - 100px)" : "100%", height: isExpanded ? "calc(100vh - 100px)" : "auto", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Header Info */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px", marginBottom: "8px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={16} color="var(--accent-blue)" />
          <h2 style={{ fontSize: "14px", margin: 0 }}>QUANT AGENTS CONSENSUS DEBATE ARENA (군집 의사결정 매트릭스)</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "10.5px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
          <span>TARGET: {run.ticker} | DATE: {run.trade_date}</span>
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              className="tab-btn"
              style={{
                padding: "3px 6px",
                fontSize: "10px",
                background: "rgba(41, 98, 255, 0.15)",
                border: "1px solid var(--accent-blue)",
                color: "var(--accent-blue)",
                borderRadius: "3px",
                height: "auto",
                transform: "none",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                cursor: "pointer",
                fontWeight: "bold"
              }}
            >
              {isExpanded ? <Minimize2 size={11} /> : <Maximize2 size={11} />}
              {isExpanded ? "축소" : "확대"}
            </button>
          )}
        </div>
      </div>

      {/* 1. Slim Verdict Banner Bar (가로 한줄형) */}
      {renderVerdictBanner()}

      {/* Main Scrollable View */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px", paddingRight: "4px" }}>
        
        {/* 2. PM 최종 승인 주문서 (Compact height & padding) */}
        <div className="card" style={{ backgroundColor: "#141926", borderColor: "var(--accent-blue)", padding: "10px 14px", flexShrink: 0, display: "flex", flexDirection: "column", maxHeight: "130px", overflow: "hidden" }}>
          <h3 style={{ margin: "0 0 6px 0", fontSize: "12.5px", color: "var(--accent-blue)", display: "flex", alignItems: "center", gap: "6px", fontWeight: "700" }}>
            <Award size={14} />
            PM 최종 승인 주문서 (Portfolio Manager Execution Order)
          </h3>
          <div style={{ overflowY: "auto", fontSize: "12px", color: "var(--text-primary)", paddingRight: "2px" }}>
            {renderMarkdownToJSX(run.decision)}
          </div>
        </div>

        {/* 3. THREE-COLUMN DEBATE ARENA (분석가 리포트 vs 매크로 리서치 vs 의사결정 및 합의) */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px", color: "var(--text-secondary)", fontSize: "11px", fontWeight: "700" }}>
            <ArrowRightLeft size={12} color="var(--accent-blue)" />
            <span>에이전트 논리 대립 아레나 (3-Column Agent Debate Arena)</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.05fr 0.9fr 1.05fr", gap: "12px", alignItems: "stretch" }}>
            
            {/* Column 1: 개별 전문 분석가 리포트 (Core Analysts) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div 
                style={{ 
                  backgroundColor: "rgba(0, 192, 118, 0.05)", 
                  border: "1px solid var(--accent-bull)", 
                  borderRadius: "4px", 
                  padding: "4px 8px",
                  textAlign: "center",
                  fontSize: "11px",
                  fontWeight: "bold",
                  color: "var(--accent-bull)"
                }}
              >
                📊 ANALYST CORE (전문 분석가 리포트)
              </div>

              {stateResult?.market_report && (
                <div className="card" style={{ borderLeft: "4px solid var(--accent-bull)", padding: "10px" }}>
                  <h4 style={{ color: "var(--accent-bull)", margin: "0 0 4px 0", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <TrendingUp size={12} />
                    시장 분석가 (Market Engine)
                  </h4>
                  <p style={{ fontSize: "10.5px", color: "var(--text-secondary)", margin: "0 0 6px 0" }}>주가 추세 및 보조 지표 상승 동력</p>
                  <div style={{ fontSize: "12px", color: "var(--text-primary)", maxHeight: "140px", overflowY: "auto", paddingRight: "2px" }}>
                    {renderMarkdownToJSX(stateResult.market_report)}
                  </div>
                </div>
              )}

              {stateResult?.fundamentals_report && (
                <div className="card" style={{ borderLeft: "4px solid var(--accent-bull)", padding: "10px" }}>
                  <h4 style={{ color: "var(--accent-bull)", margin: "0 0 4px 0", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <DollarSign size={12} />
                    재무 분석가 (Fundamentals)
                  </h4>
                  <p style={{ fontSize: "10.5px", color: "var(--text-secondary)", margin: "0 0 6px 0" }}>기업 내재 가치 및 재무제표 장점</p>
                  <div style={{ fontSize: "12px", color: "var(--text-primary)", maxHeight: "140px", overflowY: "auto", paddingRight: "2px" }}>
                    {renderMarkdownToJSX(stateResult.fundamentals_report)}
                  </div>
                </div>
              )}

              {stateResult?.sentiment_report ? (
                <div className="card" style={{ borderLeft: "4px solid var(--accent-bear)", padding: "10px" }}>
                  <h4 style={{ color: "var(--accent-bear)", margin: "0 0 4px 0", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <ShieldAlert size={12} />
                    감성 분석가 (Sentiment)
                  </h4>
                  <p style={{ fontSize: "10.5px", color: "var(--text-secondary)", margin: "0 0 6px 0" }}>투자자 반응 및 부정 심리 탐색</p>
                  <div style={{ fontSize: "12px", color: "var(--text-primary)", maxHeight: "140px", overflowY: "auto", paddingRight: "2px" }}>
                    {renderMarkdownToJSX(stateResult.sentiment_report)}
                  </div>
                </div>
              ) : (
                <div className="card" style={{ borderLeft: "4px solid var(--accent-bear)", padding: "10px" }}>
                  <h4 style={{ color: "var(--accent-bear)", margin: "0 0 4px 0", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
                    <ShieldAlert size={12} />
                    감성 요인 수집 대기
                  </h4>
                  <p style={{ fontSize: "11.5px", color: "var(--text-secondary)" }}>심리 데이터 로드 생략됨</p>
                </div>
              )}
            </div>

            {/* Column 2: 매크로 및 정보 검색 (Research & news) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div 
                style={{ 
                  backgroundColor: "rgba(171, 71, 188, 0.05)", 
                  border: "1px solid var(--accent-purple)", 
                  borderRadius: "4px", 
                  padding: "4px 8px",
                  textAlign: "center",
                  fontSize: "11px",
                  fontWeight: "bold",
                  color: "var(--accent-purple)"
                }}
              >
                🔍 CONTEXT & RESEARCH (정보 및 매크로 리서치)
              </div>

              {stateResult?.news_report && (
                <div className="card" style={{ borderLeft: "4px solid var(--accent-purple)", padding: "12px", display: "flex", flexDirection: "column", flex: 1 }}>
                  <h4 style={{ color: "var(--accent-purple)", margin: "0 0 4px 0", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <BookOpen size={13} />
                    매크로 리서처 (Research Manager)
                  </h4>
                  <p style={{ fontSize: "10.5px", color: "var(--text-secondary)", margin: "0 0 8px 0" }}>글로벌 거시 경제 및 시장 뉴스 분석 리포트</p>
                  <div style={{ fontSize: "12px", color: "var(--text-primary)", overflowY: "auto", flex: 1, paddingRight: "2px", maxHeight: "490px" }}>
                    {renderMarkdownToJSX(stateResult.news_report)}
                  </div>
                </div>
              )}
            </div>

            {/* Column 3: 아레나 끝장 토론 & 최종 중재 (Debate & Consensus) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div 
                style={{ 
                  backgroundColor: "rgba(41, 98, 255, 0.05)", 
                  border: "1px solid var(--accent-blue)", 
                  borderRadius: "4px", 
                  padding: "4px 8px",
                  textAlign: "center",
                  fontSize: "11px",
                  fontWeight: "bold",
                  color: "var(--accent-blue)"
                }}
              >
                ⚔️ DEBATE & CONSENSUS (끝장 토론 및 합의)
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                {stateResult?.investment_debate_state?.bull_history && (
                  <div className="card" style={{ borderLeft: "3px solid var(--accent-bull)", padding: "8px", backgroundColor: "rgba(0, 192, 118, 0.02)" }}>
                    <h4 style={{ color: "var(--accent-bull)", margin: "0 0 2px 0", fontSize: "11.5px", display: "flex", alignItems: "center", gap: "3px" }}>
                      <MessageSquare size={11} />
                      매수 변호 (Bull)
                    </h4>
                    <div style={{ fontSize: "11px", maxHeight: "110px", overflowY: "auto", paddingRight: "2px", fontFamily: "var(--font-mono)" }}>
                      {renderMarkdownToJSX(stateResult.investment_debate_state.bull_history)}
                    </div>
                  </div>
                )}

                {stateResult?.investment_debate_state?.bear_history && (
                  <div className="card" style={{ borderLeft: "3px solid var(--accent-bear)", padding: "8px", backgroundColor: "rgba(255, 62, 91, 0.02)" }}>
                    <h4 style={{ color: "var(--accent-bear)", margin: "0 0 2px 0", fontSize: "11.5px", display: "flex", alignItems: "center", gap: "3px" }}>
                      <MessageSquare size={11} />
                      매도 변론 (Bear)
                    </h4>
                    <div style={{ fontSize: "11px", maxHeight: "110px", overflowY: "auto", paddingRight: "2px", fontFamily: "var(--font-mono)" }}>
                      {renderMarkdownToJSX(stateResult.investment_debate_state.bear_history)}
                    </div>
                  </div>
                )}
              </div>

              {stateResult?.investment_debate_state?.judge_decision && (
                <div className="card" style={{ borderTop: "3px solid var(--accent-blue)", padding: "10px", backgroundColor: "#131722", flex: 1, display: "flex", flexDirection: "column", minHeight: "180px" }}>
                  <h4 style={{ color: "var(--accent-blue)", margin: "0 0 4px 0", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <Users size={13} />
                    토론 심판 합의문 (Debate Judge)
                  </h4>
                  <div style={{ fontSize: "11.5px", color: "var(--text-primary)", overflowY: "auto", flex: 1, paddingRight: "2px", maxHeight: "250px" }}>
                    {renderMarkdownToJSX(stateResult.investment_debate_state.judge_decision)}
                  </div>
                </div>
              )}
            </div>

          </div>
        </div>

        {/* 4. BOTTOM ROW: RISK CONSENSUS & TRADING EXECUTION PLAN (리스크 통제 & 매매 전략 실행) */}
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: "12px", marginTop: "2px" }}>
          
          {/* Risk Committee Panel */}
          {stateResult?.risk_debate_state && (
            <div className="card" style={{ borderLeft: "4px solid var(--accent-purple)", backgroundColor: "#111520", padding: "14px", display: "flex", flexDirection: "column" }}>
              <h3 style={{ margin: "0 0 8px 0", fontSize: "12.5px", color: "var(--accent-purple)", display: "flex", alignItems: "center", gap: "6px", fontWeight: "700" }}>
                <Shield size={14} />
                리스크 관리위원회 종합 통제안 (Risk Consensus Judgment)
              </h3>
              
              <div style={{ padding: "10px 12px", backgroundColor: "rgba(171, 71, 188, 0.05)", border: "1px solid rgba(171, 71, 188, 0.15)", borderRadius: "4px", fontSize: "12px", color: "#e1e4eb", marginBottom: "8px", lineHeight: "1.45", maxHeight: "150px", overflowY: "auto" }}>
                {renderMarkdownToJSX(stateResult.risk_debate_state.judge_decision || "위원회 종합 합의가 타결되었습니다.")}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "180px", overflowY: "auto", paddingRight: "2px" }}>
                {stateResult.risk_debate_state.conservative_history && (
                  <div style={{ padding: "6px", backgroundColor: "#0b0d13", borderRadius: "4px" }}>
                    <div style={{ fontSize: "10.5px", color: "var(--accent-bull)", fontWeight: "bold", marginBottom: "2px" }}>🛡️ 보수적 안방 리스크 필터 (Conservative Safety)</div>
                    <div style={{ fontSize: "11.5px", color: "var(--text-primary)" }}>{renderMarkdownToJSX(stateResult.risk_debate_state.conservative_history)}</div>
                  </div>
                )}
                {stateResult.risk_debate_state.neutral_history && (
                  <div style={{ padding: "6px", backgroundColor: "#0b0d13", borderRadius: "4px" }}>
                    <div style={{ fontSize: "10.5px", color: "var(--accent-blue)", fontWeight: "bold", marginBottom: "2px" }}>⚖️ 중립적 균형 리스크 필터 (Balanced Risk)</div>
                    <div style={{ fontSize: "11.5px", color: "var(--text-primary)" }}>{renderMarkdownToJSX(stateResult.risk_debate_state.neutral_history)}</div>
                  </div>
                )}
                {stateResult.risk_debate_state.aggressive_history && (
                  <div style={{ padding: "6px", backgroundColor: "#0b0d13", borderRadius: "4px" }}>
                    <div style={{ fontSize: "10.5px", color: "var(--accent-bear)", fontWeight: "bold", marginBottom: "2px" }}>🔥 공격적 고수익 리스크 필터 (Aggressive Risk Exposure)</div>
                    <div style={{ fontSize: "11.5px", color: "var(--text-primary)" }}>{renderMarkdownToJSX(stateResult.risk_debate_state.aggressive_history)}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Trader Execution Panel */}
          {stateResult?.trader_investment_plan && (
            <div className="card" style={{ borderLeft: "4px solid var(--accent-blue)", backgroundColor: "#111520", padding: "14px", display: "flex", flexDirection: "column", maxHeight: "250px" }}>
              <h3 style={{ margin: "0 0 6px 0", fontSize: "12.5px", color: "var(--accent-blue)", display: "flex", alignItems: "center", gap: "6px", fontWeight: "700" }}>
                <TrendingUp size={14} />
                트레이더 실제 매매 전술서 (Trading Tactical Position Order)
              </h3>
              <p style={{ fontSize: "10.5px", color: "var(--text-secondary)", margin: "0 0 8px 0" }}>리서치 보고서를 실제 매수/매도 수량 및 진입점 가격 전술로 변환</p>
              
              <div style={{ flex: 1, overflowY: "auto", fontSize: "12px", color: "#e1e4eb", backgroundColor: "#0b0d13", padding: "10px", borderRadius: "4px", border: "1px solid var(--border-color)", paddingRight: "4px", fontFamily: "var(--font-mono)" }}>
                {renderMarkdownToJSX(stateResult.trader_investment_plan)}
              </div>
            </div>
          )}

        </div>

      </div>
    </div>
  );
};
