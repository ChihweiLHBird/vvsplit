"""localStorage persistence. Browser-only (imports pyscript)."""

import json

from pyscript import window

from splitcore.model import AppState

KEY = "vvsplit"


def load():
    raw = window.localStorage.getItem(KEY)
    if raw is None:
        return AppState()
    try:
        return AppState.from_dict(json.loads(raw))
    except Exception as e:  # corrupt data: surface it, don't silently mask
        window.console.warn("vvsplit: ignoring corrupt saved state: " + str(e))
        return AppState()


def save(state):
    window.localStorage.setItem(KEY, json.dumps(state.to_dict()))
