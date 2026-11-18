# Indian Super League data analysis

Who are the best players in each position in Indian Super League history, and how has the league changed since 2014? This project collects match and player data for every ISL season and turns it into a report published with GitHub Pages.

**Status:** complete. The site is published with GitHub Pages at https://gautama-bharadwaj.github.io/isl-data-analysis/.

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
python scripts/build_tables.py       # raw JSON -> data/processed/*.csv
python scripts/build_site_data.py    # analysis -> docs/data/*.json
```

The FotMob script pauses between requests and skips files it already has, so it can be stopped and re-run.

## Tables

`scripts/build_tables.py` writes these to `data/processed/` (git-ignored, like the raw data):

| Table | Rows | What it is |
|---|---|---|
| `matches.csv` | 1,236 | One row per match: teams, score, regular season or playoff, and which data the match has |
| `team_matches.csv` | 2,472 | One row per team per match: xG, shots, possession, passes, tackles, clearances and more (from 2018–19) |
| `player_matches.csv` | 26,114 | One row per player per match with every FotMob player stat (from 2018–19) |
| `shots.csv` | 20,140 | Every shot with its location, xG, xG on target and situation (open play, set piece, free kick, penalty) |
| `players.csv` | 926 | One row per player: nationality, main role, position group, matches and minutes |
| `teams.csv` | 16 | One row per club with its former names |
| `goals.csv` | 3,421 | Every goal since 2014 with scorer, minute, penalty and own-goal flags |

**Clubs.** Renamed clubs are kept as one club under their current name: Mohun Bagan SG (formerly ATK and ATK Mohun Bagan), Odisha FC (Delhi Dynamos), SC Delhi (Hyderabad FC), East Bengal FC (SC East Bengal) and Punjab FC (RoundGlass Punjab).

**Positions.** Each player's role comes from the lineup slot they started in most often: goalkeeper, centre-back, full-back or wing-back, defensive or central midfielder, attacking midfielder or winger, and striker. These are grouped into six positions for the rankings. Players who never started get FotMob's listed position instead.

**Checks.** Player goals plus own goals match the final score in all but one of the 876 matches with player stats.

## Website

The site in `docs/` is published with GitHub Pages by `.github/workflows/pages.yml` whenever `docs/` changes on `main`.

- **The report** (`docs/index.html`): league trends, champions, the best XI, the top ten at every position, and all-time leaderboards.
- **The explorer** (`docs/explore.html`): every player season in a sortable table, side-by-side player comparison, league tables and the best players of each season.

To view it locally: `cd docs && python -m http.server`, then open http://localhost:8000.

## How players are ranked

Rankings use seasons with per-player stats, which means 2019–20 onward. xG-based stats start in 2020–21.

1. Every player's stats are added up and turned into per-90-minute rates and percentages.
2. Only players with at least **2,000 minutes** count for the all-time rankings, and **900 minutes** for a single season.
3. Each player is compared only with players in the same position. Every stat becomes a percentile (100 = best at that position), and the percentiles are combined using weights for that position. For example, strikers are weighted most on non-penalty goals and xG, and centre-backs on clearances, interceptions and aerial duels. The full list of stats and weights is in `docs/data/meta.json` and at the top of `scripts/build_site_data.py`.
4. The best XI uses a 4-3-3 shape: the top keeper, two full-backs, two centre-backs, three central midfielders, two attacking midfielders or wingers, and a striker.

The all-time scorers list is different: it counts every goal since 2014.

## Acknowledgements

- [FotMob](https://www.fotmob.com/) for match and player statistics.
- [StatsBomb](https://statsbomb.com/) for the free 2021–22 ISL event data.
- [Apache ECharts](https://echarts.apache.org/) for the charts (bundled in `docs/assets/vendor/`).
