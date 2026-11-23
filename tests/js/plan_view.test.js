const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const { sydNow, fmtTime, fmtDate, blockLabel, isStale, headerStamp, locateNow, minutesFromYou, esc, mapsUrl } = require("../../site/plan-view.js");
const S = JSON.parse(fs.readFileSync("site/strings.json")).en;
const at = s => new Date(s);

test("time formats", () => {
  assert.deepEqual(["22:00","17:30","00:00","12:00","01:05"].map(h => fmtTime(h, S)), ["10pm","5:30pm","12am","12pm","1:05am"]);
  assert.deepEqual([[240,360],[600,720],[720,840],[0,120],[840,900],[120,600],[360,900]].map(b => blockLabel(b, S)),
    ["4 – 6 PM","10 PM – 12 AM","12 – 2 AM","12 – 2 PM","2 – 3 AM","2 – 10 PM","6 PM – 3 AM"]);
  assert.equal(fmtDate("2026-11-23", S), "Mon 23 Nov"); assert.equal(fmtDate("2026-11-24", S, true), "TUE 24 NOV");
  assert.deepEqual(sydNow(at("2026-11-23T03:30:00Z")), {ymd: "2026-11-23", hm: "14:30", dow: 1});
  assert.equal(sydNow(at("2026-04-05T00:00:00Z")).hm, "10:00");   // after DST ends
});
test("stale check", () => {
  const g = "2026-11-23T10:02:00+11:00";
  assert.equal(isStale(g, "ok", at("2026-11-23T14:00:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T01:30:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T10:44:00+11:00")), false);
  assert.equal(isStale(g, "ok", at("2026-11-24T10:46:00+11:00")), true);
  assert.equal(isStale(g, "partial", at("2026-11-23T14:00:00+11:00")), true);
  assert.equal(isStale("2026-04-04T10:02:00+11:00", "ok", at("2026-04-05T09:00:00+10:00")), false);
});
test("header stamp", () => {
  const p = {generated_at: "2026-11-23T10:02:00+11:00", status: "ok"};
  assert.deepEqual(headerStamp(p, at("2026-11-23T14:00:00+11:00"), S), {text: "✓ Updated 10:02am", cls: "ok"});
  assert.deepEqual(headerStamp(p, at("2026-11-24T11:00:00+11:00"), S), {text: "⚠ Old plan, from Mon 10:02am", cls: "bad"});
  assert.deepEqual(headerStamp({...p, status: "partial"}, at("2026-11-23T14:00:00+11:00"), S), {text: "⚠ Some sources failed · 10:02am", cls: "bad"});
});
test("locateNow", () => {
  const days = [{date: "2026-11-23", entries: [{block: [0,240]}, {block: [240,360]}, {block: [360,900]}]},
                {date: "2026-11-24", entries: [{block: [0,900]}]}];
  const L = s => locateNow(days, at(s));
  assert.deepEqual(L("2026-11-23T09:00:00+11:00"), {day: 0, entry: 0});
  assert.deepEqual(L("2026-11-23T17:00:00+11:00"), {day: 0, entry: 1});
  assert.deepEqual(L("2026-11-23T23:59:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T02:30:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T03:00:00+11:00"), {day: 0, entry: 2});
  assert.deepEqual(L("2026-11-24T03:30:00+11:00"), {day: 1, entry: 0});
  assert.equal(L("2026-11-25T10:00:00+11:00"), null);
  const wk = [{date: "2026-11-28", entries: [{block: [0,900]}]}, {date: "2026-11-30", entries: [{block: [0,900]}]}];
  assert.deepEqual(locateNow(wk, at("2026-11-29T01:00:00+11:00")), {day: 0, entry: 0});   // Sat overtime
  assert.deepEqual(locateNow(wk, at("2026-11-29T14:00:00+11:00")), {day: 1, entry: 0});   // Sunday → Monday
});
test("helpers", () => {
  const m = minutesFromYou(-33.8688, 151.2093, -33.8474, 151.0636); assert.ok(m >= 29 && m <= 32);
  assert.equal(minutesFromYou(-33.8, 151.2, -33.8, 151.2), 1);
  assert.equal(esc(`<a href="x">&'`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
  assert.equal(mapsUrl("Bennelong Point, Sydney NSW 2000"), "https://www.google.com/maps/dir/?api=1&destination=Bennelong%20Point%2C%20Sydney%20NSW%202000");
});
