import React, { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, createSeriesMarkers, LineStyle } from "lightweight-charts";
import type { IChartApi, ISeriesApi, IPriceLine } from "lightweight-charts";
import { TrendingUp, Maximize2, Minimize2 } from "lucide-react";

interface MarketDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ChartPanelProps {
  ticker: string;
  data: MarketDataPoint[];
  indicators: any;
  tradeDate?: string;
  recommendation?: string;
  decisionText?: string | null;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

// 퀀트 리포트 텍스트 내에서 익절/손절/진입 가격을 정밀 파싱하고 Fallback을 적용하는 헬퍼 함수
interface PriceLevels {
  entry: number;
  target: number;
  stopLoss: number;
}

const parseQuantPriceLevels = (decisionText: string | null | undefined, fallbackPrice: number): PriceLevels => {
  let entry = fallbackPrice;
  let target = fallbackPrice * 1.15; // 기본 익절가: +15%
  let stopLoss = fallbackPrice * 0.95; // 기본 손절가: -5%
  
  if (!decisionText) {
    return { entry, target, stopLoss };
  }
  
  // 가격 정규식 (예: $150.25, 150.25, 150달러, 150,000원 등)
  const priceRegex = /(?:\$|₩)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:달러|원)?/i;
  
  const lines = decisionText.split("\n");
  for (const line of lines) {
    const lowerLine = line.toLowerCase();
    
    // 1. 매수진입가 파싱
    if (lowerLine.includes("매수가") || lowerLine.includes("진입") || lowerLine.includes("entry") || lowerLine.includes("구매")) {
      const match = line.match(priceRegex);
      if (match) {
        const val = parseFloat(match[1].replace(/,/g, ""));
        if (!isNaN(val) && val > 0) entry = val;
      }
    }
    // 2. 익절목표가 파싱
    if (lowerLine.includes("목표가") || lowerLine.includes("익절") || lowerLine.includes("target") || lowerLine.includes("매도가")) {
      const match = line.match(priceRegex);
      if (match) {
        const val = parseFloat(match[1].replace(/,/g, ""));
        if (!isNaN(val) && val > 0) target = val;
      }
    }
    // 3. 손절라인 파싱
    if (lowerLine.includes("손절") || lowerLine.includes("stop loss") || lowerLine.includes("stop-loss") || lowerLine.includes("손절라인")) {
      const match = line.match(priceRegex);
      if (match) {
        const val = parseFloat(match[1].replace(/,/g, ""));
        if (!isNaN(val) && val > 0) stopLoss = val;
      }
    }
  }
  
  // 합리적 보정: 가격이 너무 터무니없게 잡혔을 경우에 대한 예외 처리
  if (entry <= 0) entry = fallbackPrice;
  if (target <= entry) target = entry * 1.15;
  if (stopLoss >= entry) stopLoss = entry * 0.95;
  
  return { entry, target, stopLoss };
};

export const ChartPanel: React.FC<ChartPanelProps> = ({
  ticker,
  data,
  indicators,
  tradeDate,
  recommendation,
  decisionText,
  isExpanded = false,
  onToggleExpand,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  
  const [chart, setChart] = useState<IChartApi | null>(null);
  const [rsiChart, setRsiChart] = useState<IChartApi | null>(null);
  
  const [showSMA50, setShowSMA50] = useState(true);
  const [showSMA200, setShowSMA200] = useState(false);
  const [showEMA10, setShowEMA10] = useState(true);
  const [activeIndicatorPane, setActiveIndicatorPane] = useState<"RSI" | "MACD" | "NONE">("RSI");

  // Keep references to series to remove/update them
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const sma50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema10SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdLineSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersPluginRef = useRef<any>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  const mainChartHeight = isExpanded ? 550 : 310;
  const indChartHeight = isExpanded ? 180 : 110;

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    // 1. Create Main Candlestick Chart
    const mainChart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: mainChartHeight,
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

    const candleSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: "#00c076",
      downColor: "#ff3e5b",
      borderUpColor: "#00c076",
      borderDownColor: "#ff3e5b",
      wickUpColor: "#00c076",
      wickDownColor: "#ff3e5b",
    });

    candleSeriesRef.current = candleSeries;

    // Add Moving Average Series
    sma50SeriesRef.current = mainChart.addSeries(LineSeries, { color: "#2962ff", lineWidth: 2, title: "SMA 50" });
    sma200SeriesRef.current = mainChart.addSeries(LineSeries, { color: "#f3ba2f", lineWidth: 2, title: "SMA 200" });
    ema10SeriesRef.current = mainChart.addSeries(LineSeries, { color: "#ab47bc", lineWidth: 2, title: "EMA 10" });

    // 2. Create RSI / Indicator Pane
    if (!rsiContainerRef.current) return;
    const indChart = createChart(rsiContainerRef.current, {
      width: rsiContainerRef.current.clientWidth,
      height: indChartHeight,
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
        visible: true,
      },
    });

    // Add RSI Series
    rsiSeriesRef.current = indChart.addSeries(LineSeries, { color: "#ab47bc", lineWidth: 2, title: "RSI (14)" });
    
    // Add MACD Series
    macdLineSeriesRef.current = indChart.addSeries(LineSeries, { color: "#2962ff", lineWidth: 2, title: "MACD" });
    macdSignalSeriesRef.current = indChart.addSeries(LineSeries, { color: "#f3ba2f", lineWidth: 2, title: "Signal" });
    macdHistSeriesRef.current = indChart.addSeries(HistogramSeries, {
      color: "#00c076",
      title: "Histogram"
    });

    setChart(mainChart);
    setRsiChart(indChart);

    // Sync Time Scales between main chart and indicator chart safely with try-catch checks
    mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      try {
        if (range && indChart) {
          indChart.timeScale().setVisibleRange(range);
        }
      } catch (e) {
        // Suppress timescale mapping errors during initialization
      }
    });
    indChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      try {
        if (range && mainChart) {
          mainChart.timeScale().setVisibleRange(range);
        }
      } catch (e) {
        // Suppress timescale mapping errors during initialization
      }
    });

    // Resize Handler
    const handleResize = () => {
      if (chartContainerRef.current) mainChart.resize(chartContainerRef.current.clientWidth, mainChartHeight);
      if (rsiContainerRef.current) indChart.resize(rsiContainerRef.current.clientWidth, indChartHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      mainChart.remove();
      indChart.remove();
      markersPluginRef.current = null;
    };
  }, [data, mainChartHeight, indChartHeight]);

  // Load and update data in Series
  useEffect(() => {
    if (!chart || data.length === 0 || !indicators) return;

    // Convert data to Lightweight Charts format, filtering out null/NaN and sorting chronologically
    const formattedData = data
      .filter((d) => d && d.date && d.open !== null && d.high !== null && d.low !== null && d.close !== null)
      .map((d) => ({
        time: d.date,
        open: Number(d.open),
        high: Number(d.high),
        low: Number(d.low),
        close: Number(d.close),
      }))
      .sort((a, b) => a.time.localeCompare(b.time));

    // Deduplicate by time to guarantee strict uniqueness
    const uniqueData: typeof formattedData = [];
    const seenDates = new Set();
    for (const pt of formattedData) {
      if (!seenDates.has(pt.time)) {
        seenDates.add(pt.time);
        uniqueData.push(pt);
      }
    }

    candleSeriesRef.current?.setData(uniqueData);

    // Initialize markers plugin in v5 format AFTER data is set on series to prevent Value is null crash
    if (candleSeriesRef.current && !markersPluginRef.current && uniqueData.length > 0) {
      markersPluginRef.current = createSeriesMarkers(candleSeriesRef.current, []);
    }

    // SMAs and EMAs
    if (indicators.sma_50) {
      const sma50Data = Object.entries(indicators.sma_50)
        .filter(([_, v]) => v !== null && v !== undefined && !isNaN(v as number))
        .map(([k, v]) => ({ time: k, value: Number(v) }))
        .sort((a, b) => a.time.localeCompare(b.time));
      sma50SeriesRef.current?.setData(showSMA50 ? sma50Data : []);
    }
    if (indicators.sma_200) {
      const sma200Data = Object.entries(indicators.sma_200)
        .filter(([_, v]) => v !== null && v !== undefined && !isNaN(v as number))
        .map(([k, v]) => ({ time: k, value: Number(v) }))
        .sort((a, b) => a.time.localeCompare(b.time));
      sma200SeriesRef.current?.setData(showSMA200 ? sma200Data : []);
    }
    if (indicators.ema_10) {
      const ema10Data = Object.entries(indicators.ema_10)
        .filter(([_, v]) => v !== null && v !== undefined && !isNaN(v as number))
        .map(([k, v]) => ({ time: k, value: Number(v) }))
        .sort((a, b) => a.time.localeCompare(b.time));
      ema10SeriesRef.current?.setData(showEMA10 ? ema10Data : []);
    }

    // Set markers on Candlestick Chart for Trade Date & Recommendations in v5 plugin format
    if (tradeDate && markersPluginRef.current) {
      const markers = [];
      const tradePoint = data.find((d) => d.date === tradeDate);
      
      if (tradePoint) {
        let markerColor = "#f3ba2f"; // HOLD
        let markerText = "HOLD";
        let markerType = "circle";
        let markerPosition = "aboveBar";

        if (recommendation === "BUY") {
          markerColor = "#00c076";
          markerText = "★ BUY 추천";
          markerType = "arrowUp";
          markerPosition = "belowBar";
        } else if (recommendation === "SELL") {
          markerColor = "#ff3e5b";
          markerText = "▼ SELL 추천";
          markerType = "arrowDown";
          markerPosition = "aboveBar";
        }

        markers.push({
          time: tradeDate,
          position: markerPosition as any,
          color: markerColor,
          shape: markerType as any,
          text: markerText,
          size: 1.5,
        });

        markersPluginRef.current.setMarkers(markers);
      } else {
        markersPluginRef.current.setMarkers([]);
      }
    } else if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers([]);
    }

    // 3중 퀀트 가격선 오버레이 (익절가, 매수가, 손절가 가로 점선) 추가
    if (candleSeriesRef.current) {
      // 1. 기존에 그려진 가격선 인스턴스 제거
      for (const line of priceLinesRef.current) {
        try {
          candleSeriesRef.current.removePriceLine(line);
        } catch (e) {
          // Fail silently
        }
      }
      priceLinesRef.current = [];

      // 2. 새로운 가격이 들어왔을 때 오버레이 생성
      if (tradeDate) {
        const tradePoint = data.find((d) => d.date === tradeDate);
        const fallbackPrice = tradePoint ? Number(tradePoint.close) : (data[data.length - 1] ? Number(data[data.length - 1].close) : 0);
        
        if (fallbackPrice > 0) {
          const { entry, target, stopLoss } = parseQuantPriceLevels(decisionText, fallbackPrice);

          // (1) 목표 익절가 라인 (Target Price - 초록)
          const targetLine = candleSeriesRef.current.createPriceLine({
            price: target,
            color: "#00c076",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `익절라인 (Target: $${target.toFixed(2)})`,
          });
          
          // (2) 매수진입가 라인 (Entry Price - 청색)
          const entryLine = candleSeriesRef.current.createPriceLine({
            price: entry,
            color: "#2962ff",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `매수진입가 (Entry: $${entry.toFixed(2)})`,
          });

          // (3) 손절기준가 라인 (Stop Loss - 적색)
          const stopLossLine = candleSeriesRef.current.createPriceLine({
            price: stopLoss,
            color: "#ff3e5b",
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `손절라인 (Stop Loss: $${stopLoss.toFixed(2)})`,
          });

          priceLinesRef.current = [targetLine, entryLine, stopLossLine];
        }
      }
    }

    // Fit main chart to data
    chart.timeScale().fitContent();

  }, [chart, data, indicators, showSMA50, showSMA200, showEMA10, tradeDate, recommendation, decisionText]);

  // Update RSI / MACD Indicators in the bottom chart
  useEffect(() => {
    if (!rsiChart || !indicators || data.length === 0) return;

    const rsiSeries = rsiSeriesRef.current;
    const macdLine = macdLineSeriesRef.current;
    const macdSignal = macdSignalSeriesRef.current;
    const macdHist = macdHistSeriesRef.current;

    // Reset all first
    rsiSeries?.setData([]);
    macdLine?.setData([]);
    macdSignal?.setData([]);
    macdHist?.setData([]);

    if (activeIndicatorPane === "RSI" && indicators.rsi) {
      const rsiData = Object.entries(indicators.rsi)
        .filter(([_, v]) => v !== null && v !== undefined && !isNaN(v as number))
        .map(([k, v]) => ({ time: k, value: Number(v) }))
        .sort((a, b) => a.time.localeCompare(b.time));
      rsiSeries?.setData(rsiData);
      
      // Auto scale
      rsiChart.timeScale().fitContent();
    } else if (activeIndicatorPane === "MACD" && indicators.macd) {
      const macdData = Object.entries(indicators.macd)
        .filter(([_, v]: any) => v && v.line !== null && v.signal !== null && v.histogram !== null)
        .map(([k, v]: any) => ({
          time: k,
          line: Number(v.line),
          signal: Number(v.signal),
          histogram: Number(v.histogram)
        }))
        .sort((a, b) => a.time.localeCompare(b.time));

      const lineData = macdData.map(d => ({ time: d.time, value: d.line }));
      const sigData = macdData.map(d => ({ time: d.time, value: d.signal }));
      const histData = macdData.map(d => ({
        time: d.time,
        value: d.histogram,
        color: d.histogram >= 0 ? "#00c076" : "#ff3e5b"
      }));

      macdLine?.setData(lineData);
      macdSignal?.setData(sigData);
      macdHist?.setData(histData);

      // Auto scale
      rsiChart.timeScale().fitContent();
    }
  }, [rsiChart, indicators, data, activeIndicatorPane]);

  return (
    <div className="panel" style={{ flex: 1, minHeight: isExpanded ? "calc(100vh - 100px)" : "480px", height: isExpanded ? "calc(100vh - 100px)" : "auto", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <TrendingUp size={20} color="var(--accent-blue)" />
          <h2 style={{ margin: 0, fontSize: "16px" }}>{ticker} 실시간 주가 차트 및 보조지표</h2>
        </div>
        
        {/* Toggle Overlays & Expand Controls */}
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          <button
            onClick={() => setShowSMA50(!showSMA50)}
            className="tab-btn"
            style={{
              padding: "4px 8px",
              fontSize: "11px",
              background: showSMA50 ? "rgba(41, 98, 255, 0.2)" : "none",
              border: "1px solid var(--border-color)",
              color: showSMA50 ? "var(--accent-blue)" : "var(--text-secondary)",
              borderRadius: "4px",
              height: "auto",
              transform: "none",
            }}
          >
            SMA 50
          </button>
          <button
            onClick={() => setShowSMA200(!showSMA200)}
            className="tab-btn"
            style={{
              padding: "4px 8px",
              fontSize: "11px",
              background: showSMA200 ? "rgba(243, 186, 47, 0.2)" : "none",
              border: "1px solid var(--border-color)",
              color: showSMA200 ? "var(--accent-hold)" : "var(--text-secondary)",
              borderRadius: "4px",
              height: "auto",
              transform: "none",
            }}
          >
            SMA 200
          </button>
          <button
            onClick={() => setShowEMA10(!showEMA10)}
            className="tab-btn"
            style={{
              padding: "4px 8px",
              fontSize: "11px",
              background: showEMA10 ? "rgba(171, 71, 188, 0.2)" : "none",
              border: "1px solid var(--border-color)",
              color: showEMA10 ? "var(--accent-purple)" : "var(--text-secondary)",
              borderRadius: "4px",
              height: "auto",
              transform: "none",
            }}
          >
            EMA 10
          </button>
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              className="tab-btn"
              style={{
                padding: "4px 10px",
                fontSize: "11px",
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

      {/* Main Candlestick Chart Area */}
      <div ref={chartContainerRef} style={{ width: "100%", borderRadius: "4px", overflow: "hidden" }} />

      {/* Bottom Indicator Tab Selection */}
      <div style={{ display: "flex", gap: "8px", margin: "12px 0 6px 0", borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" }}>
        <button
          onClick={() => setActiveIndicatorPane("RSI")}
          style={{
            padding: "4px 10px",
            fontSize: "12px",
            background: activeIndicatorPane === "RSI" ? "rgba(41, 98, 255, 0.15)" : "none",
            color: activeIndicatorPane === "RSI" ? "var(--accent-blue)" : "var(--text-secondary)",
            border: "none",
            borderRadius: "4px",
            transform: "none",
          }}
        >
          RSI (상대강도지수)
        </button>
        <button
          onClick={() => setActiveIndicatorPane("MACD")}
          style={{
            padding: "4px 10px",
            fontSize: "12px",
            background: activeIndicatorPane === "MACD" ? "rgba(41, 98, 255, 0.15)" : "none",
            color: activeIndicatorPane === "MACD" ? "var(--accent-blue)" : "var(--text-secondary)",
            border: "none",
            borderRadius: "4px",
            transform: "none",
          }}
        >
          MACD (이동평균수렴확산)
        </button>
        <button
          onClick={() => setActiveIndicatorPane("NONE")}
          style={{
            padding: "4px 10px",
            fontSize: "12px",
            background: activeIndicatorPane === "NONE" ? "rgba(41, 98, 255, 0.15)" : "none",
            color: activeIndicatorPane === "NONE" ? "var(--accent-blue)" : "var(--text-secondary)",
            border: "none",
            borderRadius: "4px",
            transform: "none",
          }}
        >
          표시 안 함
        </button>
      </div>

      {/* Indicator Pane Area */}
      <div 
        ref={rsiContainerRef} 
        style={{ 
          width: "100%", 
          borderRadius: "4px", 
          overflow: "hidden", 
          display: activeIndicatorPane === "NONE" ? "none" : "block" 
        }} 
      />
    </div>
  );
};
