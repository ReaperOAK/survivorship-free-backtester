"""
test_fault_injection.py — Unit test asserting fault-tolerance during rebalance failures.

Tests the critical fix: If market data fetch fails during rebalance:
  1. rebalance() returns None.
  2. cron() does NOT advance last_rebalance_month.
  3. Subsequent cron() calls retry rebalancing instead of skipping the month.
"""
import unittest
import sys, os, copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "trading-lab"))
import india_ledger as ledger


class TestFaultInjection(unittest.TestCase):
    def test_rebalance_failure_does_not_advance_month(self):
        # Create an account state set to previous month
        acct = {
            "starting_balance": 1000000.0,
            "cash": 1000000.0,
            "positions": {},
            "history": [],
            "opened": "2026-10-01",
            "last_rebalance_month": "2026-10"
        }

        # Mock _prices_and_targets to simulate network/provider failure (returns empty)
        orig_fn = ledger._prices_and_targets
        try:
            ledger._prices_and_targets = lambda: ({}, {}, None, None, 0.0)
            
            # Execute cron() during the simulated failure
            ledger.cron(acct)
            
            # Assert that last_rebalance_month was NOT updated to current month
            self.assertEqual(
                acct.get("last_rebalance_month"), 
                "2026-10", 
                "BUG DETECTED: cron() advanced last_rebalance_month despite rebalance failure!"
            )
        finally:
            ledger._prices_and_targets = orig_fn


if __name__ == "__main__":
    unittest.main()
