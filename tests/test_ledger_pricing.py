"""
test_ledger_pricing.py — Unit test using standard library unittest to assert fail-loudly behavior.
"""
import unittest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-lab"))
import india_ledger as ledger


class TestLedgerPricing(unittest.TestCase):
    def test_missing_price_raises_runtime_error(self):
        acct = {
            "starting_balance": 100000.0,
            "cash": 50000.0,
            "positions": {
                "NONEXISTENT_SYMBOL": {
                    "qty": 10,
                    "avg_price": 500.0,
                    "entry_date": "2026-01-01"
                }
            }
        }
        prices = {"RELIANCE": 2500.0}
        with self.assertRaises(RuntimeError) as ctx:
            ledger.equity(acct, prices)
        
        self.assertIn("No market price found for held symbol 'NONEXISTENT_SYMBOL'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
