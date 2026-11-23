const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const { renderPage } = require("../../site/plan-view.js");
const S = JSON.parse(fs.readFileSync("site/strings.json")).en;
const at = s => new Date(s);
const P = JSON.parse(fs.readFileSync("tests/fixtures/sample_plan.json")), five = at("2026-11-23T17:00:00+11:00");

test("layout at 5pm", () => {
  const h = renderPage(P, S, five, null, new Map());
  for (const s of ["GO NOW", "REST OF TODAY", "TUE 24 NOV", "WED 25 NOV", "✓ Updated 10:02am", 'class="sc mid">45', 'class="sc">60',
                   "Free time until 10pm (Opera House)", ">The Star</a> · <a", "🚕 6 min from the CBD",
                   "dir/?api=1&amp;destination=Bennelong%20Point%2C%20Sydney%20NSW%202000"]) assert.ok(h.includes(s), s);
  assert.equal(h.split('<details class="now" open').length - 1, 1);
  assert.ok(h.indexOf("KPMG Barangaroo") < h.indexOf("REST OF TODAY"));
  assert.ok(!h.includes("Free time until 4pm (KPMG Barangaroo)"));          // past entry hidden
});
test("go now moves with the clock", () => {
  const h = renderPage(P, S, at("2026-11-23T18:30:00+11:00"), null, new Map());
  assert.ok(h.indexOf("ICC Sydney conference") < h.indexOf("REST OF TODAY"));
  const q = renderPage(P, S, at("2026-11-23T21:00:00+11:00"), null, new Map());
  assert.ok(q.indexOf('class="quiet now"') < q.indexOf("REST OF TODAY"));
});
const KPMG = "office:kpmg-barangaroo:normal:2026-11-23";
test("go-now card he closed stays closed", () => {
  const h = renderPage(P, S, five, null, new Map([[KPMG, false]]));
  assert.ok(!h.includes('<details class="now" open'));
});
test("card he opened stays open when it becomes go now", () => {
  const six = at("2026-11-23T18:30:00+11:00");   // ICC is Go Now
  const before = renderPage(P, S, five, null, new Map([["gf:icc", true]]));
  assert.ok(before.includes('<details open data-id="gf:icc">'));
  const h = renderPage(P, S, six, null, new Map([["gf:icc", true]]));
  assert.ok(h.includes('<details class="now" open data-id="gf:icc">'));
  assert.ok(!renderPage(P, S, six, null, new Map([["gf:icc", false]])).includes('<details class="now" open'));
});
test("header shows shift date after midnight", () => {
  assert.ok(renderPage(P, S, at("2026-11-24T01:30:00+11:00"), null, new Map()).includes('<span class="d">Mon 23 Nov</span>'));
});
test("location shows min from you", () => {
  assert.ok(renderPage(P, S, five, {lat: -33.8688, lon: 151.2093}, new Map()).includes("min from you"));
});
test("escapes Claude text", () => {
  const p = structuredClone(P); p.days[0].entries[2].desc = '<img src=x onerror=alert(1)> & "q"';
  const h = renderPage(p, S, five, null, new Map());
  assert.ok(h.includes("&lt;img src=x onerror=alert(1)&gt; &amp; &quot;q&quot;")); assert.ok(!h.includes("<img"));
});
test("stale and empty", () => {
  assert.ok(renderPage(P, S, at("2026-11-24T11:00:00+11:00"), null, new Map()).includes('class="upd bad"'));
  assert.ok(renderPage({...P, days: []}, S, five, null, new Map()).includes(S.no_plan));
});

test("J1 go now moves on 30 min after the stop's exit", () => {
  const goNow = s => renderPage(P, S, at(s), null, new Map()).split("REST OF TODAY")[0];
  assert.ok(goNow("2026-11-23T17:55:00+11:00").includes('data-id="'+KPMG+'"'));       // exit 17:30, still inside +30
  assert.ok(!goNow("2026-11-23T18:05:00+11:00").includes('data-id="'+KPMG+'"'));      // gone, next entry takes over
});
test("J2 go now quiet box is bright", () => {
  const q = renderPage(P, S, at("2026-11-23T21:00:00+11:00"), null, new Map()).split("REST OF TODAY")[0];
  assert.ok(q.includes('class="quiet now"'));
});
test("J3 fallback names link to Maps (lat/lon when known)", () => {
  const p = structuredClone(P), q = p.days[0].entries.find(e => e.type === "quiet" && e.nearby.length);
  q.nearby = [{name: "The Star", lat: -33.869, lon: 151.195}, "Shangri-La"];
  const h = renderPage(p, S, at("2026-11-23T21:00:00+11:00"), null, new Map());
  assert.ok(h.includes('destination=-33.869%2C151.195"') && h.includes(">The Star</a>"));
  assert.ok(h.includes("maps/search/?api=1&amp;query=Shangri-La%20Sydney") && h.includes(">Shangri-La</a>"));
});
test("J4 old partial plan says Old plan", () => {
  const p = {...P, status: "partial"};
  assert.ok(renderPage(p, S, at("2026-11-25T12:00:00+11:00"), null, new Map()).includes("Old plan"));
  assert.ok(renderPage(p, S, five, null, new Map()).includes("Some sources failed"));
});
test("J6 navigate uses lat/lon when present", () => {
  const p = structuredClone(P), e = p.days[0].entries.find(x => x.type === "stop");
  e.lat = -33.86; e.lon = 151.2;
  assert.ok(renderPage(p, S, five, null, new Map()).includes("destination=-33.86%2C151.2"));
});
