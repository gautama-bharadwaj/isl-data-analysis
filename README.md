# Indian Super League data analysis

Who are the best players in each position in Indian Super League history, and how has the league changed since 2014? This project collects match and player data for every ISL season and turns it into a report published with GitHub Pages.

**Status:** collecting data. The analysis and site come next.

## Data

Downloaded 2026-11-17: all 1,236 finished matches from 13 seasons. Full numbers are in [`data/coverage.csv`](data/coverage.csv).

| Seasons | Matches | What's available | Source |
|---|---|---|---|
| 2014 to 2017–18 | 278 | Results only, no player data | [FotMob](https://www.fotmob.com/leagues/9478/overview/indian-super-league) |
| 2018–19 | 95 | Season leaderboards with xG; per-match player stats for only 15 matches | FotMob |
| 2019–20 | 95 | Per-match player stats (93 matches) and leaderboards, no xG | FotMob |
| 2020–21 onward | 768 | Per-match player stats with xG, xA, passes, dribbles, tackles, clearances, saves and more, plus shot maps, for every match | FotMob |
| 2021–22 | 115 | Full event data for every match | [StatsBomb open data](https://github.com/statsbomb/open-data) |

Raw downloads are kept out of the repository (`data/raw/` is git-ignored). Only computed tables are published.

## Pipeline

```bash
pip install -r requirements.txt
python scripts/fetch_fotmob.py       # FotMob season stats and per-match data -> data/raw/fotmob/
python scripts/fetch_statsbomb.py    # StatsBomb 2021-22 event data -> data/raw/statsbomb/
python scripts/coverage_report.py    # what each season contains -> data/coverage.csv
```

The FotMob script pauses between requests and skips files it already has, so it can be stopped and re-run.

## Acknowledgements

- [FotMob](https://www.fotmob.com/) for match and player statistics.
- [StatsBomb](https://statsbomb.com/) for the free 2021–22 ISL event data.
