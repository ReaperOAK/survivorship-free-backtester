"""
platform_client.py — thin wrapper for the ai4trade.ai (AI-Trader) paper API.

SAFETY: constructing this client and reading data is harmless. The only methods
that change external state are register(), login(), and submit_trade(). Nothing
here runs on import; a human must call those explicitly. Token is cached at
~/.vibe-trading/ai4trade_token.json (chmod 600).

Endpoints per skills/ai4trade/SKILL.md. All trades are SIMULATED ($100k paper).
"""
from __future__ import annotations
import os, json, stat
import httpx

BASE = "https://ai4trade.ai/api"
TOKEN_PATH = os.path.expanduser("~/.vibe-trading/ai4trade_token.json")


class AI4Trade:
    def __init__(self, token: str | None = None, timeout: float = 30.0):
        self.token = token or self._load_token()
        self.http = httpx.Client(timeout=timeout)

    # --- token persistence ---
    def _load_token(self):
        if os.path.exists(TOKEN_PATH):
            try:
                return json.load(open(TOKEN_PATH)).get("token")
            except Exception:
                return None
        return None

    def _save_token(self, token, agent_id=None, name=None):
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        json.dump({"token": token, "agent_id": agent_id, "name": name}, open(TOKEN_PATH, "w"))
        os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600
        self.token = token

    @property
    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # --- account lifecycle (STATE-CHANGING) ---
    def register(self, name, email, password):
        r = self.http.post(f"{BASE}/claw/agents/selfRegister",
                           json={"name": name, "email": email, "password": password})
        d = r.json()
        if d.get("token"):
            self._save_token(d["token"], d.get("agent_id"), d.get("name"))
        return d

    def login(self, email, password):
        r = self.http.post(f"{BASE}/claw/agents/login", json={"email": email, "password": password})
        d = r.json()
        if d.get("token"):
            self._save_token(d["token"], d.get("agent_id"), d.get("name"))
        return d

    # --- reads (safe) ---
    def me(self):
        return self.http.get(f"{BASE}/claw/agents/me", headers=self._auth).json()

    def positions(self):
        return self.http.get(f"{BASE}/positions", headers=self._auth).json()

    def signal_feed(self, limit=20, **params):
        params["limit"] = limit
        return self.http.get(f"{BASE}/signals/feed", headers=self._auth, params=params).json()

    def heartbeat(self):
        return self.http.post(f"{BASE}/claw/agents/heartbeat", headers=self._auth).json()

    # --- trade (STATE-CHANGING) ---
    def submit_trade(self, market, action, symbol, quantity, price=0, executed_at="now", content=None):
        """market: us-stock|crypto|polymarket ; action: buy|sell|short|cover.
        price=0 + executed_at='now' -> platform auto-quotes current price."""
        body = {"market": market, "action": action, "symbol": symbol,
                "price": price, "quantity": quantity, "executed_at": executed_at}
        if content:
            body["content"] = content
        return self.http.post(f"{BASE}/signals/realtime", headers=self._auth, json=body).json()


if __name__ == "__main__":
    # read-only connectivity probe: does NOT register or trade
    import sys
    c = AI4Trade()
    if not c.token:
        print("No token cached. Registration required (needs explicit go-ahead).")
        # public read: signal feed works without auth
        try:
            feed = c.signal_feed(limit=3)
            n = len(feed.get("signals", []))
            print(f"Public API reachable: signal feed returned {n} signals.")
        except Exception as e:
            print(f"API probe failed: {e}")
        sys.exit(0)
    print("Token cached. Account:", c.me())
