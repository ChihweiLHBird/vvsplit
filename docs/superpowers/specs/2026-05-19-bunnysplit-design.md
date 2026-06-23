# bunnysplit — Design Spec

**Date:** 2026-05-19
**Status:** Approved (design), pending spec review

## Summary

`bunnysplit` is a bill-splitting web app built entirely as static files using
**PyScript with the MicroPython runtime**. No backend, no build step, no
JavaScript written by hand. Users maintain a roster of people and add bill
items incrementally; each item records who paid, which subset of people it is
split among, and how it is split (equally or by uneven weights). The app
persists state in the browser's `localStorage` and can, at any time, compute
per-person totals owed and a greedy settle-up plan (who pays whom).

## Goals

- Pure static PyScript app, MicroPython runtime, served by any static file server.
- Add/remove people (a roster).
- Add items incrementally; recalculate results at any time.
- Per-item: description, amount, payer, participant subset, split rule.
- Split rule: equal, or uneven via per-participant weights.
- Persist all state across page reloads via `localStorage`.
- Output: per-person totals owed **and** net balances / settle-up transfers.
- Correct money math (integer cents; exact penny distribution).
- Pure-logic core unit-tested under CPython with `pytest`.

## Non-Goals (YAGNI)

- No authentication, accounts, or multi-device sync.
- No server or database.
- No multi-currency; single implied currency, 2 decimal places.
- No minimal-transaction optimization for settle-up (greedy is acceptable).
- No editing of existing items (delete + re-add is sufficient for the starter).

## Architecture & File Layout

```
bunnysplit/
├── index.html          # loads PyScript + MicroPython, app shell markup
├── pyscript.toml        # runtime=micropython, lists .py files to load
├── styles.css           # minimal styling
├── main.py              # entry: load state, initial render, wire events
├── ui.py                # DOM render + @when event handlers (only DOM-aware module)
├── storage.py           # localStorage load/save (JSON <-> state dict)
└── splitcore/
    ├── __init__.py
    ├── model.py         # Person, Item, AppState + (de)serialization
    └── calc.py          # split_item(), per_person_totals(), settle_up()
tests/
└── test_calc.py         # pytest, runs under CPython (no DOM)
```

`splitcore/` imports nothing browser-specific, so the money logic is testable
with plain `pytest`. `ui.py` is the only module that touches the DOM.

## Data Model (`splitcore/model.py`)

- **Person**: `id: str`, `name: str`.
- **Item**:
  - `id: str`
  - `description: str`
  - `amount_cents: int`
  - `payer_id: str`
  - `participant_ids: list[str]` (subset of roster)
  - `split: dict` — either `{"mode": "equal"}` or
    `{"mode": "uneven", "weights": {person_id: number}}`.
    Equal mode is equivalent to all weights = 1.
- **AppState**: `people: list[Person]`, `items: list[Item]`.
- **Money**: stored as integer **cents** everywhere; formatted to `$X.XX`
  only at display time.
- (De)serialization: `to_dict()` / `from_dict()` on `AppState` producing
  JSON-safe structures for `storage.py`.

## Split & Settle-Up Logic (`splitcore/calc.py`)

Pure functions, no DOM, fully unit-tested.

- `split_item(item) -> dict[str, int]`
  Returns `{person_id: cents}` for one item over its participants.
  - Equal mode: `amount_cents // n` each; the leftover
    `amount_cents - (amount_cents // n) * n` pennies are distributed one each
    to the first participants (deterministic order). Sum equals `amount_cents`.
  - Uneven mode: allocate proportionally to integer/float weights; floor each
    share, then distribute the remaining pennies to the participants with the
    largest fractional remainder (deterministic tie-break by participant order).
    Sum equals `amount_cents`.
- `per_person_totals(state) -> dict[str, int]`
  Sum each person's share across all items (total each person owes).
- `settle_up(state) -> list[tuple[str, str, int]]`
  For each person, `net = total_paid - total_owed` (cents). Repeatedly match
  the largest debtor (most negative net) with the largest creditor (most
  positive net), emit `(debtor_id, creditor_id, amount_cents)`, reduce both
  nets, until all nets are zero. Greedy; produces a valid settlement with a
  small number of transfers.

## Persistence (`storage.py`)

- `load() -> AppState`: read `localStorage["bunnysplit"]`, JSON-decode,
  `AppState.from_dict`. If missing or corrupt: return a fresh empty
  `AppState` and log a clear message to the browser console (corruption is
  surfaced, not silently masked).
- `save(state)`: `AppState.to_dict` -> JSON -> `localStorage["bunnysplit"]`.
  Called after every successful state mutation.

## UI & Data Flow (`ui.py`, `main.py`)

Single page with sections:

1. **People** — text input + add button; list with remove buttons.
2. **Add item** — description, amount, payer dropdown, participant checkboxes,
   equal/uneven toggle; uneven reveals a weight input per selected participant.
3. **Items** — list of added items with a delete button each.
4. **Results** — per-person totals owed; settle-up transfer list.

Data flow: event handler → mutate `AppState` → `storage.save(state)` →
re-render the dynamic regions from state. Full re-render of dynamic regions
(not fine-grained diffing) — simple and reliable at this scale.

## Error Handling

- Amount input must parse to a strictly positive number → converted to cents;
  otherwise the mutation is rejected and an inline error message is shown.
- An item requires a payer and ≥1 participant; otherwise rejected with an
  inline message.
- Uneven weights must be non-negative and not all zero; otherwise rejected
  with an inline message.
- Removing a person referenced by an existing item is blocked with an inline
  message explaining which items reference them (no orphaned references).
- Corrupt `localStorage` → fresh state + console message (see Persistence).
- No `except: pass`. Failures are surfaced to the user or the console.

## Testing

- `pytest tests/test_calc.py` against `splitcore/` under CPython:
  - equal split with exact division
  - equal split with penny remainder (exact sum)
  - uneven weights, proportional allocation + remainder distribution
  - `per_person_totals` across multiple items
  - `settle_up` with multiple payers and participants (nets resolve to zero)
  - empty state (no people, no items)
- `model.to_dict`/`from_dict` round-trip test.
- UI and storage layers are thin and verified manually in the browser
  (documented run command: `python3 -m http.server` then open the page).

## Open Questions

None. Greedy settle-up and per-item participants confirmed with user.
