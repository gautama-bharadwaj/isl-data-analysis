"""Analyse the processed tables and write the numbers the website reads.

Reads data/processed/*.csv and writes docs/data/*.json:

  meta.json          coverage, cut-offs and the scoring method for each position
  seasons.json       league trends by season: goals, xG, conversion, home advantage, set pieces
  teams.json         one row per club per season: points, goals, xG, style
  positions.json     all-time ranking for each position with the stats behind each score
  best_xi.json       all-time best XI, best Indian XI and the best player per position each season
  leaderboards.json  all-time leaders: goals, xG over/under-performance, free kicks, dribbles, tackles...
  players.json       one row per player per season with per-90 stats, for the explorer
  set_play.json      goals by type (open play, corners, free kicks, penalties...) by season and by club
  attendance.json    crowds by season, by club and by stadium

Only aggregated numbers are written, never raw match data.

Usage: python scripts/build_site_data.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "data"

CAREER_MIN_MINUTES = 2000  # about 22 full matches
SEASON_MIN_MINUTES = 900  # about 10 full matches

POSITIONS = [
    "Goalkeeper",
    "Centre-back",
    "Full-back",
    "Central midfielder",
    "Attacking midfielder / winger",
    "Striker",
]

# Per-position scoring. Each stat is turned into a percentile among qualified players
# at that position (100 = best), then combined with these weights.
# "lower" marks stats where less is better.
METRICS = {
    "Goalkeeper": [
        ("goals_prevented_p90", 3, "Goals prevented per 90 compared with an average keeper"),
        ("save_pct", 2, "Save percentage"),
        ("clean_sheet_pct", 1, "Clean sheet rate"),
        ("high_claims_p90", 1, "High claims per 90"),
        ("sweeper_p90", 0.5, "Sweeper actions per 90"),
        ("pass_pct", 0.5, "Pass accuracy"),
    ],
    "Centre-back": [
        ("clearances_p90", 1.5, "Clearances per 90"),
        ("interceptions_p90", 1.5, "Interceptions per 90"),
        ("tackles_p90", 1, "Tackles per 90"),
        ("blocks_p90", 1, "Shot blocks per 90"),
        ("aerial_pct", 1.5, "Aerial duels won %"),
        ("pass_pct", 1, "Pass accuracy"),
        ("long_balls_p90", 0.5, "Accurate long balls per 90"),
        ("dribbled_past_p90", 1, "Times dribbled past per 90 (lower is better)", "lower"),
    ],
    "Full-back": [
        ("tackles_p90", 1.5, "Tackles per 90"),
        ("interceptions_p90", 1, "Interceptions per 90"),
        ("ground_duel_pct", 1, "Ground duels won %"),
        ("crosses_p90", 1, "Accurate crosses per 90"),
        ("chances_created_p90", 1, "Chances created per 90"),
        ("xa_p90", 1, "Expected assists (xA) per 90"),
        ("final_third_passes_p90", 1, "Passes into the final third per 90"),
        ("dribbled_past_p90", 1, "Times dribbled past per 90 (lower is better)", "lower"),
    ],
    "Central midfielder": [
        ("passes_p90", 1.5, "Accurate passes per 90"),
        ("pass_pct", 1, "Pass accuracy"),
        ("final_third_passes_p90", 1.5, "Passes into the final third per 90"),
        ("long_balls_p90", 0.5, "Accurate long balls per 90"),
        ("chances_created_p90", 1, "Chances created per 90"),
        ("tackles_interceptions_p90", 1.5, "Tackles + interceptions per 90"),
        ("recoveries_p90", 1, "Recoveries per 90"),
        ("duel_pct", 1, "Duels won %"),
    ],
    "Attacking midfielder / winger": [
        ("np_goals_p90", 1.5, "Non-penalty goals per 90"),
        ("npxg_p90", 1, "Non-penalty xG per 90"),
        ("xa_p90", 1.5, "Expected assists (xA) per 90"),
        ("chances_created_p90", 1.5, "Chances created per 90"),
        ("dribbles_p90", 1.5, "Successful dribbles per 90"),
        ("dribble_pct", 0.5, "Dribble success %"),
        ("final_third_passes_p90", 0.5, "Passes into the final third per 90"),
    ],
    "Striker": [
        ("np_goals_p90", 2.5, "Non-penalty goals per 90"),
        ("npxg_p90", 1.5, "Non-penalty xG per 90"),
        ("conversion_pct", 1, "Shot conversion % (goals per shot, excluding penalties)"),
        ("on_target_pct", 0.5, "Shots on target %"),
        ("xa_p90", 1, "Expected assists (xA) per 90"),
        ("box_touches_p90", 0.5, "Touches in the opposition box per 90"),
        ("aerial_pct", 0.5, "Aerial duels won %"),
    ],
}

# Stats summed per player before turning into rates.
SUM_COLS = {
    "minutes": "minutes_played",
    "goals": "goals",
    "assists": "assists",
    "shots": "total_shots",
    "shots_on_target": "shots_on_target",
    "xa": "expected_assists",
    "chances_created": "chances_created",
    "passes": "accurate_passes",
    "passes_att": "accurate_passes_attempted",
    "final_third_passes": "passes_into_final_third",
    "long_balls": "long_balls_accurate",
    "crosses": "accurate_crosses",
    "dribbles": "dribbles_succeeded",
    "dribbles_att": "dribbles_succeeded_attempted",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "blocks": "shot_blocks",
    "recoveries": "recoveries",
    "dribbled_past": "dribbled_past",
    "aerials_won": "aerials_won",
    "aerials_att": "aerials_won_attempted",
    "ground_duels_won": "ground_duels_won",
    "ground_duels_att": "ground_duels_won_attempted",
    "duels_won": "duel_won",
    "duels_lost": "duel_lost",
    "box_touches": "touches_opp_box",
    "saves": "saves",
    "goals_conceded": "goals_conceded",
    "high_claims": "keeper_high_claim",
    "sweeper": "keeper_sweeper",
}


def r(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def records(df: pd.DataFrame, nd: int = 3) -> list[dict]:
    df = df.replace([np.inf, -np.inf], np.nan).round(nd)
    return json.loads(df.to_json(orient="records", force_ascii=False))


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote docs/data/{name}")


def load():
    m = pd.read_csv(PROC / "matches.csv")
    t = pd.read_csv(PROC / "team_matches.csv")
    p = pd.read_csv(PROC / "player_matches.csv", low_memory=False)
    s = pd.read_csv(PROC / "shots.csv")
    pl = pd.read_csv(PROC / "players.csv")
    teams = pd.read_csv(PROC / "teams.csv")
    goals = pd.read_csv(PROC / "goals.csv")
    return m, t, p, s, pl, teams, goals


def season_label(s: str) -> str:
    return s if "-" not in s else f"{s[:4]}–{s[-2:]}"


# ---------------------------------------------------------------- league trends

def league_trends(m: pd.DataFrame, t: pd.DataFrame, s: pd.DataFrame, p: pd.DataFrame) -> list[dict]:
    m = m.copy()
    m["goals"] = m.home_goals + m.away_goals
    m["result"] = np.select([m.home_goals > m.away_goals, m.home_goals < m.away_goals], ["H", "A"], "D")
    out = []
    for season, g in m.groupby("season"):
        row = {
            "season": season,
            "label": season_label(season),
            "matches": len(g),
            "goals": int(g.goals.sum()),
            "goals_per_match": r(g.goals.mean()),
            "home_win_pct": r(100 * (g.result == "H").mean(), 1),
            "draw_pct": r(100 * (g.result == "D").mean(), 1),
            "away_win_pct": r(100 * (g.result == "A").mean(), 1),
            "home_goals_per_match": r(g.home_goals.mean()),
            "away_goals_per_match": r(g.away_goals.mean()),
            "goalless_pct": r(100 * (g.goals == 0).mean(), 1),
            "has_xg": bool(g.has_xg.all()),
        }
        ts = t[t.season == season]
        if ts.total_shots.notna().sum() >= 0.8 * 2 * len(g):
            per = ts.groupby("match_id").sum(numeric_only=True)
            row.update(
                shots_per_match=r(per.total_shots.mean(), 1),
                on_target_per_match=r(per.shots_on_target.mean(), 1),
                conversion_pct=r(100 * per.goals.sum() / per.total_shots.sum(), 1),
                possession_spread=r((ts.ball_possesion - 50).abs().mean(), 1),
                passes_per_team_match=r(ts.accurate_passes.mean(), 0),
                tackles_per_team_match=r(ts.tackles.mean(), 1),
                fouls_per_team_match=r(ts.fouls.mean(), 1),
            )
        if row["has_xg"]:
            per = ts.groupby("match_id").sum(numeric_only=True)
            row.update(
                xg_per_match=r(per.expected_goals.mean()),
                xg_open_play_share_pct=r(100 * ts.expected_goals_open_play.sum() / ts.expected_goals.sum(), 1),
            )
        ss = s[(s.season == season) & ~s.own_goal.fillna(False)]
        if len(ss) > 0.8 * 2 * len(g) * 10:
            goals = ss[ss.is_goal]
            set_piece = goals.situation.isin(["FromCorner", "SetPiece", "FreeKick", "ThrowInSetPiece"])
            row.update(
                set_piece_goal_pct=r(100 * set_piece.mean(), 1),
                penalty_goal_pct=r(100 * (goals.situation == "Penalty").mean(), 1),
                header_goal_pct=r(100 * (goals.shot_type == "Header").mean(), 1),
                outside_box_goal_pct=r(100 * (goals.x < 88.5).mean(), 1),
                direct_free_kick_goals=int((goals.situation == "FreeKick").sum()),
            )
        ps = p[p.season == season]
        if len(ps):
            mins = ps.groupby("country_code").minutes_played.sum()
            if mins.sum() > 0 and ps.country_code.notna().mean() > 0.8:
                row["indian_minutes_pct"] = r(100 * mins.get("IND", 0) / mins.sum(), 1)
        out.append(row)
    return out


# ---------------------------------------------------------------- set plays

GOAL_TYPES = [
    ("Open play", ("RegularPlay", "FastBreak", "IndividualPlay")),
    ("Corners", ("FromCorner",)),
    ("Free kicks", ("FreeKick", "SetPiece")),
    ("Throw-ins", ("ThrowInSetPiece",)),
    ("Penalties", ("Penalty",)),
]


def set_play(s: pd.DataFrame, m: pd.DataFrame) -> dict:
    """Goals by how they were scored, from the shot maps (2020-21 onward)."""
    # Only seasons where (nearly) every match has a shot map.
    shot_matches = s.groupby("season").match_id.nunique()
    full = [x for x, n in shot_matches.items() if n >= 0.8 * (m.season == x).sum()]
    goals = s[s.is_goal & s.season.isin(full)].copy()
    kind = {sit: name for name, sits in GOAL_TYPES for sit in sits}
    goals["type"] = np.where(goals.own_goal.fillna(False), "Own goals", goals.situation.map(kind).fillna("Open play"))
    order = [n for n, _ in GOAL_TYPES] + ["Own goals"]
    by_season = []
    for season, g in goals.groupby("season"):
        counts = g.type.value_counts()
        total = int(len(g))
        set_total = int(sum(counts.get(n, 0) for n in ("Corners", "Free kicks", "Throw-ins", "Penalties")))
        by_season.append({
            "season": season, "label": season_label(season), "goals": total,
            "counts": {n: int(counts.get(n, 0)) for n in order},
            "set_play_pct": r(100 * set_total / total, 1),
            "direct_free_kicks": int((g.situation == "FreeKick").sum()),
        })
    # By club: goals scored, regular season and playoffs, own goals left out.
    scored = goals[goals.type != "Own goals"].merge(
        pd.concat([m[["match_id", "home_team_id", "home_team"]].rename(columns={"home_team_id": "team_id", "home_team": "team"}),
                   m[["match_id", "away_team_id", "away_team"]].rename(columns={"away_team_id": "team_id", "away_team": "team"})]),
        on=["match_id", "team_id"], how="left")
    by_club = []
    for team, g in scored.groupby("team"):
        if len(g) < 30:
            continue
        counts = g.type.value_counts()
        set_total = int(sum(counts.get(n, 0) for n in ("Corners", "Free kicks", "Throw-ins", "Penalties")))
        by_club.append({"team": team, "goals": int(len(g)), "counts": {n: int(counts.get(n, 0)) for n in order[:-1]},
                        "set_play_pct": r(100 * set_total / len(g), 1)})
    by_club.sort(key=lambda x: -x["set_play_pct"])
    return {"types": order, "by_season": by_season, "by_club": by_club,
            "first_season": season_label(min(goals.season))}


# ---------------------------------------------------------------- attendance

# FotMob has no crowd figures before 2019-20. League averages for those seasons are the
# published averages from https://en.wikipedia.org/wiki/Indian_Super_League_attendance
# (its figures match FotMob exactly for 2022-23 to 2024-25, which both cover).
WIKI_ATTENDANCE = {"2014": 24711, "2015": 27111, "2016": 21003, "2017-2018": 15047, "2018-2019": 13155}
CLOSED_DOORS = {"2020-2021", "2021-2022"}


def attendance(m: pd.DataFrame) -> dict:
    m = m.copy()
    by_season = []
    for season, g in m.groupby("season"):
        known = g.attendance.dropna()
        row = {"season": season, "label": season_label(season), "matches": int(len(g))}
        if season in CLOSED_DOORS:
            row.update(status="closed_doors", average=None, source=None)
        elif len(known) >= 0.8 * len(g):
            row.update(status="ok", average=r(known.mean(), 0), median=r(known.median(), 0), total=int(known.sum()),
                       highest=int(known.max()), matches_with_crowd=int(len(known)), source="FotMob")
        elif season in WIKI_ATTENDANCE:
            row.update(status="ok", average=WIKI_ATTENDANCE[season], source="Wikipedia")
        else:
            row.update(status="missing", average=None, source=None)
        by_season.append(row)

    crowd = m[m.attendance.notna() & ~m.season.isin(CLOSED_DOORS)]
    club = crowd.groupby(["home_team", "season"]).attendance.agg(["mean", "size"]).reset_index()
    club = club[club["size"] >= 3]
    clubs = []
    for team, g in club.groupby("home_team"):
        g = g.sort_values("season")
        clubs.append({
            "team": team,
            "seasons": [{"season": x.season, "label": season_label(x.season), "average": r(x["mean"], 0), "home_matches": int(x["size"])}
                        for _, x in g.iterrows()],
            "average_all": r(crowd[crowd.home_team == team].attendance.mean(), 0),
        })
    clubs.sort(key=lambda c: -c["average_all"])

    stad = crowd[crowd.stadium.notna()].groupby("stadium").agg(
        matches=("match_id", "size"), average=("attendance", "mean"), highest=("attendance", "max"),
        first_season=("season", "min"), last_season=("season", "max"),
        clubs=("home_team", lambda x: ", ".join(x.value_counts().index[:2])),
    ).reset_index()
    stad = stad[stad.matches >= 5]
    stad["first_season"] = stad.first_season.map(season_label)
    stad["last_season"] = stad.last_season.map(season_label)
    top = crowd.sort_values("attendance", ascending=False).head(10)
    return {
        "by_season": by_season,
        "by_club": clubs,
        "by_stadium": records(stad.sort_values("average", ascending=False), 1),
        "biggest_crowds": [{"season": season_label(x.season), "date": x.date, "home": x.home_team, "away": x.away_team,
                            "stadium": x.stadium, "attendance": int(x.attendance)} for _, x in top.iterrows()],
        "match_level_seasons": sorted({season_label(x) for x in crowd.season.unique() if (m.season == x).sum() and
                                       crowd[crowd.season == x].shape[0] >= 0.8 * (m.season == x).sum()}),
    }


# ---------------------------------------------------------------- team seasons

def team_seasons(m: pd.DataFrame, t: pd.DataFrame, teams: pd.DataFrame) -> list[dict]:
    rows = []
    for _, x in m.iterrows():
        for side, other in (("home", "away"), ("away", "home")):
            gf, ga = x[f"{side}_goals"], x[f"{other}_goals"]
            rows.append({"season": x.season, "match_id": x.match_id, "stage": x.stage, "team_id": x[f"{side}_team_id"],
                         "team": x[f"{side}_team"], "gf": gf, "ga": ga,
                         "pts": 3 if gf > ga else 1 if gf == ga else 0})
    res = pd.DataFrame(rows)
    reg = res[res.stage == "regular"]
    table = reg.groupby(["season", "team_id", "team"]).agg(
        played=("match_id", "size"), points=("pts", "sum"), goals_for=("gf", "sum"), goals_against=("ga", "sum"),
        wins=("pts", lambda x: (x == 3).sum()), draws=("pts", lambda x: (x == 1).sum()),
    ).reset_index()
    table["goal_diff"] = table.goals_for - table.goals_against
    table["points_per_match"] = table.points / table.played
    table["position"] = table.groupby("season")["points"].rank(method="first", ascending=False)
    table = table.sort_values(["season", "points", "goal_diff", "goals_for"], ascending=[True, False, False, False])
    table["position"] = table.groupby("season").cumcount() + 1

    tt = t.merge(m[["match_id", "stage"]], on="match_id")
    tt = tt[(tt.stage == "regular") & tt.total_shots.notna()]
    opp = tt[["match_id", "team_id", "expected_goals", "total_shots"]].rename(
        columns={"team_id": "opponent_id", "expected_goals": "xga", "total_shots": "shots_against"})
    tt = tt.merge(opp, on=["match_id", "opponent_id"], how="left")
    style = tt.groupby(["season", "team_id"]).agg(
        xg=("expected_goals", "sum"), xga=("xga", "sum"), possession=("ball_possesion", "mean"),
        shots_per_match=("total_shots", "mean"), shots_against_per_match=("shots_against", "mean"),
        passes_per_match=("accurate_passes", "mean"), tackles_per_match=("tackles", "mean"),
        long_balls_per_match=("long_balls_accurate", "mean"), crosses_per_match=("accurate_crosses", "mean"),
        has_xg=("expected_goals", lambda x: x.notna().all()),
    ).reset_index()
    style.loc[~style.has_xg, ["xg", "xga"]] = np.nan
    table = table.merge(style.drop(columns="has_xg"), on=["season", "team_id"], how="left")
    table["xg_diff"] = table.xg - table.xga
    finals = m[m["round"].astype(str).str.lower() == "final"]
    winners = {}
    for _, mm in finals.iterrows():
        if mm.home_goals != mm.away_goals:
            winners[mm.season] = mm.home_team if mm.home_goals > mm.away_goals else mm.away_team
        elif isinstance(mm.penalty_winner, str):
            winners[mm.season] = mm.penalty_winner
    table["won_final"] = [winners.get(s) == tm for s, tm in zip(table.season, table.team)]
    table["label"] = table.season.map(season_label)
    return records(table, 2)


# ---------------------------------------------------------------- player aggregates

def player_base(p: pd.DataFrame, s: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    p = p.merge(m[["match_id", "has_xg"]], on="match_id", how="left")
    p["minutes_xg"] = np.where(p.has_xg, p.minutes_played, 0)
    p["xg_cov"] = np.where(p.has_xg, p.expected_goals, 0)
    p["npxg_cov"] = np.where(p.has_xg, p.expected_goals_non_penalty, 0)
    p["goals_cov"] = np.where(p.has_xg, p.goals, 0)
    # FotMob's xG on target faced runs below goals conceded across the league (own goals and
    # some penalties carry no xGOT), so scale it so an average keeper prevents zero goals.
    gk = p.is_goalkeeper & p.expected_goals_on_target_faced.notna() & p.has_xg
    scale = p.loc[gk, "goals_conceded"].sum() / p.loc[gk, "expected_goals_on_target_faced"].sum()
    p["xgot_faced"] = p.expected_goals_on_target_faced * scale
    p.loc[~gk, "xgot_faced"] = np.nan
    p["minutes_gk_xgot"] = np.where(gk, p.minutes_played, 0)
    p["conceded_gk_xgot"] = np.where(gk, p.goals_conceded, 0)
    p["clean_sheet"] = (p.is_goalkeeper & (p.goals_conceded == 0) & (p.minutes_played >= 60)).astype(int)
    p["gk_full"] = (p.is_goalkeeper & (p.minutes_played >= 60)).astype(int)

    shots = s[~s.own_goal.fillna(False)]
    pens = shots[shots.situation == "Penalty"].groupby(["season", "match_id", "player_id"]).agg(
        pen_goals=("is_goal", "sum"), pens_taken=("is_goal", "size"))
    fk = shots[shots.situation == "FreeKick"].groupby(["season", "match_id", "player_id"]).agg(
        fk_goals=("is_goal", "sum"), fk_shots=("is_goal", "size"), fk_xg=("xg", "sum"))
    p = p.join(pens, on=["season", "match_id", "player_id"]).join(fk, on=["season", "match_id", "player_id"])
    for c in ("pen_goals", "pens_taken", "fk_goals", "fk_shots", "fk_xg"):
        p[c] = p[c].fillna(0)
    # Penalty goals only count where the shot map exists.
    p["np_goals"] = p.goals - p.pen_goals
    p["np_shots"] = p.total_shots - p.pens_taken
    return p


def aggregate(p: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    agg = {k: (v, "sum") for k, v in SUM_COLS.items()}
    agg.update(
        matches=("match_id", "nunique"), starts=("started", "sum"), minutes_xg=("minutes_xg", "sum"),
        xg=("xg_cov", "sum"), npxg=("npxg_cov", "sum"), goals_in_xg_matches=("goals_cov", "sum"),
        np_goals=("np_goals", "sum"), np_shots=("np_shots", "sum"), pen_goals=("pen_goals", "sum"),
        pens_taken=("pens_taken", "sum"), fk_goals=("fk_goals", "sum"), fk_shots=("fk_shots", "sum"),
        fk_xg=("fk_xg", "sum"), xgot_faced=("xgot_faced", "sum"), minutes_gk_xgot=("minutes_gk_xgot", "sum"),
        conceded_gk_xgot=("conceded_gk_xgot", "sum"), clean_sheets=("clean_sheet", "sum"), gk_full=("gk_full", "sum"),
        rating=("rating_title", "mean"), team=("team", lambda x: x.mode().iloc[0]),
        teams=("team", lambda x: ", ".join(dict.fromkeys(x))),
        first_season=("season", "min"), last_season=("season", "max"), seasons=("season", "nunique"),
    )
    a = p.groupby(keys).agg(**agg).reset_index()
    per90 = lambda col, mins="minutes": 90 * a[col] / a[mins].replace(0, np.nan)
    pct = lambda num, den: 100 * a[num] / a[den].replace(0, np.nan)
    for c in ("goals", "assists", "shots", "xa", "chances_created", "passes", "final_third_passes", "long_balls",
              "crosses", "dribbles", "tackles", "interceptions", "clearances", "blocks", "recoveries", "dribbled_past",
              "box_touches", "saves", "high_claims", "sweeper", "np_goals"):
        a[f"{c}_p90"] = per90(c)
    a["xg_p90"] = per90("xg", "minutes_xg")
    a["npxg_p90"] = per90("npxg", "minutes_xg")
    a["tackles_interceptions_p90"] = per90("tackles") + per90("interceptions")
    a["pass_pct"] = pct("passes", "passes_att")
    a["dribble_pct"] = pct("dribbles", "dribbles_att")
    a["aerial_pct"] = pct("aerials_won", "aerials_att")
    a["ground_duel_pct"] = pct("ground_duels_won", "ground_duels_att")
    a["duel_pct"] = 100 * a.duels_won / (a.duels_won + a.duels_lost).replace(0, np.nan)
    a["conversion_pct"] = pct("np_goals", "np_shots")
    a["on_target_pct"] = pct("shots_on_target", "shots")
    a["goals_minus_xg"] = a.goals_in_xg_matches - a.xg
    a["save_pct"] = 100 * a.saves / (a.saves + a.goals_conceded).replace(0, np.nan)
    a["goals_prevented"] = a.xgot_faced - a.conceded_gk_xgot
    a["goals_prevented_p90"] = 90 * a.goals_prevented / a.minutes_gk_xgot.replace(0, np.nan)
    a["clean_sheet_pct"] = pct("clean_sheets", "gk_full")
    return a


def score(a: pd.DataFrame, group_col: str = "position_group", within: list[str] | None = None) -> pd.DataFrame:
    """Percentile-based score per position (0-100), plus each metric's percentile."""
    a = a.copy()
    a["score"] = np.nan
    for pos, metrics in METRICS.items():
        mask = a[group_col] == pos
        groups = [mask] if not within else [mask & (a[within[0]] == v) for v in a.loc[mask, within[0]].unique()]
        for gmask in groups:
            sub = a[gmask]
            if sub.empty:
                continue
            total, weights = 0, 0
            for spec in metrics:
                col, w = spec[0], spec[1]
                lower = len(spec) > 3 and spec[3] == "lower"
                vals = sub[col]
                pctile = vals.rank(pct=True, ascending=not lower) * 100
                a.loc[gmask, f"pct_{col}"] = pctile
                total = total + pctile.fillna(50) * w
                weights += w
            a.loc[gmask, "score"] = total / weights
    return a


def main() -> None:
    m, t, p, s, pl, teams, goals = load()
    pl_info = pl.set_index("player_id")[["position_group", "main_role", "country", "country_code", "is_indian"]]

    write("seasons.json", league_trends(m, t, s, p))
    write("teams.json", team_seasons(m, t, teams))
    write("set_play.json", set_play(s, m))
    write("attendance.json", attendance(m))

    base = player_base(p, s, m)
    base = base[base.season >= "2019"]  # seasons with player stats for (almost) every match

    career = aggregate(base, ["player_id"]).join(pl_info, on="player_id")
    names = p.sort_values("season").groupby("player_id").player.last()
    career["player"] = career.player_id.map(names)
    career_q = score(career[career.minutes >= CAREER_MIN_MINUTES])

    seasonal = aggregate(base, ["player_id", "season"]).join(pl_info, on="player_id")
    seasonal["player"] = seasonal.player_id.map(names)
    season_q = score(seasonal[seasonal.minutes >= SEASON_MIN_MINUTES], within=["season"])

    # ---- positions
    positions = {}
    for pos in POSITIONS:
        cols = [mm[0] for mm in METRICS[pos]]
        sub = career_q[career_q.position_group == pos].sort_values("score", ascending=False)
        keep = ["player_id", "player", "country", "is_indian", "teams", "first_season", "last_season", "matches",
                "minutes", "goals", "assists", "score"] + cols + [f"pct_{c}" for c in cols]
        positions[pos] = {"qualified": int(len(sub)), "players": records(sub[keep].head(25))}
    write("positions.json", positions)

    # ---- best XI (4-3-3)
    shape = [("Goalkeeper", 1), ("Full-back", 2), ("Centre-back", 2), ("Central midfielder", 3),
             ("Attacking midfielder / winger", 2), ("Striker", 1)]

    def xi(df: pd.DataFrame) -> list[dict]:
        out = []
        for pos, n in shape:
            top = df[df.position_group == pos].sort_values("score", ascending=False).head(n)
            for _, x in top.iterrows():
                out.append({"position": pos, "player": x.player, "player_id": int(x.player_id), "country": x.country,
                            "teams": x.teams, "score": r(x.score, 1), "minutes": int(x.minutes),
                            "goals": int(x.goals), "assists": int(x.assists)})
        return out

    per_season = []
    for season, g in season_q.groupby("season"):
        for pos in POSITIONS:
            top = g[g.position_group == pos].sort_values("score", ascending=False).head(3)
            per_season.append({"season": season, "label": season_label(season), "position": pos,
                               "top": [{"player": x.player, "team": x.team, "score": r(x.score, 1)} for _, x in top.iterrows()]})
    write("best_xi.json", {
        "formation": "4-3-3",
        "all_time": xi(career_q),
        "all_time_indian": xi(career_q[career_q.is_indian == True]),
        "by_season": per_season,
    })

    # ---- leaderboards (career, all qualified unless a stat needs its own sample)
    c = career.copy()
    lb = {}

    def top(df, col, n=15, asc=False, extra=()):
        cols = ["player", "country", "teams", "matches", "minutes", col, *extra]
        return records(df.sort_values(col, ascending=asc).head(n)[cols])

    shooters = c[c.minutes_xg >= CAREER_MIN_MINUTES]
    # All-time scorers come from the goal list, which covers every season since 2014.
    g = goals[~goals.own_goal]
    key = g.player_id.fillna(-1).astype(int).astype(str).where(g.player_id.notna(), "name:" + g.player)
    scorers = g.assign(key=key).groupby("key").agg(
        player=("player", "last"), goals=("match_id", "size"), penalties=("penalty", "sum"),
        seasons=("season", "nunique"), first_season=("season", "min"), last_season=("season", "max"),
        teams=("team", lambda x: ", ".join(dict.fromkeys(x))),
    ).sort_values("goals", ascending=False).head(25)
    lb["goals_all_time"] = records(scorers.reset_index(drop=True))
    lb["goals"] = top(c, "goals", extra=("pen_goals", "goals_p90"))
    lb["assists"] = top(c, "assists", extra=("xa",))
    lb["xg"] = top(shooters, "xg", extra=("goals_in_xg_matches",))
    lb["overperformers"] = top(shooters[shooters.xg >= 5], "goals_minus_xg", extra=("goals_in_xg_matches", "xg"))
    lb["underperformers"] = top(shooters[shooters.xg >= 5], "goals_minus_xg", asc=True, extra=("goals_in_xg_matches", "xg"))
    lb["conversion"] = top(c[c.np_shots >= 50], "conversion_pct", extra=("np_goals", "np_shots"))
    lb["free_kick_goals"] = top(c[c.fk_goals > 0], "fk_goals", extra=("fk_shots", "fk_xg"))
    q = c[c.minutes >= CAREER_MIN_MINUTES]
    lb["dribbles_p90"] = top(q, "dribbles_p90", extra=("dribbles", "dribble_pct"))
    lb["chances_created_p90"] = top(q, "chances_created_p90", extra=("chances_created",))
    lb["passes_p90"] = top(q, "passes_p90", extra=("pass_pct",))
    lb["tackles_p90"] = top(q, "tackles_p90", extra=("tackles",))
    lb["interceptions_p90"] = top(q, "interceptions_p90", extra=("interceptions",))
    lb["clearances_p90"] = top(q, "clearances_p90", extra=("clearances",))
    gk = q[q.position_group == "Goalkeeper"]
    lb["goals_prevented"] = top(gk, "goals_prevented", extra=("goals_prevented_p90", "save_pct"))
    lb["clean_sheets"] = top(c[c.position_group == "Goalkeeper"], "clean_sheets", extra=("clean_sheet_pct",))
    write("leaderboards.json", lb)

    # ---- explorer rows
    exp_cols = ["player_id", "player", "season", "team", "position_group", "country", "is_indian", "matches", "minutes",
                "goals", "assists", "xg", "xa", "np_goals_p90", "npxg_p90", "xa_p90", "conversion_pct", "shots_p90",
                "chances_created_p90", "dribbles_p90", "dribble_pct", "passes_p90", "pass_pct", "final_third_passes_p90",
                "tackles_p90", "interceptions_p90", "clearances_p90", "blocks_p90", "recoveries_p90", "aerial_pct",
                "saves_p90", "save_pct", "goals_prevented", "clean_sheets", "fk_goals", "rating"]
    sq = seasonal.merge(season_q[["player_id", "season", "score"]], on=["player_id", "season"], how="left")
    write("players.json", records(sq[sq.minutes >= 270][exp_cols + ["score"]]))

    write("meta.json", {
        "generated": date.today().isoformat(),
        "career_min_minutes": CAREER_MIN_MINUTES,
        "season_min_minutes": SEASON_MIN_MINUTES,
        "player_seasons": sorted(base.season.unique().tolist()),
        "xg_seasons": sorted(m[m.has_xg].season.unique().tolist()),
        "metrics": {pos: [{"stat": x[0], "weight": x[1], "label": x[2], "lower_is_better": len(x) > 3}
                          for x in mm] for pos, mm in METRICS.items()},
        "sources": ["FotMob", "StatsBomb open data"],
        "notes": {
            "player_stats": "Per-player stats start in 2019-20 (2018-19 has them for only 15 matches), so rankings and most leaderboards cover 2019-20 onward.",
            "xg": "xG starts in 2020-21. Per-90 xG rates use minutes from matches with xG only.",
            "goals_all_time": "The all-time scorers list uses every goal since 2014.",
            "goals_prevented": "Goals prevented compared with an average ISL keeper: xG on target faced (scaled so the league total matches goals conceded) minus goals conceded. From 2020-21.",
        },
    })


if __name__ == "__main__":
    main()
