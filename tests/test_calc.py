"""Tests for splitcore. Stdlib unittest so it runs with no pip install:

    python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splitcore.calc import per_person_totals, settle_up, split_item
from splitcore.model import AppState, Item, Person


def item(amount, participants, payer="a", split=None, iid="i1", desc="x"):
    return Item(iid, desc, amount, payer, participants,
                split or {"mode": "equal"})


class SplitItemTests(unittest.TestCase):
    def test_equal_exact(self):
        shares = split_item(item(900, ["a", "b", "c"]))
        self.assertEqual(shares, {"a": 300, "b": 300, "c": 300})

    def test_equal_penny_remainder_sums_exactly(self):
        shares = split_item(item(1000, ["a", "b", "c"]))
        # 1000 / 3 -> 334, 333, 333
        self.assertEqual(shares, {"a": 334, "b": 333, "c": 333})
        self.assertEqual(sum(shares.values()), 1000)

    def test_uneven_proportional_with_remainder(self):
        it = item(1000, ["a", "b"],
                  split={"mode": "uneven", "weights": {"a": 1, "b": 3}})
        shares = split_item(it)
        self.assertEqual(shares, {"a": 250, "b": 750})
        self.assertEqual(sum(shares.values()), 1000)

    def test_uneven_remainder_goes_to_largest_fraction(self):
        # 100 cents, weights 1:1:1 -> 33.33 each, remainder 1 penny.
        it = item(100, ["a", "b", "c"],
                  split={"mode": "uneven",
                         "weights": {"a": 1, "b": 1, "c": 1}})
        shares = split_item(it)
        self.assertEqual(sum(shares.values()), 100)
        self.assertEqual(sorted(shares.values()), [33, 33, 34])

    def test_uneven_all_zero_weights_falls_back_to_equal(self):
        it = item(300, ["a", "b", "c"],
                  split={"mode": "uneven",
                         "weights": {"a": 0, "b": 0, "c": 0}})
        shares = split_item(it)
        self.assertEqual(sum(shares.values()), 300)
        self.assertEqual(shares, {"a": 100, "b": 100, "c": 100})

    def test_no_participants(self):
        self.assertEqual(split_item(item(500, [])), {})


class TotalsTests(unittest.TestCase):
    def test_totals_across_multiple_items(self):
        state = AppState(
            people=[Person("a", "A"), Person("b", "B")],
            items=[
                item(1000, ["a", "b"], payer="a", iid="1"),
                item(500, ["b"], payer="b", iid="2"),
            ],
        )
        self.assertEqual(per_person_totals(state), {"a": 500, "b": 1000})

    def test_empty_state(self):
        self.assertEqual(per_person_totals(AppState()), {})
        self.assertEqual(settle_up(AppState()), [])


class SettleUpTests(unittest.TestCase):
    def test_multi_payer_settles_to_zero(self):
        # A pays 1000 split among A,B,C ; C pays 600 split among B,C.
        state = AppState(
            people=[Person("a", "A"), Person("b", "B"), Person("c", "C")],
            items=[
                item(900, ["a", "b", "c"], payer="a", iid="1"),
                item(600, ["b", "c"], payer="c", iid="2"),
            ],
        )
        transfers = settle_up(state)
        # Reconstruct net effect and assert everyone nets to zero.
        net = {"a": 0, "b": 0, "c": 0}
        owed = per_person_totals(state)
        paid = {"a": 900, "b": 0, "c": 600}
        for pid in net:
            net[pid] = paid[pid] - owed[pid]
        for debtor, creditor, amount in transfers:
            self.assertGreater(amount, 0)
            net[debtor] += amount
            net[creditor] -= amount
        self.assertEqual(net, {"a": 0, "b": 0, "c": 0})


class SerializationTests(unittest.TestCase):
    def test_round_trip(self):
        state = AppState(
            people=[Person("a", "Alice"), Person("b", "Bob")],
            items=[item(1234, ["a", "b"], payer="a",
                        split={"mode": "uneven",
                               "weights": {"a": 2, "b": 1}})],
        )
        restored = AppState.from_dict(state.to_dict())
        self.assertEqual(restored.to_dict(), state.to_dict())


if __name__ == "__main__":
    unittest.main()
