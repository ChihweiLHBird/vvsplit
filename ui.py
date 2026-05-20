"""DOM rendering and event handlers — the only browser-aware UI module.

State flow: handler -> mutate AppState -> storage.save -> re-render regions.
Dynamic content is built with createElement + textContent (no innerHTML),
so user-entered names cannot inject markup.
"""

from pyscript import document, window
from pyscript.ffi import create_proxy

from splitcore.calc import parse_finite, per_person_totals, settle_up
from splitcore.model import MODE_EQUAL, MODE_UNEVEN, Item, Person

# Reject absurd magnitudes early (a finite 1e308 still poisons later math).
_MAX_AMOUNT = 1e9  # dollars

_state = None
_storage = None
_id_counter = 0
# Proxies created during a render. They must be destroyed before the next
# render or each mutation permanently leaks one proxy per row.
_render_proxies = []


# ---------- small DOM helpers ----------

def _qs(sel):
    return document.querySelector(sel)


def _qsa(sel):
    nodes = document.querySelectorAll(sel)
    return [nodes.item(i) for i in range(nodes.length)]


def _clear(node):
    while node.firstChild:
        node.removeChild(node.firstChild)


def _el(tag, text=None, cls=None):
    node = document.createElement(tag)
    if text is not None:
        node.textContent = text
    if cls is not None:
        node.className = cls
    return node


def _on(node, event, handler, track=True):
    proxy = create_proxy(handler)
    if track:
        _render_proxies.append(proxy)
    node.addEventListener(event, proxy)


def _money(cents):
    return "$%.2f" % (cents / 100.0)


def _row(label, amount=None, cls="entry"):
    """A ledger row: a label on the left, an optional money figure right."""
    li = _el("li", None, cls)
    li.appendChild(_el("span", label, "label"))
    if amount is not None:
        li.appendChild(_el("span", amount, "amount"))
    return li


def _next_id(prefix):
    global _id_counter
    _id_counter += 1
    return "%s%d" % (prefix, _id_counter)


def _seed_counter():
    """Ensure generated ids never collide with ids loaded from storage."""
    global _id_counter
    biggest = 0
    for obj in list(_state.people) + list(_state.items):
        digits = "".join(ch for ch in obj.id if ch.isdigit())
        if digits:
            biggest = max(biggest, int(digits))
    _id_counter = biggest


# ---------- rendering ----------

def _people_by_id():
    return {p.id: p for p in _state.people}


def _name(by_id, pid):
    person = by_id.get(pid)
    return person.name if person else "?"


def render_all():
    for proxy in _render_proxies:
        try:
            proxy.destroy()
        except Exception:
            pass
    _render_proxies.clear()
    _render_people()
    _render_item_form()
    _render_items()
    _render_results()


def _render_people():
    box = _qs("#people-list")
    _clear(box)
    if not _state.people:
        box.appendChild(_el("li", "No people yet.", "muted"))
    for person in _state.people:
        li = _el("li", None, "entry")
        li.appendChild(_el("span", person.name, "label"))
        btn = _el("button", "remove", "link")
        _on(btn, "click", _make_remove_person(person.id))
        li.appendChild(btn)
        box.appendChild(li)
    _qs("#people-error").textContent = ""


def _render_item_form():
    payer = _qs("#payer-select")
    _clear(payer)
    for person in _state.people:
        opt = _el("option", person.name)
        opt.value = person.id
        payer.appendChild(opt)

    parts = _qs("#participants")
    _clear(parts)
    uneven = _qs("#mode-uneven").checked
    for person in _state.people:
        row = _el("label", None, "participant")
        cb = _el("input")
        cb.type = "checkbox"
        cb.value = person.id
        cb.className = "p-check"
        row.appendChild(cb)
        row.appendChild(_el("span", " " + person.name))
        wt = _el("input")
        wt.type = "number"
        wt.value = "1"
        wt.min = "0"
        wt.step = "any"
        wt.className = "p-weight"
        wt.setAttribute("data-pid", person.id)
        wt.style.display = "inline" if uneven else "none"
        row.appendChild(wt)
        parts.appendChild(row)


def _render_items():
    box = _qs("#items-list")
    _clear(box)
    if not _state.items:
        box.appendChild(_el("li", "No items yet.", "muted"))
    by_id = _people_by_id()
    for it in _state.items:
        names = [_name(by_id, pid) for pid in it.participant_ids]
        meta = "%s · paid by %s · split among %s · %s" % (
            it.description,
            _name(by_id, it.payer_id),
            ", ".join(names),
            it.split_mode(),
        )
        li = _el("li", None, "entry")
        li.appendChild(_el("span", meta, "label"))
        li.appendChild(_el("span", _money(it.amount_cents), "amount"))
        btn = _el("button", "delete", "link")
        _on(btn, "click", _make_remove_item(it.id))
        li.appendChild(btn)
        box.appendChild(li)


def _render_results():
    box = _qs("#results")
    _clear(box)

    # Defensive: a poisoned/hand-edited state must degrade to an empty
    # result, never brick the whole UI on load. Failures are logged.
    try:
        totals = per_person_totals(_state)
    except Exception as e:
        window.console.warn("vvsplit: totals failed: " + str(e))
        totals = {}
    box.appendChild(_el("h3", "Each person's share"))
    ul = _el("ul", None, "ledger")
    if not totals:
        ul.appendChild(_el("li", "Nothing to total yet.", "muted"))
    for person in _state.people:
        ul.appendChild(_row(person.name, _money(totals.get(person.id, 0))))
    box.appendChild(ul)

    box.appendChild(_el("h3", "Settle up"))
    try:
        transfers = settle_up(_state)
    except Exception as e:
        window.console.warn("vvsplit: settle-up failed: " + str(e))
        transfers = []
    ul2 = _el("ul", None, "ledger")
    if not transfers:
        ul2.appendChild(_el("li", "All settled — no transfers needed.",
                            "muted"))
    by_id = _people_by_id()
    for debtor, creditor, amount in transfers:
        label = "%s → %s" % (_name(by_id, debtor), _name(by_id, creditor))
        ul2.appendChild(_row(label, _money(amount)))
    box.appendChild(ul2)


def _persist_and_render():
    """Save then re-render. A storage failure (quota, private mode) must not
    desync memory from the DOM or surface a traceback — log and still render.
    """
    try:
        _storage.save(_state)
    except Exception as e:
        window.console.warn("vvsplit: could not save: " + str(e))
    render_all()


# ---------- handlers ----------

def on_add_person(event):
    field = _qs("#person-name")
    name = field.value.strip()
    err = _qs("#people-error")
    if not name:
        err.textContent = "Enter a name."
        return
    if any(p.name == name for p in _state.people):
        err.textContent = "That name already exists."
        return
    _state.people.append(Person(_next_id("p"), name))
    field.value = ""
    _persist_and_render()


def _make_remove_person(pid):
    def handler(event):
        refs = _state.items_referencing(pid)
        if refs:
            descs = ", ".join(i.description for i in refs)
            _qs("#people-error").textContent = (
                "Can't remove — used by item(s): " + descs)
            return
        _state.people = [p for p in _state.people if p.id != pid]
        _persist_and_render()
    return handler


def on_mode_change(event):
    _render_item_form()


def _select_share_field(event):
    """Select a share field's text on focus/click so the value can be
    replaced with one keystroke. Delegated from the persistent
    #participants container, so it survives form re-renders."""
    el = event.target
    if el.classList.contains("p-weight"):
        el.select()


def on_add_item(event):
    err = _qs("#item-error")
    err.textContent = ""

    desc = _qs("#item-desc").value.strip()
    if not desc:
        err.textContent = "Enter a description."
        return

    amount = parse_finite(_qs("#item-amount").value.strip())
    if amount is None:
        err.textContent = "Amount must be a number."
        return
    if amount > _MAX_AMOUNT:
        err.textContent = "Amount is unreasonably large."
        return
    amount_cents = int(round(amount * 100))
    if amount_cents <= 0:
        err.textContent = "Amount must be greater than zero."
        return

    payer_id = _qs("#payer-select").value
    if not payer_id or _state.person_by_id(payer_id) is None:
        err.textContent = "Select who paid."
        return

    checked = [c for c in _qsa(".p-check") if c.checked]
    participant_ids = [c.value for c in checked]
    if not participant_ids:
        err.textContent = "Pick at least one participant."
        return

    uneven = _qs("#mode-uneven").checked
    if uneven:
        weights = {}
        for w in _qsa(".p-weight"):
            pid = w.getAttribute("data-pid")
            if pid in participant_ids:
                val = parse_finite(w.value)
                if val is None:
                    err.textContent = "Weights must be numbers."
                    return
                if val < 0:
                    err.textContent = "Weights cannot be negative."
                    return
                weights[pid] = val
        if sum(weights.values()) <= 0:
            err.textContent = "Weights cannot all be zero."
            return
        split = {"mode": MODE_UNEVEN, "weights": weights}
    else:
        split = {"mode": MODE_EQUAL}

    _state.items.append(Item(
        _next_id("i"), desc, amount_cents, payer_id, participant_ids, split))
    _qs("#item-desc").value = ""
    _qs("#item-amount").value = ""
    _persist_and_render()


def _make_remove_item(iid):
    def handler(event):
        _state.items = [i for i in _state.items if i.id != iid]
        _persist_and_render()
    return handler


# ---------- entry ----------

def start(state, storage_module):
    global _state, _storage
    _state = state
    _storage = storage_module
    _seed_counter()
    _on(_qs("#add-person"), "click", on_add_person, track=False)
    _on(_qs("#add-item"), "click", on_add_item, track=False)
    _on(_qs("#mode-equal"), "change", on_mode_change, track=False)
    _on(_qs("#mode-uneven"), "change", on_mode_change, track=False)
    parts = _qs("#participants")
    _on(parts, "focusin", _select_share_field, track=False)
    _on(parts, "click", _select_share_field, track=False)
    render_all()
    boot = _qs("#boot-msg")
    if boot:
        boot.remove()
