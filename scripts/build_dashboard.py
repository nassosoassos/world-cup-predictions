#!/usr/bin/env python3
"""
Build a self-contained dashboard.html from the project's data files.

Reads:
    data/predictions-*.json   (agent-written: picks, confidence, rationale, market)
    data/scores-*.json        (actual final scores, for grading)
Writes:
    dashboard.html            (one file, no dependencies — just open it)

Everything is baked into the HTML, so it works from file:// with no server.
Stdlib only — no pip install required.

Usage:
    python3 scripts/build_dashboard.py && open dashboard.html
"""
from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone


def load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def latest_scores() -> dict:
    """Most recent scores file -> {home|away: {...}}."""
    files = sorted(glob.glob("data/scores-*.json"))
    if not files:
        return {}
    data = load_json(files[-1])
    out = {}
    for m in data.get("matches", []):
        out[f"{m.get('home_team')}|{m.get('away_team')}"] = m
    return out


def latest_futures() -> dict:
    """Most recent futures file -> {lock_deadline, markets:[...]}."""
    files = sorted(glob.glob("data/futures-*.json"))
    return load_json(files[-1]) if files else {}


def all_predictions() -> list[dict]:
    """Every prediction we've ever made, newest day first, de-duped by match."""
    days = []
    for path in sorted(glob.glob("data/predictions-*.json"), reverse=True):
        date = os.path.basename(path)[len("predictions-"):-len(".json")]
        data = load_json(path)
        preds = data.get("predictions") or data.get("matches") or []
        if preds:
            days.append({"date": date, "predictions": preds})
    return days


def grade(days: list[dict], scores: dict) -> dict:
    """Attach actual results to predictions and compute an accuracy summary."""
    seen = set()
    predicted = correct = exact = graded = 0
    conf_right, conf_wrong = [], []

    for day in days:
        for p in day["predictions"]:
            key = f"{p.get('home_team')}|{p.get('away_team')}"
            # only grade the FIRST (earliest) prediction per match for the tally,
            # but newest-first means we keep the latest call shown; tally below
            sc = scores.get(key)
            p["actual"] = None
            if sc and sc.get("completed") and sc.get("result"):
                p["actual"] = {
                    "final_score": sc.get("final_score"),
                    "result": sc.get("result"),
                    "pick_hit": p.get("pick") == sc.get("result"),
                    "score_hit": (p.get("scoreline") or "").replace(" ", "")
                    == (sc.get("final_score") or "").replace(" ", ""),
                }
                if key not in seen:
                    seen.add(key)
                    predicted += 1
                    graded += 1
                    if p["actual"]["pick_hit"]:
                        correct += 1
                        if isinstance(p.get("confidence"), (int, float)):
                            conf_right.append(p["confidence"])
                    else:
                        if isinstance(p.get("confidence"), (int, float)):
                            conf_wrong.append(p["confidence"])
                    if p["actual"]["score_hit"]:
                        exact += 1

    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {
        "graded": graded,
        "correct": correct,
        "hit_rate": round(100 * correct / graded) if graded else None,
        "exact": exact,
        "conf_right": avg(conf_right),
        "conf_wrong": avg(conf_wrong),
    }


PICK_LABEL = {"home": "Home win", "draw": "Draw", "away": "Away win"}


def build_data() -> dict:
    scores = latest_scores()
    days = all_predictions()
    summary = grade(days, scores)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "days": days,
        "summary": summary,
        "futures": latest_futures(),
    }


HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Cup 2026 — Predictions</title>
<style>
  :root {
    --bg:#0b0f1a; --card:#151b2e; --card2:#1c2438; --line:#26304a;
    --txt:#e7ecf7; --muted:#8b96b0;
    --home:#3b82f6; --draw:#94a3b8; --away:#f59e0b;
    --win:#22c55e; --loss:#ef4444; --accent:#7c3aed;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:1040px; margin:0 auto; padding:28px 20px 60px; }
  header { display:flex; align-items:baseline; justify-content:space-between;
    flex-wrap:wrap; gap:10px; margin-bottom:6px; }
  h1 { font-size:26px; margin:0; letter-spacing:-.4px; }
  h1 span { color:var(--accent); }
  .gen { color:var(--muted); font-size:12px; }
  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:12px; margin:20px 0 30px; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:14px 16px; }
  .stat b { font-size:24px; display:block; }
  .stat small { color:var(--muted); text-transform:uppercase; font-size:11px;
    letter-spacing:.6px; }
  .daysel { margin:0 0 18px; }
  select { background:var(--card2); color:var(--txt); border:1px solid var(--line);
    border-radius:8px; padding:8px 12px; font-size:14px; }
  .match { background:var(--card); border:1px solid var(--line); border-radius:14px;
    padding:18px 20px; margin-bottom:14px; }
  .mtop { display:flex; justify-content:space-between; align-items:center;
    gap:12px; flex-wrap:wrap; }
  .teams { font-size:18px; font-weight:600; }
  .kick { color:var(--muted); font-size:12px; }
  .pick { font-weight:700; padding:4px 10px; border-radius:999px; font-size:13px;
    background:rgba(124,58,237,.18); color:#c4b5fd; border:1px solid #4c3a8a; }
  .conf { color:var(--accent); letter-spacing:2px; font-size:14px; }
  .bar { display:flex; height:26px; border-radius:7px; overflow:hidden;
    margin:14px 0 6px; border:1px solid var(--line); }
  .bar > div { display:flex; align-items:center; justify-content:center;
    font-size:11px; font-weight:600; color:#0b0f1a; min-width:0; }
  .bar .h { background:var(--home); } .bar .d { background:var(--draw); }
  .bar .a { background:var(--away); }
  .leg { display:flex; gap:16px; color:var(--muted); font-size:11px; margin-bottom:10px; }
  .leg i { width:9px; height:9px; border-radius:2px; display:inline-block; margin-right:5px; }
  .score { font-size:14px; color:var(--muted); }
  .score b { color:var(--txt); }
  .rat { color:#cdd5e6; margin:10px 0 0; }
  .flag { margin-top:8px; font-size:13px; color:#fcd34d;
    background:rgba(245,158,11,.08); border-left:3px solid var(--away);
    padding:6px 10px; border-radius:0 6px 6px 0; }
  .badge { font-weight:700; padding:3px 9px; border-radius:6px; font-size:12px; }
  .hit { background:rgba(34,197,94,.16); color:#86efac; border:1px solid #2f6b46; }
  .miss { background:rgba(239,68,68,.16); color:#fca5a5; border:1px solid #7f3838; }
  .src { margin-top:10px; font-size:12px; }
  .src a { color:#93b4ff; text-decoration:none; margin-right:12px; }
  .empty { text-align:center; color:var(--muted); padding:60px 20px;
    border:1px dashed var(--line); border-radius:14px; }
  .sec { font-size:13px; text-transform:uppercase; letter-spacing:1px;
    color:var(--muted); margin:30px 0 12px; border-bottom:1px solid var(--line);
    padding-bottom:6px; }
  .lock { color:var(--away); font-weight:600; text-transform:none; letter-spacing:0; }
  .futgrid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
    gap:10px; }
  .fut { background:var(--card); border:1px solid var(--line); border-radius:11px;
    padding:12px 14px; }
  .fut .q { color:var(--muted); font-size:12px; }
  .fut .p { font-size:16px; font-weight:700; margin:3px 0; }
  .fut .c { color:var(--accent); font-size:12px; letter-spacing:2px; }
  .fut .n { color:#aab4c8; font-size:12px; margin-top:5px; }
  .fut .res { margin-top:7px; }
</style></head>
<body><div class="wrap">
  <header>
    <h1>🏆 World Cup 2026 <span>Predictions</span></h1>
    <div class="gen" id="gen"></div>
  </header>
  <div class="stats" id="stats"></div>
  <div id="futures"></div>
  <div class="sec" style="margin-top:34px">Match predictions</div>
  <div class="daysel"><label>Matchday: <select id="day"></select></label></div>
  <div id="cards"></div>
</div>
<script>
const DATA = __DATA__;
const PICK = {home:"Home win", draw:"Draw", away:"Away win"};
const pct = x => Math.round((x||0)*100);
const stars = c => "●".repeat(c||0) + "○".repeat(Math.max(0,5-(c||0)));

function renderStats(s){
  const el = document.getElementById("stats");
  if(!s.graded){ el.innerHTML =
    '<div class="stat"><b>—</b><small>No graded matches yet</small></div>'; return; }
  const cells = [
    ["Hit rate", s.hit_rate!=null ? s.hit_rate+"%" : "—"],
    ["Correct picks", s.correct+" / "+s.graded],
    ["Exact scores", s.exact],
    ["Avg conf · right", s.conf_right ?? "—"],
    ["Avg conf · wrong", s.conf_wrong ?? "—"],
  ];
  el.innerHTML = cells.map(([k,v]) =>
    `<div class="stat"><b>${v}</b><small>${k}</small></div>`).join("");
}

function matchCard(p){
  const m = p.market || {};
  const h=pct(m.home), d=pct(m.draw), a=pct(m.away);
  const kick = p.commence_time ? new Date(p.commence_time).toLocaleString() : "";
  let actual = "";
  if(p.actual){
    const b = p.actual.pick_hit ? '<span class="badge hit">PICK ✓</span>'
                                : '<span class="badge miss">PICK ✗</span>';
    const sb = p.actual.score_hit ? ' <span class="badge hit">EXACT ✓</span>' : '';
    actual = `<div class="score" style="margin-top:10px">Final: <b>${p.actual.final_score}</b>
      (${PICK[p.actual.result]||""}) &nbsp; ${b}${sb}</div>`;
  }
  const flag = p.disagreement ? `<div class="flag">⚠︎ ${p.disagreement}</div>` : "";
  const src = (p.sources||[]).map(s =>
    `<a href="${s.url}" target="_blank">${s.title||"source"}↗</a>`).join("");
  return `<div class="match">
    <div class="mtop">
      <div><div class="teams">${p.home_team} vs ${p.away_team}</div>
        <div class="kick">${kick}</div></div>
      <div style="text-align:right">
        <div class="pick">${PICK[p.pick]||p.pick||"—"}${p.scoreline?" · "+p.scoreline:""}</div>
        <div class="conf" title="confidence ${p.confidence}/5">${stars(p.confidence)}</div></div>
    </div>
    <div class="bar">
      <div class="h" style="width:${h}%">${h?h+"%":""}</div>
      <div class="d" style="width:${d}%">${d?d+"%":""}</div>
      <div class="a" style="width:${a}%">${a?a+"%":""}</div>
    </div>
    <div class="leg"><span><i class="h" style="background:var(--home)"></i>Home ${p.home_team}</span>
      <span><i style="background:var(--draw)"></i>Draw</span>
      <span><i style="background:var(--away)"></i>Away ${p.away_team}</span></div>
    ${p.rationale ? `<p class="rat">${p.rationale}</p>` : ""}
    ${flag}${actual}
    ${src ? `<div class="src">${src}</div>` : ""}
  </div>`;
}

function renderDay(date){
  const day = DATA.days.find(d => d.date===date);
  document.getElementById("cards").innerHTML =
    day && day.predictions.length
      ? day.predictions.map(matchCard).join("")
      : '<div class="empty">No predictions for this day yet.</div>';
}

function renderFutures(f){
  const el = document.getElementById("futures");
  if(!f || !f.markets || !f.markets.length){ el.innerHTML=""; return; }
  const lock = f.lock_deadline
    ? ` <span class="lock">· lock by ${f.lock_deadline.replace("T"," ")}</span>` : "";
  const cards = f.markets.map(m => {
    let res = "";
    if(m.result){
      const hit = m.result.correct;
      res = `<div class="res"><span class="badge ${hit?'hit':'miss'}">`
        + `${hit?'✓':'✗'} ${m.result.actual||''}</span></div>`;
    }
    return `<div class="fut">
      <div class="q">${m.question}</div>
      <div class="p">${m.pick}</div>
      <div class="c" title="confidence ${m.confidence}/5">${stars(m.confidence)}</div>
      ${m.note?`<div class="n">${m.note}</div>`:""}
      ${res}
    </div>`;
  }).join("");
  el.innerHTML = `<div class="sec">🏆 Tournament futures${lock}</div>
    <div class="futgrid">${cards}</div>`;
}

document.getElementById("gen").textContent = "updated " + (DATA.generated_at||"");
renderStats(DATA.summary||{});
renderFutures(DATA.futures||{});
const sel = document.getElementById("day");
if(!DATA.days.length){
  document.getElementById("cards").innerHTML =
    '<div class="empty">No predictions yet. Run the daily agent to populate this dashboard.</div>';
  sel.parentElement.style.display="none";
} else {
  DATA.days.forEach(d => { const o=document.createElement("option");
    o.value=d.date; o.textContent=d.date; sel.appendChild(o); });
  sel.onchange = e => renderDay(e.target.value);
  renderDay(DATA.days[0].date);
}
</script></body></html>
"""


def main():
    data = build_data()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = HTML.replace("__DATA__", payload)
    # Write both: dashboard.html (local convention) and index.html (GitHub Pages root).
    for name in ("dashboard.html", "index.html"):
        with open(name, "w") as f:
            f.write(html)
    s = data["summary"]
    n = sum(len(d["predictions"]) for d in data["days"])
    print(f"Wrote dashboard.html — {len(data['days'])} day(s), {n} prediction(s)"
          + (f", hit rate {s['hit_rate']}%" if s.get("hit_rate") is not None else ""))
    print("Open it with:  open dashboard.html")


if __name__ == "__main__":
    main()
