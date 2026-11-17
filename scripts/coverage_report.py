"""Summarise what the raw downloads contain for each season.

Writes data/coverage.csv: one row per season with the number of matches,
matches with player stats, matches with xG, and season stat leaderboards.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "fotmob"
OUT = ROOT / "data" / "coverage.csv"


def match_flags(path: Path) -> tuple[bool, bool, bool]:
    content = json.loads(path.read_text()).get("content") or {}
    players = content.get("playerStats") or {}
    has_players = bool(players)
    has_xg = False
    for p in players.values():
        for group in p.get("stats") or []:
            if (group.get("stats") or {}).get("Expected goals (xG)", {}).get("stat", {}).get("value") is not None:
                has_xg = True
                break
        if has_xg:
            break
    has_shots = bool((content.get("shotmap") or {}).get("shots"))
    return has_players, has_xg, has_shots


def main() -> None:
    rows = []
    for sdir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        league = json.loads((sdir / "league.json").read_text())
        fixtures = (league.get("fixtures") or {}).get("allMatches") or []
        finished = [m for m in fixtures if (m.get("status") or {}).get("finished")]
        files = sorted((sdir / "matches").glob("*.json")) if (sdir / "matches").exists() else []
        flags = [match_flags(f) for f in files]
        rows.append(
            {
                "season": sdir.name,
                "finished_matches": len(finished),
                "matches_downloaded": len(files),
                "with_player_stats": sum(f[0] for f in flags),
                "with_player_xg": sum(f[1] for f in flags),
                "with_shot_map": sum(f[2] for f in flags),
                "player_leaderboards": len(list((sdir / "stats" / "players").glob("*.json"))),
                "team_leaderboards": len(list((sdir / "stats" / "teams").glob("*.json"))),
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
