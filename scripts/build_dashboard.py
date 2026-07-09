#!/usr/bin/env python3
"""
Build a self-contained dashboard.html from the project's data files.

Reads:
    data/predictions-*.json   (agent-written: picks, confidence, rationale, market)
    data/scores-*.json        (actual final scores, for grading)
    data/futures-*.json       (tournament picks; group winners give the group map)
Writes:
    dashboard.html            (one file, no dependencies — just open it)
    index.html                (copy for GitHub Pages)

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
    """Merge every scores file (oldest -> newest) -> {home|away: {...}}.

    fetch_scores.py only writes a rolling window (--days-from), so the newest
    file drops matches that finished a few days ago (e.g. the WC openers). We
    merge across all files so completed results persist, and never let a later
    not-yet-completed snapshot clobber an already-completed result.
    """
    out = {}
    for path in sorted(glob.glob("data/scores-*.json")):
        for m in load_json(path).get("matches", []):
            key = f"{m.get('home_team')}|{m.get('away_team')}"
            prev = out.get(key)
            if prev and prev.get("completed") and not m.get("completed"):
                continue
            out[key] = m
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


# Three-letter codes + flag emoji for the 48 finalists. Used by the calendar,
# group cards and scoreboard match headers. (England/Scotland use subdivision tags.)
TEAMS = {
    "Mexico": ["MEX", "\U0001F1F2\U0001F1FD"],
    "South Korea": ["KOR", "\U0001F1F0\U0001F1F7"],
    "Czechia": ["CZE", "\U0001F1E8\U0001F1FF"],
    "South Africa": ["RSA", "\U0001F1FF\U0001F1E6"],
    "Canada": ["CAN", "\U0001F1E8\U0001F1E6"],
    "Switzerland": ["SUI", "\U0001F1E8\U0001F1ED"],
    "Qatar": ["QAT", "\U0001F1F6\U0001F1E6"],
    "Bosnia & Herzegovina": ["BIH", "\U0001F1E7\U0001F1E6"],
    "Brazil": ["BRA", "\U0001F1E7\U0001F1F7"],
    "Morocco": ["MAR", "\U0001F1F2\U0001F1E6"],
    "Scotland": ["SCO", "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"],
    "Haiti": ["HAI", "\U0001F1ED\U0001F1F9"],
    "USA": ["USA", "\U0001F1FA\U0001F1F8"],
    "Paraguay": ["PAR", "\U0001F1F5\U0001F1FE"],
    "Türkiye": ["TUR", "\U0001F1F9\U0001F1F7"],
    "Australia": ["AUS", "\U0001F1E6\U0001F1FA"],
    "Germany": ["GER", "\U0001F1E9\U0001F1EA"],
    "Ecuador": ["ECU", "\U0001F1EA\U0001F1E8"],
    "Ivory Coast": ["CIV", "\U0001F1E8\U0001F1EE"],
    "Curaçao": ["CUW", "\U0001F1E8\U0001F1FC"],
    "Netherlands": ["NED", "\U0001F1F3\U0001F1F1"],
    "Japan": ["JPN", "\U0001F1EF\U0001F1F5"],
    "Sweden": ["SWE", "\U0001F1F8\U0001F1EA"],
    "Tunisia": ["TUN", "\U0001F1F9\U0001F1F3"],
    "Belgium": ["BEL", "\U0001F1E7\U0001F1EA"],
    "Egypt": ["EGY", "\U0001F1EA\U0001F1EC"],
    "Iran": ["IRN", "\U0001F1EE\U0001F1F7"],
    "New Zealand": ["NZL", "\U0001F1F3\U0001F1FF"],
    "Spain": ["ESP", "\U0001F1EA\U0001F1F8"],
    "Uruguay": ["URU", "\U0001F1FA\U0001F1FE"],
    "Cape Verde": ["CPV", "\U0001F1E8\U0001F1FB"],
    "Saudi Arabia": ["KSA", "\U0001F1F8\U0001F1E6"],
    "France": ["FRA", "\U0001F1EB\U0001F1F7"],
    "Senegal": ["SEN", "\U0001F1F8\U0001F1F3"],
    "Norway": ["NOR", "\U0001F1F3\U0001F1F4"],
    "Iraq": ["IRQ", "\U0001F1EE\U0001F1F6"],
    "Argentina": ["ARG", "\U0001F1E6\U0001F1F7"],
    "Algeria": ["ALG", "\U0001F1E9\U0001F1FF"],
    "Austria": ["AUT", "\U0001F1E6\U0001F1F9"],
    "Jordan": ["JOR", "\U0001F1EF\U0001F1F4"],
    "Portugal": ["POR", "\U0001F1F5\U0001F1F9"],
    "Colombia": ["COL", "\U0001F1E8\U0001F1F4"],
    "DR Congo": ["COD", "\U0001F1E8\U0001F1E9"],
    "Uzbekistan": ["UZB", "\U0001F1FA\U0001F1FF"],
    "England": ["ENG", "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"],
    "Croatia": ["CRO", "\U0001F1ED\U0001F1F7"],
    "Ghana": ["GHA", "\U0001F1EC\U0001F1ED"],
    "Panama": ["PAN", "\U0001F1F5\U0001F1E6"],
}


def derive_groups(futures: dict) -> tuple[dict, list[dict]]:
    """From the futures `group_*` markets, build {team: 'A'} and a group list."""
    team_group: dict[str, str] = {}
    groups: list[dict] = []
    for m in futures.get("markets", []):
        key = m.get("key", "")
        if not key.startswith("group_"):
            continue
        letter = key.split("_", 1)[1].upper()
        field = m.get("field") or []
        for t in field:
            team_group[t] = letter
        groups.append({
            "letter": letter,
            "teams": field,
            "pick": m.get("pick"),
            "confidence": m.get("confidence"),
            "note": m.get("note"),
            "result": m.get("result"),
        })
    groups.sort(key=lambda g: g["letter"])
    return team_group, groups


def build_data() -> dict:
    scores = latest_scores()
    days = all_predictions()
    summary = grade(days, scores)
    futures = latest_futures()
    team_group, groups = derive_groups(futures)
    for d in days:
        for p in d["predictions"]:
            p["group"] = team_group.get(p.get("home_team")) or team_group.get(p.get("away_team"))
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "days": days,
        "summary": summary,
        "futures": futures,
        "groups": groups,
        "teams": TEAMS,
    }


HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Cup 2026 — Predictions</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Hanken+Grotesk:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0a0c0b; --bg2:#0e1210; --panel:#131915; --panel2:#192019;
    --line:#27322b; --line2:#36443a;
    --ink:#f3f0e6; --muted:#8b988e; --faint:#5d6a61;
    --lime:#c8f751; --lime2:#9bc23e;
    --home:#5ab0ff; --away:#ff6f5e; --draw:#9aa6a0;
    --gold:#f5c451; --win:#5fdc8a; --loss:#ff6f5e;
    --shadow:0 18px 40px -22px rgba(0,0,0,.9);
  }
  *{box-sizing:border-box;}
  html{scroll-behavior:smooth;}
  body{margin:0; background:var(--bg); color:var(--ink);
    font-family:"Hanken Grotesk",system-ui,sans-serif; font-size:15px; line-height:1.55;
    -webkit-font-smoothing:antialiased; overflow-x:hidden;}
  /* floodlit pitch atmosphere */
  body::before{content:""; position:fixed; inset:0; z-index:-2; pointer-events:none;
    background:
      radial-gradient(900px 480px at 78% -8%, rgba(200,247,81,.10), transparent 60%),
      radial-gradient(700px 520px at 6% 4%, rgba(90,176,255,.06), transparent 60%),
      var(--bg);}
  body::after{content:""; position:fixed; inset:0; z-index:-1; pointer-events:none; opacity:.5;
    background:repeating-linear-gradient(90deg, transparent 0 64px, rgba(255,255,255,.012) 64px 128px);}
  .wrap{max-width:1120px; margin:0 auto; padding:0 22px 90px;}
  a{color:inherit;}

  /* ---- header ---- */
  header{position:sticky; top:0; z-index:40; margin:0 -22px 0; padding:16px 22px 14px;
    background:linear-gradient(180deg, rgba(10,12,11,.96), rgba(10,12,11,.82) 70%, transparent);
    backdrop-filter:blur(8px); display:flex; align-items:center; justify-content:space-between;
    gap:16px; flex-wrap:wrap;}
  .brand{display:flex; align-items:center; gap:14px;}
  .crest{width:42px; height:42px; border-radius:11px; flex:none; position:relative;
    background:linear-gradient(150deg,var(--lime),var(--lime2)); color:#0a0c0b;
    display:grid; place-items:center; font-family:"Anton"; font-size:13px; letter-spacing:.5px;
    box-shadow:0 6px 18px -6px rgba(200,247,81,.5); transform:rotate(-4deg);}
  .crest span{transform:rotate(4deg); line-height:.8; text-align:center;}
  .wordmark{font-family:"Anton"; line-height:.92; letter-spacing:.6px;}
  .wordmark .l1{font-size:13px; color:var(--lime); letter-spacing:3px;}
  .wordmark .l2{font-size:25px; text-transform:uppercase;}
  .hgen{font-family:"Space Mono"; font-size:11px; color:var(--muted); text-align:right;
    display:flex; flex-direction:column; align-items:flex-end; gap:6px;}
  .livepill{display:inline-flex; align-items:center; gap:7px; font-family:"Space Mono";
    font-size:12px; color:var(--ink); background:var(--panel); border:1px solid var(--line);
    padding:5px 11px; border-radius:999px;}
  .livepill b{color:var(--lime);}
  .dot{width:7px; height:7px; border-radius:50%; background:var(--lime);
    box-shadow:0 0 0 0 rgba(200,247,81,.6); animation:pulse 2.2s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(200,247,81,.55)}70%{box-shadow:0 0 0 7px rgba(200,247,81,0)}100%{box-shadow:0 0 0 0 rgba(200,247,81,0)}}

  /* ---- scoreboard stat ribbon ---- */
  .ribbon{display:flex; flex-wrap:wrap; gap:0; margin:22px 0 8px; border:1px solid var(--line);
    border-radius:16px; overflow:hidden; background:linear-gradient(180deg,var(--panel),var(--bg2));
    box-shadow:var(--shadow);}
  .rcell{flex:1 1 0; min-width:130px; padding:16px 18px; border-right:1px solid var(--line);
    position:relative;}
  .rcell:last-child{border-right:none;}
  .rcell .v{font-family:"Anton"; font-size:32px; line-height:1; letter-spacing:.5px;}
  .rcell .v small{font-size:16px; color:var(--muted);}
  .rcell .k{font-family:"Space Mono"; font-size:10.5px; letter-spacing:1.5px; text-transform:uppercase;
    color:var(--muted); margin-top:7px;}
  .rcell.hero .v{color:var(--lime);}

  /* ---- tournament honours strip ---- */
  .honours{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px;
    margin:10px 0 4px;}
  .hon{background:var(--panel); border:1px solid var(--line); border-radius:13px; padding:13px 15px;
    display:flex; flex-direction:column; gap:3px; position:relative; overflow:hidden;}
  .hon .hk{font-family:"Space Mono"; font-size:10px; letter-spacing:1.4px; text-transform:uppercase;
    color:var(--muted);}
  .hon .hp{font-family:"Anton"; font-size:19px; letter-spacing:.4px;}
  .hon .hc{font-family:"Space Mono"; font-size:11px; color:var(--gold); letter-spacing:1px;}
  .hon .htag{position:absolute; top:11px; right:13px; font-size:15px; opacity:.85;}

  /* ---- view switch ---- */
  .switch{display:inline-flex; gap:4px; margin:30px 0 6px; padding:5px; border-radius:13px;
    background:var(--panel); border:1px solid var(--line);}
  .switch button{font-family:"Hanken Grotesk"; font-weight:700; font-size:13px; letter-spacing:.3px;
    color:var(--muted); background:none; border:none; padding:9px 18px; border-radius:9px;
    cursor:pointer; display:flex; align-items:center; gap:7px; transition:.18s;}
  .switch button:hover{color:var(--ink);}
  .switch button.on{background:var(--lime); color:#0a0c0b;}
  .switch .ic{font-size:14px;}

  .secline{display:flex; align-items:baseline; justify-content:space-between; gap:14px;
    flex-wrap:wrap; margin:26px 0 14px;}
  .secline h2{font-family:"Anton"; font-size:21px; letter-spacing:.6px; margin:0; text-transform:uppercase;}
  .secline .reset{font-family:"Space Mono"; font-size:12px; color:var(--lime); cursor:pointer;
    text-decoration:none; border-bottom:1px dashed rgba(200,247,81,.4);}
  .secline .reset:hover{color:var(--ink);}
  .sectools{display:flex; align-items:center; gap:18px;}
  .toolbtn{font-family:"Space Mono"; font-size:12px; color:var(--muted); cursor:pointer;
    border-bottom:1px dashed transparent; transition:.15s; white-space:nowrap;}
  .toolbtn:hover{color:var(--lime); border-color:rgba(200,247,81,.4);}

  /* ---- calendar ---- */
  .cal{background:linear-gradient(180deg,var(--panel),var(--bg2)); border:1px solid var(--line);
    border-radius:18px; padding:18px 18px 20px; box-shadow:var(--shadow);}
  .calhdr{font-family:"Anton"; font-size:18px; letter-spacing:1px; text-transform:uppercase;
    margin:2px 2px 14px; display:flex; align-items:center; gap:10px;}
  .calhdr::after{content:""; flex:1; height:1px; background:var(--line);}
  .dow{display:grid; grid-template-columns:repeat(7,1fr); gap:8px; margin-bottom:8px;}
  .dow span{font-family:"Space Mono"; font-size:10px; letter-spacing:1px; color:var(--faint);
    text-align:center; text-transform:uppercase;}
  .grid{display:grid; grid-template-columns:repeat(7,1fr); gap:8px;}
  .cell{aspect-ratio:1/.92; border-radius:11px; padding:8px; position:relative; border:1px solid transparent;
    display:flex; flex-direction:column;}
  .cell.noplay{background:rgba(255,255,255,.012);}
  .cell .num{font-family:"Space Mono"; font-size:12px; color:var(--faint);}
  .cell.match{background:var(--panel2); border-color:var(--line2); cursor:pointer; transition:.16s;}
  .cell.match .num{color:var(--ink);}
  .cell.match:hover{border-color:var(--lime); transform:translateY(-2px);}
  .cell.match .flags{margin-top:auto; display:flex; flex-wrap:wrap; gap:2px; font-size:13px; line-height:1;}
  .cell.match .cnt{position:absolute; top:7px; right:8px; font-family:"Space Mono"; font-size:9.5px;
    font-weight:700; color:var(--lime); background:rgba(200,247,81,.12); border:1px solid rgba(200,247,81,.3);
    border-radius:6px; padding:1px 5px;}
  .cell.sel{background:var(--lime); border-color:var(--lime);}
  .cell.sel .num{color:#0a0c0b; font-weight:700;}
  .cell.sel .cnt{color:#0a0c0b; background:rgba(10,12,11,.18); border-color:rgba(10,12,11,.25);}
  .cell.today::before{content:"TODAY"; position:absolute; bottom:6px; right:7px; font-family:"Space Mono";
    font-size:8px; letter-spacing:1px; color:var(--gold);}

  /* ---- group cards ---- */
  .groups{display:grid; grid-template-columns:repeat(auto-fill,minmax(255px,1fr)); gap:13px;}
  .gcard{background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px 17px 15px;
    position:relative; overflow:hidden; cursor:pointer; transition:.18s; box-shadow:var(--shadow);}
  .gcard:hover{border-color:var(--lime2); transform:translateY(-3px);}
  .gcard.on{border-color:var(--lime);}
  .gwm{position:absolute; top:-22px; right:-6px; font-family:"Anton"; font-size:96px; line-height:1;
    color:rgba(255,255,255,.03);}
  .ghdr{display:flex; align-items:baseline; gap:9px; margin-bottom:11px;}
  .ghdr .gl{font-family:"Anton"; font-size:16px; letter-spacing:1.5px; color:var(--lime);}
  .ghdr .gt{font-family:"Space Mono"; font-size:10px; letter-spacing:1px; color:var(--muted);
    text-transform:uppercase;}
  .trow{display:flex; align-items:center; gap:9px; padding:6px 8px; border-radius:8px; margin:0 -4px;
    position:relative; z-index:1;}
  .trow .fl{font-size:15px; width:20px; text-align:center;}
  .trow .cd{font-family:"Space Mono"; font-size:11px; color:var(--muted); width:32px;}
  .trow .nm{font-size:13.5px; font-weight:600; flex:1; white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis;}
  .trow.win{background:linear-gradient(90deg, rgba(200,247,81,.14), transparent);}
  .trow.win .nm{color:var(--lime);}
  .trow.win .crown{font-size:12px;}
  .gnote{font-size:11.5px; color:var(--muted); margin-top:10px; line-height:1.45;
    border-top:1px solid var(--line); padding-top:9px;}
  .gres{margin-top:8px;}

  /* ---- match cards ---- */
  .matchwrap{display:flex; flex-direction:column; gap:14px;}
  .daydiv{font-family:"Space Mono"; font-size:11px; letter-spacing:1.5px; text-transform:uppercase;
    color:var(--lime); display:flex; align-items:center; gap:12px; margin:8px 2px 0;}
  .daydiv:first-child{margin-top:0;}
  .daydiv::before{content:"\\25B8"; color:var(--lime);}
  .daydiv::after{content:""; flex:1; height:1px; background:var(--line);}
  .match{background:linear-gradient(180deg,var(--panel),var(--bg2)); border:1px solid var(--line);
    border-radius:18px; padding:0; overflow:hidden; box-shadow:var(--shadow);
    opacity:0; transform:translateY(10px); animation:rise .5s cubic-bezier(.2,.7,.3,1) forwards;}
  @keyframes rise{to{opacity:1; transform:none;}}
  .sb{display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:10px;
    padding:18px 20px 16px; background:radial-gradient(120% 140% at 50% -40%, rgba(200,247,81,.05), transparent 60%);}
  .side{display:flex; flex-direction:column; gap:5px; min-width:0;}
  .side.away{align-items:flex-end; text-align:right;}
  .side .fl{font-size:30px; line-height:1;}
  .side .code{font-family:"Anton"; font-size:30px; letter-spacing:1px; line-height:.9;}
  .side .name{font-family:"Space Mono"; font-size:10.5px; color:var(--muted); letter-spacing:.5px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%;}
  .mid{text-align:center; display:flex; flex-direction:column; align-items:center; gap:6px; padding:0 4px;}
  .mid .vs{font-family:"Anton"; font-size:15px; color:var(--faint); letter-spacing:1px;}
  .mid .fin{font-family:"Anton"; font-size:30px; letter-spacing:1px; color:var(--ink);}
  .mid .kick{font-family:"Space Mono"; font-size:10px; color:var(--muted); white-space:nowrap;}
  .mid .gchip{font-family:"Space Mono"; font-size:9.5px; letter-spacing:.8px; color:var(--lime);
    border:1px solid rgba(200,247,81,.3); border-radius:6px; padding:1px 6px;}

  .callrow{display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
    padding:11px 20px; background:var(--panel2); border-top:1px solid var(--line); border-bottom:1px solid var(--line);}
  .call{display:flex; align-items:center; gap:10px; font-size:13px;}
  .call .lab{font-family:"Space Mono"; font-size:10px; letter-spacing:1.5px; color:var(--faint); text-transform:uppercase;}
  .call .pk{font-family:"Anton"; font-size:16px; letter-spacing:.5px;}
  .call .sl{font-family:"Space Mono"; font-size:13px; color:var(--ink); background:var(--bg);
    border:1px solid var(--line2); border-radius:6px; padding:2px 8px;}
  .conf{display:flex; gap:3px; align-items:center;}
  .conf .lab{font-family:"Space Mono"; font-size:9.5px; letter-spacing:1px; color:var(--faint); margin-right:3px;}
  .conf i{width:11px; height:11px; border-radius:3px; background:var(--line2); display:inline-block;}
  .conf i.f{background:var(--gold); box-shadow:0 0 7px -1px rgba(245,196,81,.5);}

  .body{padding:15px 20px 18px;}
  .bar{display:flex; height:30px; border-radius:9px; overflow:hidden; border:1px solid var(--line);
    background:var(--bg);}
  .bar>div{display:flex; align-items:center; justify-content:center; font-family:"Space Mono";
    font-size:11px; font-weight:700; color:#0a0c0b; min-width:0; transition:.3s;}
  .bar .h{background:var(--home);} .bar .d{background:var(--draw);} .bar .a{background:var(--away);}
  .leg{display:flex; justify-content:space-between; gap:10px; margin:9px 1px 0; font-family:"Space Mono";
    font-size:10.5px; color:var(--muted);}
  .leg i{width:9px; height:9px; border-radius:2px; display:inline-block; margin-right:5px; vertical-align:1px;}
  .rat{color:#d4dccd; margin:15px 0 0; font-size:14px;}
  .flag{margin-top:12px; font-size:13px; color:#f7e4a3; background:rgba(245,196,81,.07);
    border-left:3px solid var(--gold); padding:9px 12px; border-radius:0 8px 8px 0;}
  .flag b{color:var(--gold); font-family:"Space Mono"; font-size:10px; letter-spacing:1px; display:block; margin-bottom:2px;}
  .result{display:flex; align-items:center; gap:9px; margin-top:13px; flex-wrap:wrap;
    padding-top:13px; border-top:1px dashed var(--line2);}
  .result .rl{font-family:"Space Mono"; font-size:11px; color:var(--muted); letter-spacing:.5px;}
  .result .rs{font-family:"Anton"; font-size:18px; letter-spacing:1px;}
  .badge{font-family:"Space Mono"; font-weight:700; padding:3px 9px; border-radius:7px; font-size:11px;
    letter-spacing:.5px;}
  .hit{background:rgba(95,220,138,.15); color:var(--win); border:1px solid rgba(95,220,138,.35);}
  .miss{background:rgba(255,111,94,.15); color:var(--loss); border:1px solid rgba(255,111,94,.35);}
  .src{margin-top:14px; display:flex; flex-wrap:wrap; gap:8px;}
  .src a{font-family:"Space Mono"; font-size:11px; color:var(--home); text-decoration:none;
    border:1px solid var(--line2); border-radius:7px; padding:4px 9px; transition:.15s; background:var(--bg);}
  .src a:hover{border-color:var(--home); color:var(--ink);}
  /* foldable analysis */
  .why{margin-top:13px; border-top:1px dashed var(--line2); padding-top:11px;}
  .why>summary{list-style:none; cursor:pointer; display:inline-flex; align-items:center; gap:8px;
    font-family:"Space Mono"; font-size:11px; letter-spacing:1px; text-transform:uppercase;
    color:var(--muted); user-select:none; transition:.15s;}
  .why>summary::-webkit-details-marker{display:none;}
  .why>summary:hover{color:var(--lime);}
  .why[open]>summary{color:var(--ink);}
  .why>summary .chev{color:var(--lime); transition:transform .2s; display:inline-block;}
  .why[open]>summary .chev{transform:rotate(90deg);}
  .why .rat{margin-top:11px;}
  .why .rat:first-child{margin-top:11px;}

  .empty{text-align:center; color:var(--muted); padding:64px 20px; border:1px dashed var(--line2);
    border-radius:18px; font-family:"Space Mono"; font-size:13px;}
  .hidden{display:none !important;}

  @media (max-width:560px){
    .wordmark .l2{font-size:20px;}
    .rcell .v{font-size:25px;}
    .side .code{font-size:23px;} .side .fl{font-size:24px;}
    .grid,.dow{gap:5px;} .cell{padding:5px;}
    .cell.match .flags{font-size:11px;}
  }
</style></head>
<body><div class="wrap">
  <header>
    <div class="brand">
      <div class="crest"><span>WC<br>26</span></div>
      <div class="wordmark"><div class="l1">FIFA WORLD CUP</div><div class="l2">Prediction Desk</div></div>
    </div>
    <div class="hgen">
      <span class="livepill"><span class="dot"></span>HIT RATE <b id="hr">—</b></span>
      <span id="gen"></span>
    </div>
  </header>

  <div class="ribbon" id="stats"></div>
  <div class="honours" id="honours"></div>

  <div class="switch" id="switch">
    <button data-v="schedule" class="on"><span class="ic">◳</span> Schedule</button>
    <button data-v="groups"><span class="ic">▦</span> Groups</button>
  </div>

  <div id="scheduleView">
    <div class="cal" id="calwrap"></div>
  </div>
  <div id="groupsView" class="hidden">
    <div class="groups" id="groups"></div>
  </div>

  <div class="secline">
    <h2 id="mhdr">Match predictions</h2>
    <div class="sectools">
      <a class="toolbtn" id="expandall">⤢ expand all</a>
      <a class="reset hidden" id="reset">↺ show all matches</a>
    </div>
  </div>
  <div class="matchwrap" id="cards"></div>
</div>
<script>
const DATA = __DATA__;
const TEAMS = DATA.teams || {};
const PICK = {home:"Home win", draw:"Draw", away:"Away win"};
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DOW = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
const pct = x => Math.round((x||0)*100);
const pad = n => String(n).padStart(2,"0");
const code = t => (TEAMS[t]||[])[0] || (t||"").slice(0,3).toUpperCase();
const flag = t => (TEAMS[t]||[])[1] || "";

// local calendar date (YYYY-MM-DD) of a kickoff, so the calendar agrees with
// the local kick times shown on the cards.
const localDate = iso => { const dt=new Date(iso);
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}`; };

// one entry per real match (latest forecast wins — DATA.days is newest-first),
// tagged with _md = the actual matchday it is played on, sorted chronologically.
const seen = {};
const MATCHES = [];
DATA.days.forEach(d => (d.predictions||[]).forEach(p => {
  const k = p.home_team + "|" + p.away_team;
  if(seen[k]) return; seen[k] = 1;
  const o = {...p, _date:d.date};
  o._md = o.commence_time ? localDate(o.commence_time) : d.date;
  MATCHES.push(o);
}));
MATCHES.sort((a,b) => (a.commence_time||a._md).localeCompare(b.commence_time||b._md));

const confBlocks = (c,lab) => {
  const n = c||0;
  let s = lab ? `<span class="lab">CONF</span>` : "";
  for(let i=1;i<=5;i++) s += `<i class="${i<=n?'f':''}"></i>`;
  return `<span class="conf" title="confidence ${n}/5">${s}</span>`;
};

function renderStats(s){
  const hrEl = document.getElementById("hr");
  if(!s.graded){
    document.getElementById("stats").innerHTML =
      '<div class="rcell"><div class="v">—</div><div class="k">No graded matches yet</div></div>';
    hrEl.textContent = "—"; return;
  }
  hrEl.textContent = (s.hit_rate!=null? s.hit_rate+"%":"—");
  const cells = [
    ["hero", (s.hit_rate!=null? s.hit_rate:"—"), "%", "Hit rate"],
    ["", s.correct, "<small>/"+s.graded+"</small>", "Correct picks"],
    ["", s.exact, "", "Exact scores"],
    ["", (s.conf_right ?? "—"), "", "Avg conf · right"],
    ["", (s.conf_wrong ?? "—"), "", "Avg conf · wrong"],
  ];
  document.getElementById("stats").innerHTML = cells.map(([cls,v,suf,k]) =>
    `<div class="rcell ${cls}"><div class="v">${v}${suf||""}</div><div class="k">${k}</div></div>`).join("");
}

function renderHonours(f){
  const want = {champion:"\\u{1F3C6}", top_scorer_team:"\\u26BD", semifinalists:"\\u{1F947}"};
  const el = document.getElementById("honours");
  const ms = (f.markets||[]).filter(m => want[m.key]);
  if(!ms.length){ el.innerHTML=""; return; }
  el.innerHTML = ms.map(m => {
    let res = "";
    if(m.result){ const hit=m.result.correct;
      res = `<div class="gres"><span class="badge ${hit?'hit':'miss'}">${hit?'\\u2713':'\\u2717'} ${m.result.actual||''}</span></div>`; }
    return `<div class="hon"><span class="htag">${want[m.key]}</span>
      <div class="hk">${m.question}</div>
      <div class="hp">${m.pick||'—'}</div>
      ${m.confidence?`<div class="hc">${'\\u2605'.repeat(m.confidence)}${'\\u2606'.repeat(Math.max(0,5-m.confidence))}</div>`:""}
      ${res}</div>`;
  }).join("");
}

/* ---------- calendar ---------- */
let selDay = null;
function renderCalendar(){
  // actual matchday -> {count, teams[]}
  const byDate = {};
  MATCHES.forEach(p => {
    const b = byDate[p._md] || (byDate[p._md] = {count:0, teams:[]});
    b.count++; b.teams.push(p.home_team, p.away_team);
  });
  Object.values(byDate).forEach(b => b.teams = [...new Set(b.teams)]);
  const dates = Object.keys(byDate).sort();
  if(!dates.length){ document.getElementById("calwrap").innerHTML =
    '<div class="empty">No matchdays scheduled yet.</div>'; return; }
  const months = [...new Set(dates.map(d => d.slice(0,7)))].sort();
  const today = DATA.generated_at ? DATA.generated_at.slice(0,10) : "";

  let html = "";
  months.forEach(ym => {
    const [y,m] = ym.split("-").map(Number);
    const first = new Date(y, m-1, 1).getDay();
    const ndays = new Date(y, m, 0).getDate();
    html += `<div class="calhdr">${MON[m-1]} ${y}</div>`;
    html += `<div class="dow">${DOW.map(d=>`<span>${d}</span>`).join("")}</div><div class="grid">`;
    for(let i=0;i<first;i++) html += `<div class="cell noplay"></div>`;
    for(let day=1; day<=ndays; day++){
      const ds = `${y}-${pad(m)}-${pad(day)}`;
      const info = byDate[ds];
      if(!info){ html += `<div class="cell noplay"><div class="num">${day}</div></div>`; continue; }
      const fl = info.teams.slice(0,8).map(flag).join("");
      const cls = `cell match${ds===selDay?' sel':''}${ds===today?' today':''}`;
      html += `<div class="${cls}" data-d="${ds}"><div class="num">${day}</div>
        <span class="cnt">${info.count}</span><div class="flags">${fl}</div></div>`;
    }
    html += `</div>`;
  });
  document.getElementById("calwrap").innerHTML = html;
  document.querySelectorAll(".cell.match").forEach(c =>
    c.onclick = () => filterDay(c.dataset.d));
}

/* ---------- groups ---------- */
let selGroup = null;
function renderGroups(){
  const gs = DATA.groups||[];
  const el = document.getElementById("groups");
  if(!gs.length){ el.innerHTML = '<div class="empty">No group data yet.</div>'; return; }
  el.innerHTML = gs.map(g => {
    const rows = (g.teams||[]).map(t => {
      const win = t===g.pick;
      return `<div class="trow ${win?'win':''}">
        <span class="fl">${flag(t)}</span><span class="cd">${code(t)}</span>
        <span class="nm">${t}</span>${win?'<span class="crown">\\u{1F451}</span>':''}</div>`;
    }).join("");
    let res = "";
    if(g.result){ const hit=g.result.correct;
      res = `<div class="gres"><span class="badge ${hit?'hit':'miss'}">${hit?'\\u2713':'\\u2717'} ${g.result.actual||''}</span></div>`; }
    return `<div class="gcard" data-g="${g.letter}">
      <div class="gwm">${g.letter}</div>
      <div class="ghdr"><span class="gl">GROUP ${g.letter}</span>
        <span class="gt">pick ${'\\u2605'.repeat(g.confidence||0)}</span></div>
      ${rows}
      ${g.note?`<div class="gnote">${g.note}</div>`:""}${res}</div>`;
  }).join("");
  document.querySelectorAll(".gcard").forEach(c =>
    c.onclick = () => filterGroup(c.dataset.g));
}

/* ---------- match cards ---------- */
function matchCard(p, i){
  const m = p.market||{};
  const h=pct(m.home), d=pct(m.draw), a=pct(m.away);
  const kick = p.commence_time ? new Date(p.commence_time).toLocaleString([], {
    weekday:"short", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"}) : "";
  const graded = p.actual;
  const mid = graded
    ? `<div class="fin">${graded.final_score||""}</div>`
    : `<div class="vs">VS</div>`;
  let result = "";
  if(graded){
    const b = graded.pick_hit ? '<span class="badge hit">PICK \\u2713</span>'
                              : '<span class="badge miss">PICK \\u2717</span>';
    const sb = graded.score_hit ? ' <span class="badge hit">EXACT \\u2713</span>' : '';
    result = `<div class="result"><span class="rl">FULL TIME</span>
      <span class="rs">${graded.final_score||""}</span>
      <span class="rl">${PICK[graded.result]||""}</span>${b}${sb}</div>`;
  }
  const fl = p.disagreement ? `<div class="flag"><b>TIPSTER WATCH</b>${p.disagreement}</div>` : "";
  const src = (p.sources||[]).map(s =>
    `<a href="${s.url}" target="_blank" rel="noopener">${s.title||"source"} \\u2197</a>`).join("");
  const rat = p.rationale ? `<p class="rat">${p.rationale}</p>` : "";
  const srcBlock = src ? `<div class="src">${src}</div>` : "";
  const why = rat + fl + srcBlock;
  const nsrc = (p.sources||[]).length;
  const srcN = nsrc ? ` \\u00b7 ${nsrc} source${nsrc>1?'s':''}` : "";
  const details = why ? `<details class="why"><summary><span class="chev">\\u25B8</span> Analysis${srcN}</summary><div class="whybody">${why}</div></details>` : "";
  return `<div class="match" style="animation-delay:${Math.min(i*55,440)}ms">
    <div class="sb">
      <div class="side home">
        <div class="fl">${flag(p.home_team)}</div>
        <div class="code">${code(p.home_team)}</div>
        <div class="name">${p.home_team}</div>
      </div>
      <div class="mid">
        ${mid}
        ${kick?`<div class="kick">${kick}</div>`:""}
        ${p.group?`<div class="gchip">GROUP ${p.group}</div>`:""}
      </div>
      <div class="side away">
        <div class="fl">${flag(p.away_team)}</div>
        <div class="code">${code(p.away_team)}</div>
        <div class="name">${p.away_team}</div>
      </div>
    </div>
    <div class="callrow">
      <div class="call"><span class="lab">Our call</span>
        <span class="pk" style="color:${p.pick==='home'?'var(--home)':p.pick==='away'?'var(--away)':'var(--draw)'}">${PICK[p.pick]||p.pick||"—"}</span>
        ${p.scoreline?`<span class="sl">${p.scoreline}</span>`:""}</div>
      ${confBlocks(p.confidence,true)}
    </div>
    <div class="body">
      <div class="bar">
        <div class="h" style="width:${h}%">${h>=10?h+"%":""}</div>
        <div class="d" style="width:${d}%">${d>=10?d+"%":""}</div>
        <div class="a" style="width:${a}%">${a>=10?a+"%":""}</div>
      </div>
      <div class="leg">
        <span><i style="background:var(--home)"></i>${code(p.home_team)} ${h}%</span>
        <span><i style="background:var(--draw)"></i>Draw ${d}%</span>
        <span><i style="background:var(--away)"></i>${code(p.away_team)} ${a}%</span>
      </div>
      ${result}
      ${details}
    </div>
  </div>`;
}

let allOpen = false;
function applyFold(){ document.querySelectorAll("#cards .why").forEach(x => x.open = allOpen); }
function setExpandAll(open){
  allOpen = open; applyFold();
  document.getElementById("expandall").textContent = open ? "\\u2715 collapse all" : "\\u2922 expand all";
}

function renderMatches(list, heading){
  document.getElementById("mhdr").textContent = heading;
  const el = document.getElementById("cards");
  el.innerHTML = list.length ? list.map((p,i)=>matchCard(p,i)).join("")
    : '<div class="empty">No predictions for this selection yet.</div>';
  applyFold();
}

// like renderMatches but split into per-day sections (used by the group view).
function renderGrouped(list, heading){
  document.getElementById("mhdr").textContent = heading;
  const el = document.getElementById("cards");
  if(!list.length){ el.innerHTML = '<div class="empty">No predictions for this selection yet.</div>'; return; }
  const sections = []; const idx = {};
  list.forEach(p => {
    if(idx[p._md]==null){ idx[p._md]=sections.length; sections.push({d:p._md, items:[]}); }
    sections[idx[p._md]].items.push(p);
  });
  let i = 0, html = "";
  sections.forEach(s => {
    html += `<div class="daydiv">${prettyDate(s.d)}</div>`;
    s.items.forEach(p => { html += matchCard(p, i++); });
  });
  el.innerHTML = html;
  applyFold();
}

/* ---------- filters / view state ---------- */
function clearSel(){
  document.querySelectorAll(".cell.sel").forEach(c=>c.classList.remove("sel"));
  document.querySelectorAll(".gcard.on").forEach(c=>c.classList.remove("on"));
}
function showReset(on){ document.getElementById("reset").classList.toggle("hidden", !on); }

function prettyDate(ds){
  const [y,m,d] = ds.split("-").map(Number);
  const dt = new Date(y, m-1, d);
  return `${DOW[dt.getDay()]} ${d} ${MON[m-1]}`;
}

function filterDay(ds){
  selDay = ds; selGroup = null;
  clearSel();
  const cell = document.querySelector(`.cell[data-d="${ds}"]`);
  if(cell) cell.classList.add("sel");
  const list = MATCHES.filter(p => p._md===ds);
  renderMatches(list, `${prettyDate(ds)} \\u00b7 ${list.length} match${list.length===1?'':'es'}`);
  showReset(false);
}
function filterGroup(letter){
  selGroup = letter; selDay = null;
  clearSel();
  const card = document.querySelector(`.gcard[data-g="${letter}"]`);
  if(card) card.classList.add("on");
  const list = MATCHES.filter(p => p.group===letter);
  renderGrouped(list, `Group ${letter} \\u00b7 ${list.length} match${list.length===1?'':'es'}`);
  showReset(true);
}
function showAll(){
  selGroup = null; clearSel();
  renderGrouped(MATCHES, `All matches \\u00b7 ${MATCHES.length}`);
  showReset(false);
}

/* ---------- view switch ---------- */
document.querySelectorAll("#switch button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#switch button").forEach(x=>x.classList.remove("on"));
    b.classList.add("on");
    const v = b.dataset.v;
    document.getElementById("scheduleView").classList.toggle("hidden", v!=="schedule");
    document.getElementById("groupsView").classList.toggle("hidden", v!=="groups");
  };
});

/* ---------- boot ---------- */
document.getElementById("gen").textContent = "updated " + (DATA.generated_at||"");
renderStats(DATA.summary||{});
renderHonours(DATA.futures||{});
document.getElementById("expandall").onclick = () => setExpandAll(!allOpen);
if(!MATCHES.length){
  document.getElementById("calwrap").innerHTML =
    '<div class="empty">No predictions yet. Run the daily agent to populate this board.</div>';
  renderMatches([], "Match predictions");
} else {
  renderCalendar();
  renderGroups();
  document.getElementById("reset").onclick = showAll;
  // default to today's fixtures, else the next matchday, else the most recent.
  const mdays = [...new Set(MATCHES.map(p => p._md))].sort();
  const today = (DATA.generated_at||"").slice(0,10);
  const def = mdays.includes(today) ? today
            : (mdays.find(d => d >= today) || mdays[mdays.length-1]);
  filterDay(def);
}
</script></body></html>
"""


def validate_predictions() -> list[str]:
    """Flag predictions whose scoreline contradicts the pick.

    Scorelines are ALWAYS home-away order, so a 'home' pick needs home>away
    goals, 'away' needs away>home, 'draw' needs equal. A mismatch (e.g. an
    away pick written '2-1') is a data-entry bug — catch it every build.

    Only the newest predictions file is checked: that's the current run, the
    one place the error is introduced. Past files are immutable and stay put.
    """
    problems = []
    files = sorted(glob.glob("data/predictions-*.json"))
    for path in files[-1:]:
        for p in load_json(path).get("predictions", []):
            pick = p.get("pick")
            score = (p.get("scoreline") or "").strip()
            try:
                h, a = (int(x) for x in score.split("-"))
            except (ValueError, AttributeError):
                continue
            ok = ((pick == "home" and h > a)
                  or (pick == "away" and a > h)
                  or (pick == "draw" and h == a))
            if not ok:
                problems.append(
                    f"{os.path.basename(path)}: {p.get('home_team')} vs "
                    f"{p.get('away_team')} pick={pick} scoreline={score} "
                    f"(home-away order — pick and scoreline disagree)")
    return problems


def main():
    problems = validate_predictions()
    if problems:
        print("\n!! SCORELINE/PICK MISMATCH — fix before publishing:")
        for msg in problems:
            print(f"   - {msg}")
        print()
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
