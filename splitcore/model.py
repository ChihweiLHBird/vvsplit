"""Data model for vvsplit.

Plain classes (no dataclasses) so this runs identically under CPython and
MicroPython. Money is integer cents everywhere; formatting happens in the UI.
"""

MODE_EQUAL = "equal"
MODE_UNEVEN = "uneven"


class Person:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    @staticmethod
    def from_dict(d):
        return Person(str(d["id"]), str(d["name"]))


class Item:
    """A single bill line.

    split is either {"mode": MODE_EQUAL} or
    {"mode": MODE_UNEVEN, "weights": {person_id: number}}.
    """

    def __init__(self, id, description, amount_cents, payer_id,
                 participant_ids, split):
        self.id = id
        self.description = description
        self.amount_cents = amount_cents
        self.payer_id = payer_id
        self.participant_ids = list(participant_ids)
        self.split = split

    def split_mode(self):
        if isinstance(self.split, dict):
            return self.split.get("mode", MODE_EQUAL)
        return MODE_EQUAL

    def weights(self):
        if isinstance(self.split, dict):
            w = self.split.get("weights", {})
            if isinstance(w, dict):
                return w
        return {}

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount_cents": self.amount_cents,
            "payer_id": self.payer_id,
            "participant_ids": list(self.participant_ids),
            "split": self.split,
        }

    @staticmethod
    def from_dict(d):
        pids = d.get("participant_ids", [])
        if not isinstance(pids, list):
            pids = []
        split = d.get("split", {})
        if not isinstance(split, dict):
            split = {"mode": MODE_EQUAL}
        amount = d.get("amount_cents", 0)
        # bool is an int subclass; exclude it. Reject non-int (e.g. strings
        # from hand-edited storage) so downstream cent math can't crash.
        if isinstance(amount, bool) or not isinstance(amount, int):
            amount = 0
        return Item(
            str(d.get("id", "")),
            str(d.get("description", "")),
            amount,
            str(d.get("payer_id", "")),
            [str(p) for p in pids],
            split,
        )


class AppState:
    def __init__(self, people=None, items=None):
        self.people = people if people is not None else []
        self.items = items if items is not None else []

    def person_by_id(self, pid):
        for p in self.people:
            if p.id == pid:
                return p
        return None

    def items_referencing(self, pid):
        """Items where the person is payer or participant (for safe removal)."""
        out = []
        for it in self.items:
            if it.payer_id == pid or pid in it.participant_ids:
                out.append(it)
        return out

    def to_dict(self):
        return {
            "people": [p.to_dict() for p in self.people],
            "items": [i.to_dict() for i in self.items],
        }

    @staticmethod
    def from_dict(d):
        if not isinstance(d, dict):
            return AppState()
        # Skip individual bad records rather than discarding all saved state.
        people = []
        for p in d.get("people", []) or []:
            try:
                people.append(Person.from_dict(p))
            except Exception:
                pass
        items = []
        for i in d.get("items", []) or []:
            try:
                items.append(Item.from_dict(i))
            except Exception:
                pass
        return AppState(people=people, items=items)
