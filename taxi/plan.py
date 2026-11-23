from taxi.drive import base_minutes, drive_minutes
from taxi.model import BLOCKS, SYD, Candidate, block_index, hm_of, shift_minute, shift_slot

HOME_AREA = "CBD"
LATE_FROM = shift_minute("22:00")
KIND_RANK = {"casino": 0, "hotel": 1, "club": 2, "hospital": 3}


def nearby(steady: list[dict], anchor: str, span: tuple[int, int], t: dict, n: int) -> list[dict]:
    def busy_min(p):
        total = 0
        for a, b in p["busy"]:
            start, end = shift_minute(a), shift_minute(b)
            if start > end:  # window began before noon
                start = 0
            total += max(0, min(end, span[1]) - max(start, span[0]))
        return total

    late = span[0] >= LATE_FROM  # after 22:00 the places still busy to the end (casinos) beat hotels that wind down at 23:00
    ok = [(busy_min(p), p) for p in steady]
    ok = [(m, p) for m, p in ok if m > 0]
    ok.sort(key=lambda x: (-x[0] if late else 0, base_minutes(t, anchor, x[1]["area"]), KIND_RANK[x[1]["kind"]], x[1]["name"]))
    return [{"name": p["name"], "address": p["address"], "lat": p["lat"], "lon": p["lon"]} for _, p in ok[:n]]


def _hm(dt) -> str:
    return dt.astimezone(SYD).strftime("%H:%M")


def _drive(stops, k, t, p) -> int:
    """Minutes to drive to stop k from home (first stop) or from the previous stop's exit."""
    c, _ = stops[k]
    if k == 0:
        return base_minutes(t, HOME_AREA, c.area)
    pc, pm = stops[k - 1]
    return drive_minutes(t, pc.area, c.area, pm + p["load_minutes"])


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

    pen = p["drive_penalty"]  # a small cost per drive minute: near-ties go to the shorter drive (scores shown are unchanged)
    best = [(c.score - pen * base_minutes(t, HOME_AREA, c.area), None) for c, _ in el]
    for i in range(len(el)):
        for j in range(i):
            if reachable(el[j], el[i]):
                v = best[j][0] + el[i][0].score - pen * drive_minutes(t, el[j][0].area, el[i][0].area, el[j][1] + p["load_minutes"])
                if v > best[i][0]:
                    best[i] = (v, j)
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
                        "until": hm_of(max(lo, stops[next_k][1] - _drive(stops, next_k, t, p))) if nxt else None,  # leave-by time
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
            entries.append(_stop(c, minute, _drive(stops, k, t, p), None))
        else:
            entries.append(_stop(c, minute, _drive(stops, k, t, p), stops[k - 1][0].name))
    if run:
        close_run(len(stops))
    return entries
