"""localStorage persistence. Browser-only (imports pyscript)."""

import json

from pyscript import window

from splitcore.model import AppState

KEY = "bunnysplit"
CORRUPT_KEY = KEY + ":corrupt"
_recovery_warning = ""


def _preserve_corrupt(raw, existing_backup):
    # Keep every distinct recovery artifact. The stable base key preserves the
    # first payload; later payloads use numeric suffixes so neither is lost.
    try:
        if existing_backup is None:
            backup_key = CORRUPT_KEY
        elif existing_backup == raw:
            return CORRUPT_KEY
        else:
            suffix = 1
            while True:
                backup_key = CORRUPT_KEY + ":" + str(suffix)
                existing = window.localStorage.getItem(backup_key)
                if existing is None:
                    break
                if existing == raw:
                    return backup_key
                suffix += 1
        window.localStorage.setItem(backup_key, raw)
        return backup_key
    except Exception:
        return None


def recovery_warning():
    return _recovery_warning


def load():
    global _recovery_warning
    _recovery_warning = ""
    # localStorage access itself can throw (Safari private mode or
    # third-party-storage blocked → SecurityError). Treat as "no saved
    # data" rather than letting it propagate and brick page boot.
    try:
        raw = window.localStorage.getItem(KEY)
    except Exception as e:
        window.console.warn("bunnysplit: localStorage unavailable: " + str(e))
        return AppState()
    try:
        existing_backup = window.localStorage.getItem(CORRUPT_KEY)
    except Exception:
        existing_backup = None
    if raw is None:
        if existing_backup is not None:
            _recovery_warning = (
                "A corrupt-data backup is preserved in localStorage as "
                + CORRUPT_KEY + "."
            )
        return AppState()
    try:
        issues = []
        state = AppState.from_dict(
            json.loads(raw),
            on_issue=lambda kind, message: issues.append(kind + ": " + message),
        )
        if issues:
            backup_key = _preserve_corrupt(raw, existing_backup)
            _recovery_warning = "Recovered malformed saved data. "
            if backup_key is not None:
                _recovery_warning += (
                    "A backup is preserved in localStorage as "
                    + backup_key + "."
                )
            else:
                _recovery_warning += "The recovery backup could not be written."
        elif existing_backup is not None:
            _recovery_warning = (
                "A corrupt-data backup is preserved in localStorage as "
                + CORRUPT_KEY + "."
            )
        return state
    except Exception as e:  # corrupt data: surface it, don't silently mask
        window.console.warn("bunnysplit: ignoring corrupt saved state: " + str(e))
        # Stash the bad blob so the next save() doesn't destroy data the
        # user might still recover by hand.
        backup_key = _preserve_corrupt(raw, existing_backup)
        _recovery_warning = "Recovered corrupt saved data. "
        if backup_key is not None:
            _recovery_warning += (
                "A backup is preserved in localStorage as "
                + backup_key + "."
            )
        else:
            _recovery_warning += "The recovery backup could not be written."
        return AppState()


def save(state):
    window.localStorage.setItem(KEY, json.dumps(state.to_dict()))


def writable():
    # getItem can succeed while setItem throws (Safari private mode has a
    # 0 quota), so probe an actual write to know if persistence works.
    try:
        probe = KEY + ":probe"
        window.localStorage.setItem(probe, "1")
        window.localStorage.removeItem(probe)
        return True
    except Exception:
        return False
