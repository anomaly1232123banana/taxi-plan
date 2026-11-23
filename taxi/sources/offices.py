from taxi.model import Candidate, at_shift

WEEKDAYS = range(5)  # Mon-Fri


def office_candidates(offices, days, w, S, holidays=frozenset()) -> list[Candidate]:
    cfg, out = w["office"], []
    for o in offices:
        for d in days:
            if d.weekday() not in WEEKDAYS or d in holidays:
                continue
            base = dict(kind="office", venue=o["name"], address=o["address"], area=o["area"], lat=o["lat"], lon=o["lon"],
                        source_url=o["source_url"], median_age=o["median_age"], age_lo=o["age_lo"], age_hi=o["age_hi"],
                        spend=o["spend"], wait=o["wait"], desc=o["desc"])
            out.append(Candidate(id=f'office:{o["id"]}:normal:{d.isoformat()}', name=o["name"],
                                 exit=at_shift(d, o["normal_finish"]), size=o["staff"], pays=o["cabcharge"], **base))
            out.append(Candidate(id=f'office:{o["id"]}:late:{d.isoformat()}', name=S["office_late"].format(name=o["name"]),
                                 exit=at_shift(d, o["late_finish"]), size=round(o["staff"] * cfg["late_crowd_share"]),
                                 pays=o["cabcharge"], **base))
    return out
