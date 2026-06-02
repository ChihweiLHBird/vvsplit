# Code Review Report

Date: 2026-05-24

## Scope

Reviewed the current `main.py`, `ui.py`, `storage.py`, `splitcore/`, `tests/`, `index.html`, `styles.css`, `sw.js`, `manifest.webmanifest`, and `docs/superpowers/specs/2026-05-19-vvsplit-design.md`.

No repo-wide review guideline file such as `AGENTS.md`, `CLAUDE.md`, or `CONTRIBUTING.md` was present at the project root, so this review used the checked-in design spec plus the current code and tests as the main source of truth.

## Summary

I found 5 remaining high-confidence issues in the current codebase.

Verification run during review:

- `python3 -m unittest discover -s tests`

## Important

### Uneven split math still breaks on very large finite values loaded from storage

Confidence: 97

Files: `splitcore/calc.py:10-22`, `splitcore/calc.py:93-119`, `splitcore/model.py:97-121`

The recent hardening closes several malformed-state holes, but it still allows arbitrarily large positive `amount_cents` values and huge finite uneven weights through the model boundary. The uneven split path still uses float math, so corrupted or hand-edited saved state can:

- invent cents: `10**50` split 1:1 returns a sum larger than the input
- crash: `10**20` split 1:1:1 can make `remainder` exceed `n`, so `order[k]` raises `IndexError`
- overflow on huge finite weights such as `1e308`, raising `OverflowError` or `ValueError`

This means the exact-money guarantee still does not hold for all persisted inputs the code currently accepts.

### Third-party runtime compromise would still expose all saved bill data

Confidence: 89

Files: `index.html:20-37`, `storage.py:9-37`

The app still executes `https://pyscript.net/.../core.js` in-origin, stores all bill data in `localStorage`, and ships with CSP commented out. If that runtime response is compromised, attacker-controlled code can run with full access to every saved bill.

### Offline cold boot is still unreliable because `core.js` is warmed as an opaque response

Confidence: 91

Files: `index.html:37`, `sw.js:45-47`, `sw.js:67-70`, `sw.js:117-129`

The service worker warmup fetches `core.js` with `mode: 'no-cors'`, which stores an opaque response in the cache. But `index.html` loads that file as a module script, and module-script fetches require a CORS-usable response. Result: after install, the app can still fail to cold-boot offline until a later online visit happens to cache a normal runtime response.

### Startup load failures still leave the top bar claiming data is saved

Confidence: 90

Files: `main.py:3-6`, `storage.py:12-33`, `index.html:61-64`, `ui.py:661-674`

The save-status fix only covers save attempts after the UI is running. If `localStorage` is blocked, unavailable, or the saved blob is unreadable during `storage.load()`, the app falls back to an empty in-memory state, but the top bar still initially shows `Saved · localStorage`. That can mislead users into thinking persistence is healthy when startup already failed.

## Optional

### Save failure is still conveyed only by color on narrow screens

Confidence: 84

Files: `styles.css:177-188`, `index.html:61-64`, `ui.py:463-489`

Below `560px`, `.saved-label` is hidden. On those screens a failed save is reduced to a red dot plus a `title` tooltip. That is not a reliable non-visual or touch-friendly warning, so the persistence failure can still be missed on mobile.
