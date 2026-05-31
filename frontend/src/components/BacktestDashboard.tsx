import React, { useState, useEffect, useRef } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import type { IChartApi } from "lightweight-charts";
import { 
    LineChart, 
    Play, 
    RefreshCw, 
    Download, 
    Award, 
    DollarSign, 
    Percent, 
    FileText, 
    BarChart3
} from "lucide-react";

interface BacktestDashboardProps {
    apiBase: string;
}

export const BacktestDashboard: React.FC<BacktestDashboardProps> = ({ apiBase }) => {
    // Sizing and form states
    const [tickersInput, setTickersInput] = useState("");
    const [startDate, setStartDate] = useState("2026-01-01");
    const [endDate, setEndDate] = useState("2026-05-31");
    const [initialCapital, setInitialCapital] = useState(100000);
    const [sizingMode, setSizingMode] = useState<"confidence" | "fixed">("confidence");
    const [slippage, setSlippage] = useState(0.0005);
    
    // Sub-view tab
    const [dashboardTab, setDashboardTab] = useState<"backtest" | "ticker_perf" | "history">("backtest");

    // Dynamic data states
    const [backtestResult, setBacktestResult] = useState<any | null>(null);
    const [backtestLoading, setBacktestLoading] = useState(false);
    
    const [overallSummary, setOverallSummary] = useState<any | null>(null);
    const [tickerPerfList, setTickerPerfList] = useState<any[]>([]);
    const [decisionsHistory, setDecisionsHistory] = useState<any[]>([]);
    const [statsLoading, setStatsLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);

    // Chart ref
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);
    const portfolioSeriesRef = useRef<any>(null);
    const benchmarkSeriesRef = useRef<any>(null);

    useEffect(() => {
        loadOverallStats();
    }, []);

    // Effect to initialize lightweight-charts when backtestResult is loaded
    useEffect(() => {
        if (!chartContainerRef.current || !backtestResult || backtestResult.equity_curve.length === 0) return;

        // Clean up previous chart if any
        if (chartInstance) {
            chartInstance.remove();
            setChartInstance(null);
        }

        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: 380,
            layout: {
                background: { color: "#161a22" },
                textColor: "#848e9c",
            },
            grid: {
                vertLines: { color: "#242a36" },
                horzLines: { color: "#242a36" },
            },
            timeScale: {
                borderColor: "#242a36",
            },
        });

        // Add line series
        const portfolioSeries = chart.addSeries(LineSeries, {
            color: "#2962ff",
            lineWidth: 3,
            title: "Portfolio Equity"
        });

        const benchmarkSeries = chart.addSeries(LineSeries, {
            color: "#f3ba2f",
            lineWidth: 2,
            title: "SPY Benchmark"
        });

        // Map equity curve data
        const initialVal = backtestResult.equity_curve[0].portfolio_value;
        const initialBench = backtestResult.equity_curve[0].benchmark_value;

        const portData = backtestResult.equity_curve.map((pt: any) => ({
            time: pt.date,
            value: pt.portfolio_value
        }));

        // Scale benchmark to match initial portfolio value for comparison
        const benchData = backtestResult.equity_curve.map((pt: any) => ({
            time: pt.date,
            value: pt.benchmark_value * (initialVal / initialBench)
        }));

        portfolioSeries.setData(portData);
        benchmarkSeries.setData(benchData);

        portfolioSeriesRef.current = portfolioSeries;
        benchmarkSeriesRef.current = benchmarkSeries;
        setChartInstance(chart);

        chart.timeScale().fitContent();

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.resize(chartContainerRef.current.clientWidth, 380);
            }
        };
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
            chart.remove();
        };
    }, [backtestResult]);

    const loadOverallStats = async () => {
        setStatsLoading(true);
        try {
            // Load overall database statistics
            const summaryRes = await fetch(`${apiBase}/performance/summary`);
            if (summaryRes.ok) {
                const summaryData = await summaryRes.json();
                setOverallSummary(summaryData);
            }

            // Load performance by ticker
            const tickerRes = await fetch(`${apiBase}/performance/by-ticker`);
            if (tickerRes.ok) {
                const tickerData = await tickerRes.json();
                setTickerPerfList(tickerData);
            }

            // Load stored decisions list
            const decsRes = await fetch(`${apiBase}/performance/decisions?limit=100`);
            if (decsRes.ok) {
                const decsData = await decsRes.json();
                setDecisionsHistory(decsData);
            }
        } catch (err) {
            console.error("Error loading performance stats:", err);
        } finally {
            setStatsLoading(false);
        }
    };

    const handleRunBacktest = async (e: React.FormEvent) => {
        e.preventDefault();
        setBacktestLoading(true);
        setBacktestResult(null);

        // Process tickers input (comma separated)
        const tickers = tickersInput
            .split(",")
            .map((t) => t.trim().toUpperCase())
            .filter((t) => t.length > 0);

        try {
            const response = await fetch(`${apiBase}/performance/backtest`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tickers: tickers.length > 0 ? tickers : null,
                    start_date: startDate,
                    end_date: endDate,
                    initial_capital: initialCapital,
                    sizing_mode: sizingMode,
                    slippage: slippage
                })
            });

            if (!response.ok) {
                throw new Error("백테스트 시뮬레이션 계산에 실패했습니다.");
            }

            const data = await response.json();
            setBacktestResult(data);
        } catch (err: any) {
            alert(`백테스트 오류: ${err.message}`);
        } finally {
            setBacktestLoading(false);
        }
    };

    const handleSyncLogs = async () => {
        setSyncing(true);
        try {
            const res = await fetch(`${apiBase}/performance/sync`, { method: "POST" });
            if (!res.ok) throw new Error("동기화 작업 오류");
            const data = await res.json();
            
            alert(
                `[동기화 완료]\n` +
                `- 신규 데이터 생성: ${data.markdown_sync.synced_count}건\n` +
                `- 기존 데이터 갱신: ${data.markdown_sync.updated_count}건\n` +
                `- 주가 정보(Outcome) 업데이트: ${data.outcomes_resolved}건`
            );
            loadOverallStats();
        } catch (err: any) {
            alert(`동기화 실패: ${err.message}`);
        } finally {
            setSyncing(false);
        }
    };

    const handleExport = (format: "csv" | "parquet") => {
        window.open(`${apiBase}/performance/decisions/export?format=${format}`);
    };

    const formatPercent = (val: number) => {
        if (val === undefined || val === null) return "0.00%";
        const prefix = val >= 0 ? "+" : "";
        return `${prefix}${(val * 100).toFixed(2)}%`;
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto", padding: "8px" }}>
            {/* Top Toolbar: Stats Refresh & sync */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "var(--bg-panel)", border: "1px solid var(--border-color)", padding: "12px 16px", borderRadius: "8px", flexShrink: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <BarChart3 size={20} color="var(--accent-blue)" />
                    <h2 style={{ fontSize: "16px", margin: 0, fontWeight: "700" }}>에이전트 트레이딩 성과 및 포트폴리오 백테스트</h2>
                </div>
                
                <div style={{ display: "flex", gap: "8px" }}>
                    <button 
                        onClick={handleSyncLogs} 
                        disabled={syncing}
                        style={{ 
                            fontSize: "12px", 
                            padding: "6px 12px", 
                            background: "rgba(0, 192, 118, 0.15)", 
                            color: "var(--accent-bull)", 
                            border: "1px solid var(--accent-bull)",
                            borderRadius: "4px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px"
                        }}
                    >
                        <RefreshCw size={13} className={syncing ? "pulse-animation" : ""} />
                        {syncing ? "로그 동기화 중..." : "Markdown 로그 동기화"}
                    </button>
                    <button 
                        onClick={loadOverallStats} 
                        disabled={statsLoading}
                        style={{ 
                            fontSize: "12px", 
                            padding: "6px 12px", 
                            background: "rgba(41, 98, 255, 0.15)", 
                            color: "var(--accent-blue)", 
                            border: "1px solid var(--accent-blue)",
                            borderRadius: "4px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px"
                        }}
                    >
                        <RefreshCw size={13} className={statsLoading ? "pulse-animation" : ""} />
                        성과 새로고침
                    </button>
                    <div style={{ position: "relative", display: "inline-block" }}>
                        <button 
                            onClick={() => handleExport("csv")}
                            style={{ 
                                fontSize: "12px", 
                                padding: "6px 12px", 
                                background: "#242a36", 
                                color: "var(--text-primary)", 
                                border: "1px solid var(--border-color)",
                                borderRadius: "4px",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px"
                            }}
                        >
                            <Download size={13} />
                            CSV 내보내기
                        </button>
                    </div>
                    <button 
                        onClick={() => handleExport("parquet")}
                        style={{ 
                            fontSize: "12px", 
                            padding: "6px 12px", 
                            background: "#242a36", 
                            color: "var(--text-primary)", 
                            border: "1px solid var(--border-color)",
                            borderRadius: "4px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px"
                        }}
                    >
                        <Download size={13} />
                        Parquet 내보내기
                    </button>
                </div>
            </div>

            {/* Overall Database Performance summary cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", flexShrink: 0 }}>
                <div className="card" style={{ display: "flex", flexDirection: "column", padding: "16px", background: "linear-gradient(135deg, #1e222d 0%, #161a22 100%)", borderLeft: "4px solid var(--accent-blue)", margin: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "bold" }}>총 체결 거래량</span>
                        <DollarSign size={16} color="var(--accent-blue)" />
                    </div>
                    <span style={{ fontSize: "22px", fontWeight: "800", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                        {overallSummary ? overallSummary.total_trades : "0"}건
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                        커버된 종목 수: {overallSummary ? overallSummary.total_tickers : "0"}개
                    </span>
                </div>

                <div className="card" style={{ display: "flex", flexDirection: "column", padding: "16px", background: "linear-gradient(135deg, #1e222d 0%, #161a22 100%)", borderLeft: "4px solid var(--accent-bull)", margin: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "bold" }}>평균 실현 수익률</span>
                        <Percent size={16} color="var(--accent-bull)" />
                    </div>
                    <span style={{ fontSize: "22px", fontWeight: "800", color: "var(--accent-bull)", fontFamily: "var(--font-mono)" }}>
                        {overallSummary ? formatPercent(overallSummary.avg_return) : "0.00%"}
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                        승률: {overallSummary ? (overallSummary.win_rate * 100).toFixed(1) : "0.0"}% ({overallSummary ? overallSummary.winning_trades : 0}승 / {overallSummary ? overallSummary.losing_trades : 0}패)
                    </span>
                </div>

                <div className="card" style={{ display: "flex", flexDirection: "column", padding: "16px", background: "linear-gradient(135deg, #1e222d 0%, #161a22 100%)", borderLeft: "4px solid #ab47bc", margin: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "bold" }}>평균 누적 초과수익 (Alpha)</span>
                        <Award size={16} color="#ab47bc" />
                    </div>
                    <span style={{ fontSize: "22px", fontWeight: "800", color: "#ab47bc", fontFamily: "var(--font-mono)" }}>
                        {overallSummary ? formatPercent(overallSummary.avg_alpha) : "0.00%"}
                    </span>
                    <span style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                        S&P 500 (SPY) 대비 벤치마크 초과 성과
                    </span>
                </div>
            </div>

            {/* Inner Tabs selection */}
            <div className="tab-container" style={{ margin: 0, flexShrink: 0 }}>
                <button 
                    onClick={() => setDashboardTab("backtest")} 
                    className={`tab-btn ${dashboardTab === "backtest" ? "active" : ""}`}
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                    <LineChart size={14} />
                    포트폴리오 백테스트 시뮬레이션
                </button>
                <button 
                    onClick={() => setDashboardTab("ticker_perf")} 
                    className={`tab-btn ${dashboardTab === "ticker_perf" ? "active" : ""}`}
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                    <BarChart3 size={14} />
                    종목별 성과 통계
                </button>
                <button 
                    onClick={() => setDashboardTab("history")} 
                    className={`tab-btn ${dashboardTab === "history" ? "active" : ""}`}
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                    <FileText size={14} />
                    의사결정 히스토리 정형 데이터 (SQLite)
                </button>
            </div>

            {/* Main Area based on Active Inner Tab */}
            <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: "0" }}>
                {dashboardTab === "backtest" && (
                    <div style={{ display: "grid", gridTemplateColumns: "350px 1fr", gap: "16px", height: "100%", minHeight: "0" }}>
                        {/* Left Side: Backtest parameters form */}
                        <div className="panel" style={{ overflowY: "auto", flexShrink: 0 }}>
                            <h3 style={{ fontSize: "14px", borderBottom: "1px solid var(--border-color)", paddingBottom: "10px", marginBottom: "16px" }}>백테스트 설정</h3>
                            
                            <form onSubmit={handleRunBacktest} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>대상 종목군 (콤마 분리, 빈 칸일 시 전체)</label>
                                    <input 
                                        type="text" 
                                        placeholder="예: AAPL, NVDA, TSLA" 
                                        value={tickersInput}
                                        onChange={(e) => setTickersInput(e.target.value)}
                                    />
                                </div>

                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                        <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>시작일</label>
                                        <input 
                                            type="date" 
                                            value={startDate}
                                            onChange={(e) => setStartDate(e.target.value)}
                                        />
                                    </div>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                        <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>종료일</label>
                                        <input 
                                            type="date" 
                                            value={endDate}
                                            onChange={(e) => setEndDate(e.target.value)}
                                        />
                                    </div>
                                </div>

                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>초기 자산 (USD)</label>
                                    <input 
                                        type="number" 
                                        value={initialCapital}
                                        onChange={(e) => setInitialCapital(Number(e.target.value))}
                                    />
                                </div>

                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>베팅 비중 모델 (Sizing Mode)</label>
                                    <select 
                                        value={sizingMode} 
                                        onChange={(e) => setSizingMode(e.target.value as any)}
                                    >
                                        <option value="confidence">에이전트 확신도 비중 (Confidence)</option>
                                        <option value="fixed">고정 자산 10% 배분 (Fixed)</option>
                                    </select>
                                </div>

                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    <label style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: "bold" }}>거래 수수료 및 슬리피지율 (%)</label>
                                    <input 
                                        type="number" 
                                        step="0.0001"
                                        value={slippage}
                                        onChange={(e) => setSlippage(Number(e.target.value))}
                                    />
                                </div>

                                <button 
                                    type="submit" 
                                    disabled={backtestLoading}
                                    style={{ 
                                        marginTop: "12px", 
                                        display: "flex", 
                                        alignItems: "center", 
                                        justifyContent: "center", 
                                        gap: "8px" 
                                    }}
                                >
                                    <Play size={14} />
                                    {backtestLoading ? "백테스트 연산 중..." : "벡터 백테스트 실행"}
                                </button>
                            </form>
                        </div>

                        {/* Right Side: Backtest Result Chart & stats */}
                        <div style={{ display: "flex", flexDirection: "column", gap: "16px", minWidth: "0" }}>
                            {backtestResult ? (
                                <div style={{ display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto" }}>
                                    {/* Stats grid */}
                                    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "10px", backgroundColor: "#161a22", border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>누적 수익률</span>
                                            <span style={{ fontSize: "16px", fontWeight: "bold", color: backtestResult.summary.cumulative_return >= 0 ? "var(--accent-bull)" : "var(--accent-bear)", fontFamily: "var(--font-mono)" }}>
                                                {formatPercent(backtestResult.summary.cumulative_return)}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>샤프 지수 (Sharpe)</span>
                                            <span style={{ fontSize: "16px", fontWeight: "bold", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                                                {backtestResult.summary.sharpe_ratio}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>최대 낙폭 (MDD)</span>
                                            <span style={{ fontSize: "16px", fontWeight: "bold", color: "var(--accent-bear)", fontFamily: "var(--font-mono)" }}>
                                                {formatPercent(backtestResult.summary.max_drawdown)}
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>승률</span>
                                            <span style={{ fontSize: "16px", fontWeight: "bold", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                                                {(backtestResult.summary.win_rate * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>초과 성과 (Alpha)</span>
                                            <span style={{ fontSize: "16px", fontWeight: "bold", color: "#ab47bc", fontFamily: "var(--font-mono)" }}>
                                                {formatPercent(backtestResult.summary.alpha)}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Chart area */}
                                    <div className="panel" style={{ padding: "16px", minHeight: "410px" }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                                            <h4 style={{ margin: 0, fontSize: "13px", fontWeight: "bold" }}>포트폴리오 누적 수익률 곡선 vs SPY 벤치마크</h4>
                                            <div style={{ display: "flex", gap: "10px", fontSize: "11px" }}>
                                                <span style={{ color: "#2962ff", display: "flex", alignItems: "center", gap: "4px" }}>
                                                    <span style={{ width: "8px", height: "8px", backgroundColor: "#2962ff", borderRadius: "50%", display: "inline-block" }} /> 포트폴리오
                                                </span>
                                                <span style={{ color: "#f3ba2f", display: "flex", alignItems: "center", gap: "4px" }}>
                                                    <span style={{ width: "8px", height: "8px", backgroundColor: "#f3ba2f", borderRadius: "50%", display: "inline-block" }} /> SPY Benchmark
                                                </span>
                                            </div>
                                        </div>
                                        <div ref={chartContainerRef} style={{ width: "100%" }} />
                                    </div>

                                    {/* Trades list */}
                                    <div className="panel" style={{ padding: "16px" }}>
                                        <h4 style={{ margin: "0 0 12px 0", fontSize: "13px", fontWeight: "bold" }}>백테스트 모의 체결 거래 내역</h4>
                                        <div style={{ overflowX: "auto" }}>
                                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                                                <thead>
                                                    <tr style={{ borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)" }}>
                                                        <th style={{ padding: "8px" }}>티커</th>
                                                        <th style={{ padding: "8px" }}>진입일</th>
                                                        <th style={{ padding: "8px" }}>진입가</th>
                                                        <th style={{ padding: "8px" }}>청산일</th>
                                                        <th style={{ padding: "8px" }}>청산가</th>
                                                        <th style={{ padding: "8px" }}>보유기간</th>
                                                        <th style={{ padding: "8px" }}>확신도</th>
                                                        <th style={{ padding: "8px" }}>수익률</th>
                                                        <th style={{ padding: "8px" }}>실현 손익</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {backtestResult.trades.map((t: any, index: number) => (
                                                        <tr key={index} style={{ borderBottom: "1px solid var(--border-color)" }}>
                                                            <td style={{ padding: "8px", fontWeight: "bold", color: "var(--accent-blue)" }}>{t.ticker}</td>
                                                            <td style={{ padding: "8px" }}>{t.entry_date}</td>
                                                            <td style={{ padding: "8px" }}>${t.entry_price.toFixed(2)}</td>
                                                            <td style={{ padding: "8px" }}>{t.exit_date}</td>
                                                            <td style={{ padding: "8px" }}>${t.exit_price.toFixed(2)}</td>
                                                            <td style={{ padding: "8px" }}>{t.horizon_days}일</td>
                                                            <td style={{ padding: "8px" }}>{(t.confidence * 100).toFixed(0)}%</td>
                                                            <td style={{ padding: "8px", fontWeight: "bold", color: t.raw_return >= 0 ? "var(--accent-bull)" : "var(--accent-bear)" }}>
                                                                {formatPercent(t.raw_return)}
                                                            </td>
                                                            <td style={{ padding: "8px", fontWeight: "bold", color: t.profit >= 0 ? "var(--accent-bull)" : "var(--accent-bear)", fontFamily: "var(--font-mono)" }}>
                                                                ${t.profit.toLocaleString()}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="panel" style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
                                    {backtestLoading ? (
                                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                                            <span className="pulse-animation" style={{ width: "24px", height: "24px", borderRadius: "50%", backgroundColor: "var(--accent-blue)", display: "inline-block" }} />
                                            <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>에이전트 트레이딩 시그널을 수집하여 포트폴리오를 시뮬레이션 중...</p>
                                        </div>
                                    ) : (
                                        <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>왼쪽 파널에서 백테스트 조건을 설정한 뒤 실행해 보세요.</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {dashboardTab === "ticker_perf" && (
                    <div className="panel" style={{ overflowY: "auto", flex: 1 }}>
                        <h3 style={{ fontSize: "14px", borderBottom: "1px solid var(--border-color)", paddingBottom: "10px", marginBottom: "16px" }}>종목별 실현 성과 순위</h3>
                        
                        <div style={{ overflowX: "auto" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                                <thead>
                                    <tr style={{ borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)" }}>
                                        <th style={{ padding: "12px 8px" }}>종목 (Ticker)</th>
                                        <th style={{ padding: "12px 8px" }}>총 거래수</th>
                                        <th style={{ padding: "12px 8px" }}>평균 실현 수익률</th>
                                        <th style={{ padding: "12px 8px" }}>단순 누적 수익률</th>
                                        <th style={{ padding: "12px 8px" }}>승률 (Win Rate)</th>
                                        <th style={{ padding: "12px 8px" }}>비고</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {tickerPerfList.map((tp, idx) => (
                                        <tr key={idx} style={{ borderBottom: "1px solid var(--border-color)", height: "45px" }}>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: "var(--accent-blue)" }}>{tp.ticker}</td>
                                            <td style={{ padding: "8px", fontFamily: "var(--font-mono)" }}>{tp.total_trades}회</td>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: tp.avg_return >= 0 ? "var(--accent-bull)" : "var(--accent-bear)" }}>
                                                {formatPercent(tp.avg_return)}
                                            </td>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: tp.cumulative_return >= 0 ? "var(--accent-bull)" : "var(--accent-bear)" }}>
                                                {formatPercent(tp.cumulative_return)}
                                            </td>
                                            <td style={{ padding: "8px" }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                                    <div style={{ width: "80px", height: "6px", backgroundColor: "#242a36", borderRadius: "3px", overflow: "hidden" }}>
                                                        <div style={{ width: `${tp.win_rate * 100}%`, height: "100%", backgroundColor: "var(--accent-bull)" }} />
                                                    </div>
                                                    <span>{(tp.win_rate * 100).toFixed(0)}%</span>
                                                </div>
                                            </td>
                                            <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px" }}>
                                                {tp.winning_trades}승 {tp.losing_trades}패
                                            </td>
                                        </tr>
                                    ))}
                                    {tickerPerfList.length === 0 && (
                                        <tr>
                                            <td colSpan={6} style={{ textAlign: "center", padding: "20px", color: "var(--text-secondary)" }}>종목별 실현 거래 데이터가 없습니다.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {dashboardTab === "history" && (
                    <div className="panel" style={{ overflowY: "auto", flex: 1 }}>
                        <h3 style={{ fontSize: "14px", borderBottom: "1px solid var(--border-color)", paddingBottom: "10px", marginBottom: "16px" }}>SQLite 실시간 의사결정 시그널 대장 (decisions Table)</h3>
                        
                        <div style={{ overflowX: "auto" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                                <thead>
                                    <tr style={{ borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)" }}>
                                        <th style={{ padding: "8px" }}>ID</th>
                                        <th style={{ padding: "8px" }}>종목</th>
                                        <th style={{ padding: "8px" }}>시뮬레이션 일자</th>
                                        <th style={{ padding: "8px" }}>시그널</th>
                                        <th style={{ padding: "8px" }}>확신도</th>
                                        <th style={{ padding: "8px" }}>보유기간</th>
                                        <th style={{ padding: "8px" }}>목표가</th>
                                        <th style={{ padding: "8px" }}>실현 수익률</th>
                                        <th style={{ padding: "8px" }}>초과 수익 (Alpha)</th>
                                        <th style={{ padding: "8px" }}>비고 / 사후 고찰 (Reflection)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {decisionsHistory.map((dec, idx) => (
                                        <tr key={idx} style={{ borderBottom: "1px solid var(--border-color)" }}>
                                            <td style={{ padding: "8px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>{dec.id}</td>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: "var(--text-primary)" }}>{dec.ticker}</td>
                                            <td style={{ padding: "8px" }}>{dec.decision_date}</td>
                                            <td style={{ padding: "8px" }}>
                                                <span style={{ 
                                                    padding: "2px 6px", 
                                                    borderRadius: "3px",
                                                    fontSize: "10px",
                                                    fontWeight: "bold",
                                                    backgroundColor: dec.side === "BUY" ? "rgba(0, 192, 118, 0.15)" : dec.side === "SELL" ? "rgba(255, 62, 91, 0.15)" : "rgba(243, 186, 47, 0.15)",
                                                    color: dec.side === "BUY" ? "var(--accent-bull)" : dec.side === "SELL" ? "var(--accent-bear)" : "var(--accent-hold)"
                                                }}>
                                                    {dec.side}
                                                </span>
                                            </td>
                                            <td style={{ padding: "8px" }}>{(dec.confidence * 100).toFixed(0)}%</td>
                                            <td style={{ padding: "8px" }}>{dec.horizon_days}d</td>
                                            <td style={{ padding: "8px" }}>{dec.price_target ? `$${dec.price_target.toFixed(2)}` : "N/A"}</td>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: dec.realized_return === null ? "var(--text-secondary)" : (dec.realized_return >= 0 ? "var(--accent-bull)" : "var(--accent-bear)") }}>
                                                {dec.realized_return === null ? "PENDING" : formatPercent(dec.realized_return)}
                                            </td>
                                            <td style={{ padding: "8px", fontWeight: "bold", color: dec.realized_alpha === null ? "var(--text-secondary)" : (dec.realized_alpha >= 0 ? "#ab47bc" : "var(--accent-bear)") }}>
                                                {dec.realized_alpha === null ? "PENDING" : formatPercent(dec.realized_alpha)}
                                            </td>
                                            <td style={{ padding: "8px", color: "var(--text-secondary)", fontSize: "11px", maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={dec.reflection}>
                                                {dec.reflection || "보유 및 주가 피드백 대기 중..."}
                                            </td>
                                        </tr>
                                    ))}
                                    {decisionsHistory.length === 0 && (
                                        <tr>
                                            <td colSpan={10} style={{ textAlign: "center", padding: "20px", color: "var(--text-secondary)" }}>DB에 저장된 의사결정 정보가 존재하지 않습니다.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
