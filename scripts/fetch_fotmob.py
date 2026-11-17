"""Download Indian Super League data from FotMob.

For every season this saves:
  data/raw/fotmob/<season>/league.json          fixtures, table and the list of stat leaderboards
  data/raw/fotmob/<season>/stats/<stat>.json    full season leaderboard for each player and team stat
  data/raw/fotmob/<season>/matches/<id>.json    per-match team stats, player stats, shot map and lineups

Files that already exist are skipped, so the script can be stopped and re-run.
The raw files are for local analysis only and are git-ignored.

Usage:
  python scripts/fetch_fotmob.py                     # every season
  python scripts/fetch_fotmob.py --season 2024/2025  # one season
  python scripts/fetch_fotmob.py --no-matches        # season stats only
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import requests

LEAGUE_ID = 9478  # Indian Super League on FotMob
BASE = "https://www.fotmob.com/api/data"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "fotmob"

# Only these parts of a match page are kept, to keep the raw files small.
MATCH_KEYS_TOP = ("general", "header")
MATCH_KEYS_CONTENT = ("matchFacts", "stats", "playerStats", "shotmap", "lineup")

session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.fotmob.com/",
    }
)


def get_json(url: str, params: dict | None = None, tries: int = 4) -> dict:
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (403, 404):
                raise RuntimeError(f"{r.status_code} for {r.url}")
            print(f"  {r.status_code} for {r.url}, retrying", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  {e}, retrying", file=sys.stderr)
        time.sleep(2 ** attempt + random.random())
    raise RuntimeError(f"giving up on {url} {params or ''}")


def polite_pause() -> None:
    time.sleep(0.6 + random.random() * 0.6)


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def season_dir(season: str) -> Path:
    return OUT / season.replace("/", "-")


def list_seasons() -> list[str]:
    data = get_json(f"{BASE}/leagues", {"id": LEAGUE_ID})
    return list(data["allAvailableSeasons"])


def fetch_league(season: str) -> dict:
    path = season_dir(season) / "league.json"
    if path.exists():
        return json.loads(path.read_text())
    data = get_json(f"{BASE}/leagues", {"id": LEAGUE_ID, "season": season})
    save(path, data)
    polite_pause()
    return data


def fetch_season_stats(season: str, league: dict) -> None:
    stats = league.get("stats") or {}
    for kind in ("players", "teams"):
        for item in stats.get(kind) or []:
            url = item.get("fetchAllUrl")
            if not url:
                continue
            name = url.rstrip("/").split("/")[-1]
            path = season_dir(season) / "stats" / kind / name
            if path.exists():
                continue
            save(path, get_json(url))
            polite_pause()


def trim_match(data: dict) -> dict:
    out = {k: data.get(k) for k in MATCH_KEYS_TOP}
    content = data.get("content") or {}
    out["content"] = {k: content.get(k) for k in MATCH_KEYS_CONTENT}
    return out


def fetch_matches(season: str, league: dict) -> None:
    matches = (league.get("fixtures") or {}).get("allMatches") or []
    done = [m for m in matches if (m.get("status") or {}).get("finished")]
    print(f"  {len(done)} finished matches")
    for i, m in enumerate(done, 1):
        path = season_dir(season) / "matches" / f"{m['id']}.json"
        if path.exists():
            continue
        data = get_json(f"{BASE}/matchDetails", {"matchId": m["id"]})
        save(path, trim_match(data))
        if i % 25 == 0:
            print(f"  {i}/{len(done)}")
        polite_pause()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", action="append", help="e.g. 2024/2025 (repeatable). Default: all seasons")
    ap.add_argument("--no-matches", action="store_true", help="skip per-match downloads")
    args = ap.parse_args()

    seasons = args.season or list_seasons()
    for season in seasons:
        print(f"Season {season}")
        league = fetch_league(season)
        fetch_season_stats(season, league)
        if not args.no_matches:
            fetch_matches(season, league)
    print("Done.")


if __name__ == "__main__":
    main()
