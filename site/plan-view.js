(function (root) {
  const STALE_CUTOFF = "10:45";   // latest scan should have landed by now
  const PLAN_TIME = "10:00";      // a plan generated before this on the cut-off day is old
  const ROAD_FACTOR = 1.3;        // straight line -> road distance
  const SPEED_KMH = 35;

  const fill = (t, v) => t.replace(/\{(\w+)\}/g, (_, k) => esc(v[k]));
  const mins = hm => +hm.slice(0, 2) * 60 + +hm.slice(3);
  const prevYmd = ymd => { const [y, m, d] = ymd.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10); };

  const syd = new Intl.DateTimeFormat("en-CA", {timeZone: "Australia/Sydney", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
  function sydNow(d) {
    const p = Object.fromEntries(syd.formatToParts(d).map(x => [x.type, x.value]));
    return {ymd: `${p.year}-${p.month}-${p.day}`, hm: `${p.hour}:${p.minute}`, dow: new Date(Date.UTC(+p.year, +p.month - 1, +p.day)).getUTCDay()};
  }

  function h12(h) { return h % 12 || 12; }
  function fmtTime(hm, S) {
    const h = +hm.slice(0, 2), m = hm.slice(3);
    return h12(h) + (m === "00" ? "" : ":" + m) + (h < 12 ? S.am : S.pm);
  }
  function fmtDate(ymd, S, upper = false) {
    const [y, m, d] = ymd.split("-").map(Number);
    const s = `${S.days[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${d} ${S.months[m - 1]}`;
    return upper ? s.toUpperCase() : s;
  }
  function blockLabel(block, S) {
    const [a, b] = block.map(m => (12 + m / 60) % 24);
    const sa = a < 12 ? S.AM : S.PM, sb = b < 12 ? S.AM : S.PM;
    return sa === sb ? `${h12(a)} – ${h12(b)} ${sb}` : `${h12(a)} ${sa} – ${h12(b)} ${sb}`;
  }

  function isStale(generatedAt, status, now) {
    const n = sydNow(now), g = sydNow(new Date(generatedAt));
    const cutDay = n.hm >= STALE_CUTOFF ? n.ymd : prevYmd(n.ymd);
    return status !== "ok" || (g.ymd + " " + g.hm) < (cutDay + " " + PLAN_TIME);
  }
  function headerStamp(plan, now, S) {
    const g = sydNow(new Date(plan.generated_at)), time = fmtTime(g.hm, S);
    if (plan.status !== "ok") return {text: fill(S.updated_partial, {time}), cls: "bad"};
    if (isStale(plan.generated_at, plan.status, now)) return {text: fill(S.updated_old, {day: S.days[g.dow], time}), cls: "bad"};
    return {text: fill(S.updated_ok, {time}), cls: "ok"};
  }

  // Shift date and minutes since 12:00 for a moment; 00:00-03:00 belongs to the previous day's shift.
  function shiftPos(now) {
    const n = sydNow(now);
    if (n.hm <= "03:00") return {ymd: prevYmd(n.ymd), m: 720 + mins(n.hm)};
    return {ymd: n.ymd, m: n.hm < "12:00" ? 0 : mins(n.hm) - 720};
  }
  function locateNow(days, now) {
    const {ymd, m} = shiftPos(now);
    const d = days.findIndex(x => x.date === ymd);
    if (d >= 0) {
      const e = days[d].entries.findIndex(x => (x.block[0] <= m && m < x.block[1]) || (m === 900 && x.block[1] === 900));
      if (e >= 0) return {day: d, entry: e};
    }
    const later = days.findIndex(x => x.date > ymd);
    return later >= 0 ? {day: later, entry: 0} : null;
  }

  function minutesFromYou(lat1, lon1, lat2, lon2) {
    const r = x => x * Math.PI / 180, a = Math.sin(r(lat2 - lat1) / 2) ** 2 +
      Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
    const km = 6371 * 2 * Math.asin(Math.sqrt(a));
    return Math.max(1, Math.round(km * ROAD_FACTOR / SPEED_KMH * 60));
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const mapsUrl = address => "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent(address);

  const GOOD_SCORE = 55;          // green badge at or above, yellow below

  function quiet(e, S) {
    const head = e.until ? fill(S.free_until, {time: fmtTime(e.until, S), name: e.next}) : S.free_rest;
    const alt = e.nearby && e.nearby.length ? `<div class="alt">${fill(S.try_nearby, {names: e.nearby.join(" · ")})}</div>` : "";
    return `<div class="quiet"><div class="lbl">${esc(blockLabel(e.block, S))} · ${esc(S.quiet)}</div><b>${head}</b>${alt}</div>`;
  }

  function card(e, S, isNow, pos, toggled) {
    const open = toggled.has(e.id) ? toggled.get(e.id) : isNow;   // toggled: Map id -> explicit open state
    const exit = S["exit_" + e.kind] ? fill(S["exit_" + e.kind], {time: fmtTime(e.exit, S)}) : "";
    const desc = e.desc ? `<div class="s">${esc(e.desc)}</div>` : "";
    const f = [fill(S.address, {address: e.address})];
    if (e.start) f.push(fill(S.starts_ends, {start: fmtTime(e.start, S), end: fmtTime(e.exit, S)}));
    if (e.size != null) f.push(fill(S.crowd, {size: e.size.toLocaleString("en-US"), lo: e.age_lo, hi: e.age_hi}));
    if (e.wait) f.push(fill(S.wait, {wait: e.wait}));
    if (isNow && pos && e.lat != null && e.lon != null) f.push(fill(S.from_you, {min: minutesFromYou(pos.lat, pos.lon, e.lat, e.lon)}));
    else if (e.drive_from) f.push(fill(S.from_prev, {min: e.drive_min, name: e.drive_from}));
    else f.push(fill(S.from_cbd, {min: e.drive_min}));
    return `<details${isNow ? ' class="now"' : ""}${open ? " open" : ""} data-id="${esc(e.id)}"><summary>` +
      `<div class="lbl">${esc(blockLabel(e.block, S))}</div>` +
      `<div class="row1"><span class="t">${esc(e.name)}</span><span class="${e.score >= GOOD_SCORE ? "sc" : "sc mid"}">${esc(e.score)}</span></div>` +
      `<div class="p">${exit}</div>${isNow ? desc : ""}` +
      `<div class="tap">${esc(open ? S.tap_close : S.tap_open)}</div></summary>` +
      `<div class="more">${isNow ? "" : desc}<div class="f">${f.join("<br>")}</div>` +
      `<a class="go" href="${esc(mapsUrl(e.address))}" target="_blank" rel="noopener">${esc(S.navigate)}</a></div></details>`;
  }

  function renderPage(plan, S, now, pos, toggled) {
    const stamp = headerStamp(plan, now, S);
    const top = `<div class="top"><span class="d">${esc(fmtDate(shiftPos(now).ymd, S))}</span><span class="upd ${stamp.cls}">${stamp.text}</span></div>`;
    const loc = locateNow(plan.days || [], now);
    if (!loc) return top + `<div class="empty">${esc(S.no_plan)}</div>`;
    const one = (e, isNow) => e.type === "quiet" ? quiet(e, S) : card(e, S, isNow, pos, toggled);
    const day = plan.days[loc.day], hd = t => `<div class="hd">${esc(t)}</div>`;
    let h = top + hd(S.go_now) + one(day.entries[loc.entry], true);
    const rest = day.entries.slice(loc.entry + 1);
    if (rest.length) h += hd(day.date === shiftPos(now).ymd ? S.rest_of_today : fmtDate(day.date, S, true)) + rest.map(e => one(e, false)).join("");
    for (const d of plan.days.slice(loc.day + 1)) h += hd(fmtDate(d.date, S, true)) + d.entries.map(e => one(e, false)).join("");
    return h + '<div class="gap"></div>';
  }

  const api = {sydNow, fmtTime, fmtDate, blockLabel, isStale, headerStamp, locateNow, minutesFromYou, esc, mapsUrl, shiftPos, fill, renderPage};
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.PlanView = api;
})(this);
