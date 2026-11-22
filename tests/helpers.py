from taxi.model import Candidate


def cand(**kw) -> Candidate:
    base = dict(id="x", kind="event", name="X", venue="V", address="A", area="CBD",
                lat=-33.8688, lon=151.2093, source_url="https://example.com")
    base.update(kw)
    return Candidate(**base)
