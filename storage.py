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
        # Stash the bad blob so the next save() doesn't destroy data the
        # user might still recover by hand.
        try:
            window.localStorage.setItem(KEY + ":corrupt", raw)
        except Exception:
            pass
        return AppState()


def save(state):
    window.localStorage.setItem(KEY, json.dumps(state.to_dict()))
