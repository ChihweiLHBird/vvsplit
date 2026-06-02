"""localStorage persistence. Browser-only (imports pyscript)."""

import json

from pyscript import window

from splitcore.model import AppState

KEY = "vvsplit"


def load():
    # localStorage access itself can throw (Safari private mode or
    # third-party-storage blocked → SecurityError). Treat as "no saved
    # data" rather than letting it propagate and brick page boot.
    try:
        raw = window.localStorage.getItem(KEY)
    except Exception as e:
        window.console.warn("vvsplit: localStorage unavailable: " + str(e))
        return AppState()
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
