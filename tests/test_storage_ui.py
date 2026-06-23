"""Browser-bound persistence and save-status tests using small PyScript fakes."""

import importlib.util
import json
import pathlib
import sys
import types
import unittest
from unittest import mock

from splitcore.model import AppState, Item, Person


ROOT = pathlib.Path(__file__).resolve().parent.parent


class FakeLocalStorage:
    def __init__(self, initial=None):
        self.values = dict(initial or {})

    def getItem(self, key):
        return self.values.get(key)

    def setItem(self, key, value):
        self.values[key] = value

    def removeItem(self, key):
        self.values.pop(key, None)


class FakeConsole:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)

    def log(self, message):
        pass


def load_storage(local_storage):
    pyscript = types.ModuleType("pyscript")
    pyscript.window = types.SimpleNamespace(
        localStorage=local_storage,
        console=FakeConsole(),
    )
    with mock.patch.dict(sys.modules, {"pyscript": pyscript}):
        spec = importlib.util.spec_from_file_location(
            "storage_under_test", ROOT / "storage.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class StorageRecoveryTests(unittest.TestCase):
    def test_invalid_json_is_backed_up_and_reported(self):
        local = FakeLocalStorage({"bunnysplit": "{broken"})
        storage = load_storage(local)

        state = storage.load()

        self.assertEqual(state.to_dict(), {"people": [], "items": []})
        self.assertEqual(local.values["bunnysplit:corrupt"], "{broken")
        self.assertIn("Recovered corrupt saved data", storage.recovery_warning())

    def test_partial_model_recovery_is_backed_up_and_reported(self):
        raw = json.dumps({
            "people": [
                {"id": "a", "name": "A"},
                {"id": "a", "name": "duplicate"},
            ],
            "items": "not-a-list",
        })
        local = FakeLocalStorage({"bunnysplit": raw})
        storage = load_storage(local)

        state = storage.load()

        self.assertEqual([person.name for person in state.people], ["A"])
        self.assertEqual(state.items, [])
        self.assertEqual(local.values["bunnysplit:corrupt"], raw)
        self.assertIn("Recovered malformed saved data",
                      storage.recovery_warning())

    def test_existing_backup_remains_visible_and_is_not_overwritten(self):
        valid = json.dumps({"people": [], "items": []})
        local = FakeLocalStorage({
            "bunnysplit": valid,
            "bunnysplit:corrupt": "original backup",
        })
        storage = load_storage(local)

        storage.load()
        storage.save(AppState())

        self.assertIn("backup is preserved", storage.recovery_warning())
        self.assertEqual(local.values["bunnysplit:corrupt"], "original backup")

    def test_later_corrupt_payload_gets_a_versioned_backup(self):
        current_corrupt = "{current-corrupt"
        local = FakeLocalStorage({
            "bunnysplit": current_corrupt,
            "bunnysplit:corrupt": "older backup",
        })
        storage = load_storage(local)

        storage.load()
        storage.load()  # Reloading the same payload must not duplicate it.
        storage.save(AppState())

        self.assertEqual(local.values["bunnysplit:corrupt"], "older backup")
        self.assertEqual(local.values["bunnysplit:corrupt:1"], current_corrupt)
        self.assertNotIn("bunnysplit:corrupt:2", local.values)
        self.assertIn("bunnysplit:corrupt:1", storage.recovery_warning())


class FakeClassList:
    def __init__(self):
        self.values = set()

    def add(self, value):
        self.values.add(value)

    def remove(self, value):
        self.values.discard(value)


class FakePill:
    def __init__(self):
        self.label = types.SimpleNamespace(textContent="")
        self.classList = FakeClassList()
        self.title = ""

    def querySelector(self, selector):
        return self.label if selector == ".saved-label" else None


def load_ui(pill):
    pyscript = types.ModuleType("pyscript")
    pyscript.document = types.SimpleNamespace(
        querySelector=lambda selector: pill if selector == ".saved-pill" else None)
    pyscript.window = types.SimpleNamespace(console=FakeConsole())
    ffi = types.ModuleType("pyscript.ffi")
    ffi.create_proxy = lambda function: function
    with mock.patch.dict(
            sys.modules, {"pyscript": pyscript, "pyscript.ffi": ffi}):
        spec = importlib.util.spec_from_file_location(
            "ui_under_test", ROOT / "ui.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class UiBoundaryTests(unittest.TestCase):
    def test_recovery_warning_is_visible_in_saved_pill(self):
        pill = FakePill()
        ui = load_ui(pill)
        ui._storage = types.SimpleNamespace(
            recovery_warning=lambda: "Recovered data; backup preserved.")

        ui._set_save_status(True)

        self.assertEqual(pill.label.textContent, "Recovered corrupt data")
        self.assertIn("err", pill.classList.values)
        self.assertEqual(pill.title, "Recovered data; backup preserved.")

    def test_id_generation_checks_collisions_without_parsing_loaded_ids(self):
        pill = FakePill()
        ui = load_ui(pill)
        ui._state = AppState(
            people=[Person("p1", "A"), Person("custom" + "9" * 5000, "B")],
            items=[Item("p2", "x", 1, "p1", ["p1"], {"mode": "equal"})],
        )

        ui._seed_counter()

        self.assertEqual(ui._next_id("p"), "p3")


if __name__ == "__main__":
    unittest.main()
