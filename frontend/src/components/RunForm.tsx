import React, { useState } from "react";
import { PlusCircle, Database, Trash2, X } from "lucide-react";

interface RunResponse {
  id: string;
  ticker: string;
  trade_date: string;
  status: string;
  progress: number;
  current_step: string;
  recommendation: string;
  created_at: string;
}

interface RunFormProps {
  onSubmit: (data: { ticker: string; date: string }) => void;
  isLoading: boolean;
  history: RunResponse[];
  activeRunId: string | null;
  onSelectRun: (id: string) => void;
  onDeleteRun: (id: string) => void;
}

export const RunForm: React.FC<RunFormProps> = ({
  onSubmit,
  isLoading,
  history,
  activeRunId,
  onSelectRun,
  onDeleteRun,
}) => {
  const [ticker, setTicker] = useState("AAPL");
  const [date, setDate] = useState("2026-05-25");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker || !date) return;
    onSubmit({
      ticker: ticker.trim().toUpperCase(),
      date,
    });
  };

  const getRecommendationStyle = (rec: string) => {
    const r = rec ? rec.toUpperCase() : "HOLD";
    if (r === "STRONG BUY" || r === "강력 매수" || r === "강력매수") {
      return { color: "#00e676", backgroundColor: "rgba(0, 230, 118, 0.15)", border: "1px solid rgba(0, 230, 118, 0.3)" };
    }
    if (r === "BUY" || r === "매수") {
      return { color: "var(--accent-bull)", backgroundColor: "var(--accent-bull-glow)", border: "1px solid var(--accent-bull-glow)" };
    }
    if (r === "OVERWEIGHT" || r === "비중확대" || r === "비중 확대" || r === "매수 대기" || r === "매수대기") {
      return { color: "#81c784", backgroundColor: "rgba(129, 199, 132, 0.12)", border: "1px solid rgba(129, 199, 132, 0.25)" };
    }
    if (r === "UNDERWEIGHT" || r === "비중축소" || r === "비중 축소") {
      return { color: "#e57373", backgroundColor: "rgba(229, 115, 115, 0.12)", border: "1px solid rgba(229, 115, 115, 0.25)" };
    }
    if (r === "SELL" || r === "매도") {
      return { color: "var(--accent-bear)", backgroundColor: "var(--accent-bear-glow)", border: "1px solid var(--accent-bear-glow)" };
    }
    return { color: "var(--accent-hold)", backgroundColor: "var(--accent-hold-glow)", border: "1px solid var(--accent-hold-glow)" };
  };

  const getStatusStyle = (status: string) => {
    if (status === "COMPLETED") return { color: "var(--accent-bull)" };
    if (status === "FAILED") return { color: "var(--accent-bear)" };
    if (status === "CANCELLED") return { color: "var(--accent-hold)" };
    if (status === "RUNNING") return { color: "var(--accent-blue)" };
    return { color: "var(--text-secondary)" };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", height: "100%", overflowY: "hidden" }}>
      {/* 1. Simulation Parameter Form */}
      <div className="panel" style={{ flexShrink: 0, padding: "12px" }}>
        <h2 style={{ fontSize: "14px", marginBottom: "12px", display: "flex", alignItems: "center", gap: "6px", fontWeight: "700" }}>
          <PlusCircle size={16} color="var(--accent-blue)" />
          분석 파라미터 입력
        </h2>
        
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "500" }}>주식 티커 (Ticker)</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="예: AAPL, NVDA, TSLA"
              disabled={isLoading}
              style={{ padding: "6px 10px", fontSize: "12.5px" }}
              required
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "500" }}>시뮬레이션 날짜 (YYYY-MM-DD)</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={isLoading}
              style={{ padding: "5px 10px", fontSize: "12.5px" }}
              required
            />
          </div>

          <button 
            type="submit" 
            disabled={isLoading} 
            style={{ 
              marginTop: "4px", 
              padding: "8px", 
              fontSize: "12.5px", 
              display: "flex", 
              justifyContent: "center", 
              alignItems: "center", 
              gap: "6px",
              backgroundColor: "var(--accent-blue)"
            }}
          >
            {isLoading ? (
              <>
                <span className="pulse-animation" style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "white", display: "inline-block" }} />
                연산 작동 중...
              </>
            ) : "분석 시뮬레이션 시작"}
          </button>
        </form>
      </div>

      {/* 2. Run History List */}
      <div className="panel" style={{ flex: 1, overflowY: "hidden", display: "flex", flexDirection: "column", padding: "12px" }}>
        <h2 style={{ fontSize: "14px", marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, fontWeight: "700" }}>
          <Database size={16} color="var(--accent-blue)" />
          시뮬레이션 목록 ({history.length})
        </h2>

        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px", paddingRight: "2px" }}>
          {history.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "11px", textAlign: "center", marginTop: "20px" }}>실행 이력이 존재하지 않습니다.</p>
          ) : (
            history.map((item) => {
              const isActive = item.id === activeRunId;
              const recStyle = getRecommendationStyle(item.recommendation);
              const isProcessing = item.status === "RUNNING" || item.status === "PENDING";
              
              return (
                <div
                  key={item.id}
                  onClick={() => onSelectRun(item.id)}
                  style={{
                    backgroundColor: isActive ? "#242a37" : "#1e222d",
                    border: isActive ? "1px solid var(--accent-blue)" : "1px solid var(--border-color)",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px"
                  }}
                  className="card-hover-effect"
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: "bold", fontSize: "13px", color: isActive ? "var(--accent-blue)" : "var(--text-primary)" }}>
                      {item.ticker} ({item.trade_date})
                    </span>
                    
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {item.status === "COMPLETED" ? (
                        <span style={{
                          fontSize: "8.5px",
                          fontWeight: "bold",
                          padding: "1px 5px",
                          borderRadius: "3px",
                          ...recStyle
                        }}>
                          {item.recommendation}
                        </span>
                      ) : (
                        <span style={{ fontSize: "10.5px", fontWeight: "600", ...getStatusStyle(item.status) }}>
                          {item.status === "RUNNING" ? `${Math.min(100, Math.max(0, item.progress)).toFixed(0)}%` : 
                           item.status === "PENDING" ? "대기 중" :
                           item.status === "CANCELLED" ? "취소됨" : item.status}
                        </span>
                      )}

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteRun(item.id);
                        }}
                        style={{
                          background: "none",
                          border: "none",
                          padding: "3px",
                          cursor: "pointer",
                          color: isProcessing ? "var(--accent-bear)" : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          borderRadius: "4px",
                          transition: "color 0.2s ease",
                          height: "auto",
                          width: "auto",
                          transform: "none"
                        }}
                        title={isProcessing ? "작업 취소" : "기록 삭제"}
                      >
                        {isProcessing ? <X size={12} /> : <Trash2 size={12} />}
                      </button>
                    </div>
                  </div>
                  
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10.5px", color: "var(--text-secondary)" }}>
                    <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "120px" }}>{item.current_step}</span>
                    <span>{new Date(item.created_at).toLocaleDateString([], { month: "2-digit", day: "2-digit" })}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
