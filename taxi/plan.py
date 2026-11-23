from taxi.drive import base_minutes, drive_minutes
from taxi.model import BLOCKS, SYD, Candidate, block_index, hm_of, shift_minute, shift_slot

HOME_AREA = "CBD"
KIND_RANK = {"casino": 0, "hotel": 1, "club": 2, "hospital": 3}


def nearby(steady: list[dict], anchor: str, span: tuple[int, int], t: dict, n: int) -> list[str]:
    def busy(p):
        for a, b in p["busy"]:
            start, end = shift_minute(a), shift_minute(b)
            if start > end:  # window began before noon
                start = 0
            if start < span[1] and end > span[0]:
                return True
        return False

    ok = [p for p in steady if busy(p)]
    ok.sort(key=lambda p: (base_minutes(t, anchor, p["area"]), KIND_RANK[p["kind"]], p["name"]))
    return [p["name"] for p in ok[:n]]


def _hm(dt) -> str:
    return dt.astimezone(SYD).strftime("%H:%M")


def _stop(c: Candidate, minute: int, drive_min: int, drive_from: str | None) -> dict:
    return {"type": "stop", "block": list(BLOCKS[block_index(minute)]), "id": c.id, "kind": c.kind, "name": c.name,
            "score": c.score, "exit": _hm(c.exit), "start": _hm(c.start) if c.start else None, "desc": c.desc,
            "address": c.address, "lat": c.lat, "lon": c.lon, "size": c.size, "age_lo": c.age_lo, "age_hi": c.age_hi,
            "wait": c.wait, "drive_min": drive_min, "drive_from": drive_from, "url": c.source_url}


def _choose(cands: list[Candidate], t: dict, w: dict) -> list[tuple[Candidate, int]]:
    """Best-scoring chain of reachable stops, one per block, as (candidate, exit minute) in time order."""
    p = w["plan"]
    el = []
    for c in cands:
        slot = shift_slot(c.exit)
        if slot is None or c.area not in t["areas"] or c.score < p["big_threshold"]:
            continue
        if base_minutes(t, HOME_AREA, c.area) <= p["far_minutes"] or c.score >= p["far_threshold"]:
            el.append((c, slot[1]))
    el.sort(key=lambda x: (x[1], -x[0].score, x[0].id))

    def reachable(a, b):
        (ca, ma), (cb, mb) = a, b
        leave = ma + p["load_minutes"]
        return block_index(ma) < block_index(mb) and leave + drive_minutes(t, ca.area, cb.area, leave) <= mb

    best = [(c.score, None) for c, _ in el]
    for i in range(len(el)):
        for j in range(i):
            if reachable(el[j], el[i]) and best[j][0] + el[i][0].score > best[i][0]:
                best[i] = (best[j][0] + el[i][0].score, j)
    if not el:
        return []
    i = max(range(len(el)), key=lambda k: (best[k][0], -k))
    chain = []
    while i is not None:
        chain.append(el[i])
        i = best[i][1]
    return chain[::-1]


def plan_day(cands: list[Candidate], steady: list[dict], t: dict, w: dict) -> list[dict]:
    p = w["plan"]
    stops = _choose(cands, t, w)
    by_block = {block_index(m): k for k, (_, m) in enumerate(stops)}
    entries, run = [], None  # run = [first block, last block] of the open quiet stretch

    def close_run(next_k):
        lo, hi = BLOCKS[run[0]][0], BLOCKS[run[1]][1]
        prev = stops[next_k - 1][0] if next_k > 0 else None
        nxt = stops[next_k][0] if next_k < len(stops) else None
        anchor = nxt.area if nxt else prev.area if prev else HOME_AREA
        entries.append({"type": "quiet", "block": [lo, hi],
                        "until": hm_of(BLOCKS[block_index(stops[next_k][1])][0]) if nxt else None,
                        "next": nxt.name if nxt else None,
                        "nearby": nearby(steady, anchor, (lo, hi), t, p["fallbacks"])})

    for b in range(len(BLOCKS)):
        k = by_block.get(b)
        if k is None:
            run = [run[0], b] if run else [b, b]
            continue
        if run:
            close_run(k)
            run = None
        c, minute = stops[k]
        if k == 0:
            entries.append(_stop(c, minute, base_minutes(t, HOME_AREA, c.area), None))
        else:
            pc, pm = stops[k - 1]
            leave = pm + p["load_minutes"]
            entries.append(_stop(c, minute, drive_minutes(t, pc.area, c.area, leave), pc.name))
    if run:
        close_run(len(stops))
    return entries
