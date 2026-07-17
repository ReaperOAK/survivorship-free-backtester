# Local venv patches (not upstream)

These are applied to the installed `vibe-trading-ai` inside `.venv/`. They are
LOST if the package is reinstalled/upgraded — re-apply after any `pip install -U`.

## 1. OpenRouter request-level model fallback
- **File:** `.venv/lib/python3.12/site-packages/src/providers/llm.py` (in `build_llm`)
- **Why:** Vibe-Trading's swarm uses a single `LANGCHAIN_MODEL_NAME`, so a rate-limited
  free model (429) kills the whole run with no fallback. Free-tier models throttle constantly.
- **What:** When `provider=openrouter`, forward `VIBE_FALLBACK_MODELS` (env) as the
  OpenRouter `{"models":[...]}` request array (capped at 3) via `extra_body`, so every
  call — including each swarm worker — falls over to the next free model on error.
- **Marker:** search for `[LOCAL PATCH]` in that file.

## Operational note
- Free-model swarms should also run with `SWARM_MAX_WORKERS=1` (serial) to avoid
  self-inflicted parallel rate-limiting.
