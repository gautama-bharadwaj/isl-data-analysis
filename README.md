# Indian Super League data analysis

Who are the best players in each position in Indian Super League history, and how has the league changed since 2014? This project collects match and player data for every ISL season and turns it into a report published with GitHub Pages.

**Status:** collecting data. The analysis and site come next.

## Data

| Seasons | What's available | Source |
|---|---|---|
| 2014 to 2017–18 | Results and basic match data | [FotMob](https://www.fotmob.com/leagues/9478/overview/indian-super-league) |
| 2018–19, 2020–21 onward | Per-match player stats: xG, xA, shots, passes, dribbles, tackles, interceptions, clearances, saves and more, plus shot maps | [FotMob](https://www.fotmob.com/leagues/9478/overview/indian-super-league) |
| 2019–20 | Per-match player stats without xG | [FotMob](https://www.fotmob.com/leagues/9478/overview/indian-super-league) |
| 2021–22 | Full event data for all 115 matches | [StatsBomb open data](https://github.com/statsbomb/open-data) |

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
