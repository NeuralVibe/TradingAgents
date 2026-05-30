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
  onSubmit: (data: { ticker: string; date: string; provider: string; model: string; debateRounds: number }) => void;
  isLoading: boolean;
  history: RunResponse[];
  activeRunId: string | null;
  onSelectRun: (id: string) => void;
  onDeleteRun: (id: string, event: React.MouseEvent) => void;
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
  const [provider, setProvider] = useState("local");
  const [model, setModel] = useState("qwen3.6-27b-uncensored-heretic-v2-native-mtp-preserved");
  const [debateRounds, setDebateRounds] = useState(1);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker || !date) return;
    onSubmit({
      ticker: ticker.trim().toUpperCase(),
      date,
      provider,
      model,
      debateRounds,
    });
  };

  const getRecommendationStyle = (rec: string) => {
    if (rec === "BUY") return { color: "var(--accent-bull)", backgroundColor: "var(--accent-bull-glow)" };
    if (rec === "SELL") return { color: "var(--accent-bear)", backgroundColor: "var(--accent-bear-glow)" };
    return { color: "var(--accent-hold)", backgroundColor: "var(--accent-hold-glow)" };
  };

  const getStatusStyle = (status: string) => {
    if (status === "COMPLETED") return { color: "var(--accent-bull)" };
    if (status === "FAILED") return { color: "var(--accent-bear)" };
    if (status === "CANCELLED") return { color: "var(--accent-hold)" };
    if (status === "RUNNING") return { color: "var(--accent-blue)" };
    return { color: "var(--text-secondary)" };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto" }}>
      {/* 1. Simulation Parameter Form */}
      <div className="panel" style={{ flexShrink: 0 }}>
        <h2 style={{ fontSize: "16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <PlusCircle size={20} color="var(--accent-blue)" />
          분석 파라미터 입력
        </h2>
        
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>주식 티커 (Ticker)</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="예: AAPL, TSLA, NVDA"
              disabled={isLoading}
              required
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>시뮬레이션 분석 날짜 (YYYY-MM-DD)</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>LLM 제공자 (Provider)</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={isLoading}>
              <option value="local">Local LLM (LMStudio)</option>
              <option value="openai">OpenAI (API Key 필요)</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>분석 LLM 모델 (Model)</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="모델 식별자 입력"
              disabled={isLoading}
              required
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>끝장 토론 라운드 수 (Debate Rounds)</label>
            <select value={debateRounds} onChange={(e) => setDebateRounds(Number(e.target.value))} disabled={isLoading}>
              <option value={1}>1 라운드 (기본값)</option>
              <option value={2}>2 라운드 (심층 분석)</option>
              <option value={3}>3 라운드 (극한 논쟁)</option>
            </select>
          </div>

          <button type="submit" disabled={isLoading} style={{ marginTop: "8px", display: "flex", justifyContent: "center", alignItems: "center", gap: "6px" }}>
            {isLoading ? (
              <>
                <span className="pulse-animation" style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "white", display: "inline-block" }} />
                에이전트 분석 작동 중...
              </>
            ) : "멀티 에이전트 분석 시작"}
          </button>
        </form>
      </div>

      {/* 2. Run History List */}
      <div className="panel" style={{ flex: 1, overflowY: "hidden", display: "flex", flexDirection: "column" }}>
        <h2 style={{ fontSize: "16px", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
          <Database size={20} color="var(--accent-blue)" />
          이전 분석 시뮬레이션 목록 ({history.length})
        </h2>

        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
          {history.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "12px", textAlign: "center", marginTop: "20px" }}>실행 이력이 존재하지 않습니다.</p>
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
                    padding: "10px 12px",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px"
                  }}
                  className="card-hover-effect"
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: "bold", fontSize: "14px", color: isActive ? "var(--accent-blue)" : "var(--text-primary)" }}>
                      {item.ticker} ({item.trade_date})
                    </span>
                    
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {item.status === "COMPLETED" ? (
                        <span style={{
                          fontSize: "10px",
                          fontWeight: "bold",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          ...recStyle
                        }}>
                          {item.recommendation}
                        </span>
                      ) : (
                        <span style={{ fontSize: "11px", fontWeight: "600", ...getStatusStyle(item.status) }}>
                          {item.status === "RUNNING" ? `${Math.min(100, Math.max(0, item.progress)).toFixed(0)}%` : 
                           item.status === "PENDING" ? "대기 중" :
                           item.status === "CANCELLED" ? "취소됨" : item.status}
                        </span>
                      )}

                      {/* Cancel / Delete action icon */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteRun(item.id, e);
                        }}
                        style={{
                          background: "none",
                          border: "none",
                          padding: "4px",
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
                        {isProcessing ? <X size={14} /> : <Trash2 size={14} />}
                      </button>
                    </div>
                  </div>
                  
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-secondary)" }}>
                    <span>{item.current_step}</span>
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
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
