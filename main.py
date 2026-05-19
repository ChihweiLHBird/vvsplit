"""Entry point: load persisted state, then hand off to the UI layer."""

import storage
import ui

ui.start(storage.load(), storage)
