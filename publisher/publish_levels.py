#!/usr/bin/env python3
"""Maneki -> TradingView Pine Seeds publisher.

Computes the QQQ dealer-state STRUCTURAL LEVELS from the settled options chain and
writes one EOD row per level into the Pine Seeds data/ CSVs, then commits + pushes.

Levels (all price series, pricescale 100):
  QQQ_FLIP     zero-gamma flip
  QQQ_CALLWALL call wall
  QQQ_PUTWALL  put wall
  QQQ_EM_HI    spot + 1-week implied move
  QQQ_EM_LO    spot - 1-week implied move

Mirrors tests/dashboard.py exactly so the chart matches the CLI read.
EOD ONLY: run once daily after the settled chain lands. Idempotent (upsert by date):
if the chain has not advanced, it rewrites the same date and produces no new commit,
so it never publishes stale data as fresh.

Env:
  MANEKI_DB   path to qqq_flow.sqlite   (default: /Users/darksweep/maneki/data/qqq_flow.sqlite)
  SEEDS_REPO  path to the cloned repo   (default: /Users/darksweep/QQQ-PineScript)
  SEEDS_PUSH  "1" to git commit+push    (default: "1"; set "0" for a dry run)
"""
import datetime as dt, math, os, sqlite3, subprocess, sys
import numpy as np

sys.path.insert(0, "/Users/darksweep/maneki")
from maneki.research.gex import _daily_features
from maneki.data.gexstate import GexState  # noqa: F401  (kept for parity w/ dashboard setup)

DB   = os.environ.get("MANEKI_DB", "/Users/darksweep/maneki/data/qqq_flow.sqlite")
REPO = os.environ.get("SEEDS_REPO", "/Users/darksweep/QQQ-PineScript")
PUSH = os.environ.get("SEEDS_PUSH", "1") == "1"


def compute():
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    vix = {str(d)[:10]: v for d, v in
           cx.execute("SELECT date,vix_close FROM vix WHERE vix_close IS NOT NULL")}
    feats = _daily_features(DB, vix)
    latest = max(feats)
    f = feats[latest]
    spot = f["spot"]

    # ATM IV nearest weekly expiry — identical to dashboard.py
    rows = cx.execute(
        "SELECT expiry,strike,right,iv FROM chain WHERE date=? AND iv IS NOT NULL",
        (latest,)).fetchall()
    aiv, Tw = None, 7 / 365
    if rows:
        exps = sorted(set(str(r[0])[:10] for r in rows))
        be = min(exps, key=lambda e:
                 abs((dt.date.fromisoformat(e) - dt.date.fromisoformat(latest)).days - 7))
        ks = sorted({float(r[1]) for r in rows if str(r[0])[:10] == be})
        K = min(ks, key=lambda s: abs(s - spot))
        ivs = [float(r[3]) for r in rows
               if str(r[0])[:10] == be and abs(float(r[1]) - K) < 0.01]
        aiv = float(np.mean(ivs)) if ivs else None
        Tw = (dt.date.fromisoformat(be) - dt.date.fromisoformat(latest)).days / 365

    im_1w = spot * aiv * math.sqrt(Tw) if aiv else None
    levels = {
        "QQQ_FLIP":     f.get("flip"),
        "QQQ_CALLWALL": f.get("call_wall"),
        "QQQ_PUTWALL":  f.get("put_wall"),
        "QQQ_EM_HI":    (spot + im_1w) if im_1w else None,
        "QQQ_EM_LO":    (spot - im_1w) if im_1w else None,
    }
    return latest, levels


def upsert(sym, date_iso, val):
    path = os.path.join(REPO, "data", f"{sym}.csv")
    tag = date_iso.replace("-", "") + "T"
    rows = {}
    if os.path.exists(path):
        for ln in open(path):
            ln = ln.strip()
            if ln:
                rows[ln.split(",")[0]] = ln
    v = f"{val:.2f}"
    rows[tag] = f"{tag},{v},{v},{v},{v},0"        # flat OHLC, volume 0
    with open(path, "w") as fh:
        fh.write("\n".join(rows[k] for k in sorted(rows)) + "\n")


def main():
    latest, levels = compute()
    missing = [k for k, v in levels.items() if v is None]
    if missing:
        print(f"[publish] MISSING {missing} for {latest} — aborting (no partial push).")
        sys.exit(1)
    for sym, val in levels.items():
        upsert(sym, latest, float(val))
        print(f"[publish] {sym} {latest} = {float(val):.2f}")
    if PUSH:
        subprocess.run(["git", "-C", REPO, "add", "data/"], check=True)
        r = subprocess.run(["git", "-C", REPO, "commit", "-m", f"levels {latest}"])
        if r.returncode == 0:
            subprocess.run(["git", "-C", REPO, "push"], check=True)
            print(f"[publish] pushed levels {latest}")
        else:
            print("[publish] nothing to commit (chain not advanced)")


if __name__ == "__main__":
    main()
