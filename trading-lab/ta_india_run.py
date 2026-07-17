"""
ta_india_run.py — run TradingAgents (multi-agent LLM) on an INDIAN stock,
wired to our free OpenRouter model. Proof-of-concept that it CAN analyze
Indian stocks (yfinance .NS data flows in). Minimal rounds to limit LLM calls.
"""
import os, sys

# load OpenRouter key from our env file
envp = os.path.expanduser("~/.vibe-trading/.env")
for line in open(envp):
    line = line.strip()
    if line.startswith("OPENROUTER_API_KEY="):
        key = line.split("=", 1)[1]
        os.environ["OPENAI_API_KEY"] = key
        os.environ["OPENROUTER_API_KEY"] = key

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "ollama"
config["backend_url"] = "http://127.0.0.1:11434/v1"   # local Ollama, no rate limits
config["deep_think_llm"] = "qwen2.5:7b-instruct"
config["quick_think_llm"] = "qwen2.5:7b-instruct"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
config["online_tools"] = True

ticker = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
date = sys.argv[2] if len(sys.argv) > 2 else "2025-06-30"
print(f"Analyzing {ticker} as of {date} with free model {config['deep_think_llm']}...\n", flush=True)

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate(ticker, date)
print("\n================ FINAL DECISION ================")
print(decision)
