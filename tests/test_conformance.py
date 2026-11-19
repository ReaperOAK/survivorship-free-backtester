"""
test_conformance.py — Unit test asserting 100% conformance between backtest engine and live ledger.
"""
import unittest
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-lab"))
import signal_engine as se

ACCOUNT = os.path.expanduser("~/.vibe-trading/india_account.json")


class TestEngineLedgerConformance(unittest.TestCase):
    def test_engine_matches_ledger_positions(self):
        if not os.path.exists(ACCOUNT):
            self.skipTest(f"Account {ACCOUNT} does not exist on this machine")

        with open(ACCOUNT) as f:
            acct = json.load(f)

        sig = se.current_signal("nifty500", "ensemble_regime", 20)
        picks = sig["picks"]
        weights = {s: float(picks.loc[s, "weight"]) for s in picks.index}
        prices = {s: float(picks.loc[s, "price"]) for s in picks.index}

        total_cap = float(acct["starting_balance"])
        COST = 0.002

        engine_positions = {}
        cash = total_cap
        for s in sorted(weights, key=lambda sym: weights[sym] * total_cap, reverse=True):
            px = prices[s]
            target_dlrs = weights[s] * total_cap
            qty = int(target_dlrs // px)
            spend = qty * px * (1 + COST)
            if cash >= spend and qty > 0:
                cash -= spend
                engine_positions[s] = qty

        ledger_positions = {s: p["qty"] for s, p in acct["positions"].items()}

        self.assertEqual(
            set(engine_positions.keys()), 
            set(ledger_positions.keys()), 
            "Mismatch in held symbol set between engine and ledger"
        )
        for s, qty in engine_positions.items():
            self.assertEqual(
                qty, 
                ledger_positions[s], 
                f"Share count mismatch for {s}: engine={qty}, ledger={ledger_positions[s]}"
            )


if __name__ == "__main__":
    unittest.main()
