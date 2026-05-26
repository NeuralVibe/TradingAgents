import argparse
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Stock Trading Simulation")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker to analyze (e.g. AAPL, NVDA, TSLA)")
    parser.add_argument("--date", type=str, default="2026-05-25", help="Simulation date (YYYY-MM-DD)")
    parser.add_argument("--debug", action="store_true", help="Enable debug print outputs")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"Initializing Stock Trading Agents for: {args.ticker}")
    print(f"Simulation Date: {args.date}")
    print(f"LLM Provider: {DEFAULT_CONFIG.get('llm_provider')}")
    print(f"LLM Model: {DEFAULT_CONFIG.get('deep_think_llm')}")
    print(f"Backend URL: {DEFAULT_CONFIG.get('backend_url')}")
    print("=" * 60)
    
    config = DEFAULT_CONFIG.copy()
    
    # Initialize the Multi-Agent Trading Graph
    ta = TradingAgentsGraph(debug=args.debug, config=config)
    
    print("\nRunning multi-agent analysis and debate...")
    print("This might take a minute as agents process technical, fundamental, sentiment, and news data...")
    print("-" * 60)
    
    try:
        state, decision = ta.propagate(args.ticker, args.date)
        print("-" * 60)
        print("\n[Simulation Run Completed Successfully]")
        print("\n================ Final Trading Proposal ================")
        print(decision)
        print("========================================================")
    except Exception as e:
        import traceback
        print(f"\n[Error running simulation]: {str(e)}")
        traceback.print_exc()
        print("Please check your local LLM server status and Finnhub API Key.")

if __name__ == "__main__":
    main()
