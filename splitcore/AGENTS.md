# AGENTS.md

- `splitcore/` is the pure logic layer. Keep it browser-free and importable under both CPython and MicroPython.
- Preserve exact penny conservation: every split path must sum exactly to `amount_cents`.
- Money stays as integer cents; formatting belongs in `ui.py`, not here.
- `model.py` is the persisted-state trust boundary. Harden malformed saved data here rather than making the UI or calc layer compensate later.
- Keep `MODE_EQUAL` and `MODE_UNEVEN` literal values stable; tests lock persisted JSON to those exact strings.
- Do not switch `model.py` to dataclasses.
- After edits here, run `python -m unittest discover -s tests` and `python -m py_compile splitcore/*.py`.
- Persisted-state hardening caps amounts (`MAX_CENTS` in `model.py`) and uneven weights (`_MAX_WEIGHT` in `calc.py`); preserve those bounds and exact penny conservation when changing split math or deserialization.
