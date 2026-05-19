"""Split and settle-up math. Pure functions over the model; integer cents.

Every function guarantees money conservation: the sum of allocated cents
always equals the input amount exactly (no lost or invented pennies).
"""

from splitcore.model import MODE_EQUAL, MODE_UNEVEN


def _equal_shares(participants, amount):
    """Even split; leftover pennies go one each to the first participants."""
    n = len(participants)
    base = amount // n
    remainder = amount - base * n
    return {
        pid: base + (1 if idx < remainder else 0)
        for idx, pid in enumerate(participants)
    }


def split_item(item):
    """Return {person_id: cents} splitting one item among its participants.

    Equal mode: even division; leftover pennies go one each to the first
    participants in order.

    Uneven mode: proportional to weights; floor each share, then hand the
    remaining pennies to the participants with the largest fractional
    remainder (ties broken by participant order).
    """
    participants = item.participant_ids
    n = len(participants)
    if n == 0:
        return {}

    amount = item.amount_cents
    mode = item.split_mode()

    if mode == MODE_EQUAL:
        return _equal_shares(participants, amount)

    if mode == MODE_UNEVEN:
        weights = item.split.get("weights", {})
        w = [float(weights.get(pid, 0)) for pid in participants]
        total_w = sum(w)
        if total_w <= 0:
            # Degenerate weights: fall back to an equal split so money is
            # still conserved rather than silently dropping the amount.
            return _equal_shares(participants, amount)

        exact = [amount * wi / total_w for wi in w]
        floors = [int(x) for x in exact]
        distributed = sum(floors)
        remainder = amount - distributed

        order = sorted(
            range(n),
            key=lambda i: (-(exact[i] - floors[i]), i),
        )
        shares = {}
        for idx, pid in enumerate(participants):
            shares[pid] = floors[idx]
        for k in range(remainder):
            shares[participants[order[k]]] += 1
        return shares

    raise ValueError("unknown split mode: %r" % mode)


def per_person_totals(state):
    """Return {person_id: cents owed} summed across all items."""
    totals = {p.id: 0 for p in state.people}
    for item in state.items:
        for pid, cents in split_item(item).items():
            totals[pid] = totals.get(pid, 0) + cents
    return totals


def settle_up(state):
    """Return a list of (debtor_id, creditor_id, cents) transfers.

    net = total_paid - total_owed. Greedily match the largest debtor with the
    largest creditor until every net is zero.
    """
    owed = per_person_totals(state)
    paid = {p.id: 0 for p in state.people}
    for item in state.items:
        paid[item.payer_id] = paid.get(item.payer_id, 0) + item.amount_cents

    net = {}
    for p in state.people:
        net[p.id] = paid.get(p.id, 0) - owed.get(p.id, 0)

    transfers = []
    if not net:
        return transfers
    while True:
        creditor = max(net, key=lambda k: net[k])
        debtor = min(net, key=lambda k: net[k])
        if net[creditor] <= 0 or net[debtor] >= 0:
            break
        amount = min(net[creditor], -net[debtor])
        transfers.append((debtor, creditor, amount))
        net[creditor] -= amount
        net[debtor] += amount
    return transfers
