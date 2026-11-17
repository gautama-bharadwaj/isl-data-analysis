"""Download StatsBomb's free event data for the 2021-22 Indian Super League season.

Data: https://github.com/statsbomb/open-data (credit: StatsBomb).
Saves to data/raw/statsbomb/ (git-ignored).
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
COMPETITION_ID, SEASON_ID = 1238, 108  # Indian Super League 2021/2022
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "statsbomb"


def get(path: str):
    r = requests.get(f"{RAW}/{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> None:
    matches = get(f"matches/{COMPETITION_ID}/{SEASON_ID}.json")
    (OUT / "events").mkdir(parents=True, exist_ok=True)
    (OUT / "lineups").mkdir(parents=True, exist_ok=True)
    (OUT / "matches.json").write_text(json.dumps(matches))
    for i, m in enumerate(matches, 1):
        mid = m["match_id"]
        for kind in ("events", "lineups"):
            path = OUT / kind / f"{mid}.json"
            if not path.exists():
                path.write_text(json.dumps(get(f"{kind}/{mid}.json")))
        if i % 20 == 0:
            print(f"{i}/{len(matches)}")
    print(f"Done: {len(matches)} matches")


if __name__ == "__main__":
    main()
