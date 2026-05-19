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
        return Person(d["id"], d["name"])


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
        return self.split.get("mode", MODE_EQUAL)

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
        return Item(
            d["id"],
            d["description"],
            d["amount_cents"],
            d["payer_id"],
            d["participant_ids"],
            d["split"],
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
        return AppState(
            people=[Person.from_dict(p) for p in d.get("people", [])],
            items=[Item.from_dict(i) for i in d.get("items", [])],
        )
