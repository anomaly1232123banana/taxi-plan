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

  const api = {sydNow, fmtTime, fmtDate, blockLabel, isStale, headerStamp, locateNow, minutesFromYou, esc, mapsUrl, shiftPos, fill};
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.PlanView = api;
})(this);
