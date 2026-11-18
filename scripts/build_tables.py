"""Turn the raw FotMob downloads into tidy tables.

Reads data/raw/fotmob/ and writes data/processed/ (git-ignored):

  matches.csv         one row per finished match: teams, score, stage, data coverage
  team_matches.csv    one row per team per match: goals, xG, shots, passes, tackles...
  player_matches.csv  one row per player per match: minutes, role, every FotMob player stat
  shots.csv           one row per shot: location, xG, xGOT, situation (open play, free kick...)
  players.csv         one row per player: nationality, main role, position group, matches, minutes
  teams.csv           one row per club: current name and former names
  goals.csv           one row per goal in every season since 2014: scorer, minute, penalty, own goal

Usage: python scripts/build_tables.py
"""

from __future__ import annotations

import json
import re
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "fotmob"
OUT = ROOT / "data" / "processed"

# FotMob already keeps one id per club through renames and shows the current name.
# Former names are listed here so the report can mention them.
FORMER_NAMES = {
    "Mohun Bagan SG": "ATK (2014–20), ATK Mohun Bagan (2020–23)",
    "Odisha FC": "Delhi Dynamos (2014–19)",
    "SC Delhi": "Hyderabad FC (2019–25)",
    "East Bengal FC": "SC East Bengal (2020–23)",
    "Punjab FC": "RoundGlass Punjab (2023)",
    "Northeast United FC": "",
    "Kerala Blasters FC": "",
}

# FotMob lineup slot ids encode the row (tens and above) and the lane (last digit,
# 2 = right touchline ... 8 = left touchline). 11 is the goalkeeper.
WIDE_LANES = {2, 8}


def role_from_slot(slot: int | None) -> str | None:
    if slot is None or slot <= 0:
        return None
    if slot == 11:
        return "GK"
    row, lane = divmod(slot, 10)
    if row in (3, 4, 5):
        return "FB" if lane in WIDE_LANES else "CB"
    if row == 6:
        return "DM"
    if row == 7:
        return "WM" if lane in WIDE_LANES else "CM"
    if row == 8:
        return "W" if lane in (2, 3, 7, 8) else "AM"
    if row >= 9:
        return "W" if lane in WIDE_LANES else "ST"
    return None


# Roles grouped into the positions used for "best player per position".
POSITION_GROUP = {
    "GK": "Goalkeeper",
    "CB": "Centre-back",
    "FB": "Full-back",
    "DM": "Central midfielder",
    "CM": "Central midfielder",
    "AM": "Attacking midfielder / winger",
    "WM": "Attacking midfielder / winger",
    "W": "Attacking midfielder / winger",
    "ST": "Striker",
}
USUAL_POSITION = {0: "Goalkeeper", 1: "Defender", 2: "Midfielder", 3: "Forward"}
FALLBACK_GROUP = {0: "Goalkeeper", 1: "Centre-back", 2: "Central midfielder", 3: "Striker"}


def snake(text: str) -> str:
    text = text.replace("matchstats.headers.", "")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


PLAYOFF_WORDS = ("final", "semi", "quarter", "play-off", "playoff", "knockout", "eliminator")


def stage_of(round_name) -> str:
    name = str(round_name or "").lower()
    return "playoff" if any(w in name for w in PLAYOFF_WORDS) else "regular"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def seasons() -> list[Path]:
    return sorted(p for p in RAW.iterdir() if p.is_dir())


def parse_score(score: str | None) -> tuple[int | None, int | None]:
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)", score or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def team_stats(content: dict) -> list[dict]:
    """Flatten the match's team stats into {key: value} for home and away."""
    home, away = {}, {}
    periods = ((content.get("stats") or {}).get("Periods") or {}).get("All") or {}
    for group in periods.get("stats") or []:
        for s in group.get("stats") or []:
            key, raw = s.get("key"), s.get("rawStats") or s.get("stats")
            if not key or key == group.get("key") or not isinstance(raw, list) or len(raw) != 2:
                continue
            vals = [r.get("value") if isinstance(r, dict) else r for r in raw]
            try:
                home[snake(key)], away[snake(key)] = (float(v) if v is not None else None for v in vals)
            except (TypeError, ValueError):
                continue
    return [home, away]


def player_stat_values(player: dict) -> dict:
    out = {}
    for group in player.get("stats") or []:
        for label, item in (group.get("stats") or {}).items():
            key = item.get("key")
            stat = item.get("stat") or {}
            if not key or stat.get("type") == "boolean":
                continue
            key = snake(key)
            if key in out:
                continue
            out[key] = stat.get("value")
            if "total" in stat:
                out[f"{key}_attempted"] = stat.get("total")
    return out


def lineup_info(content: dict) -> dict[int, dict]:
    """Starter slot, subbed minutes and nationality for each player in the lineup."""
    info = {}
    lineup = content.get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side) or {}
        for started, key in ((True, "starters"), (False, "subs")):
            for p in team.get(key) or []:
                if "id" not in p:
                    continue
                info[p["id"]] = {
                    "started": started,
                    "slot": p.get("positionId") if started else None,
                    "usual_position_id": p.get("usualPlayingPositionId"),
                    "country": p.get("countryName"),
                    "country_code": p.get("countryCode"),
                }
    return info


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    matches, team_rows, player_rows, shot_rows, goal_rows = [], [], [], [], []
    team_names: dict[int, str] = {}

    for sdir in seasons():
        season = sdir.name
        league = load(sdir / "league.json")
        for fx in (league.get("fixtures") or {}).get("allMatches") or []:
            status = fx.get("status") or {}
            if not status.get("finished"):
                continue
            mid = int(fx["id"])
            hid, aid = int(fx["home"]["id"]), int(fx["away"]["id"])
            team_names[hid], team_names[aid] = fx["home"]["name"], fx["away"]["name"]
            hg, ag = parse_score(status.get("scoreStr"))
            row = {
                "season": season,
                "match_id": mid,
                "date": (status.get("utcTime") or "")[:10],
                "round": fx.get("roundName"),
                "stage": stage_of(fx.get("roundName")),
                "home_team_id": hid,
                "home_team": fx["home"]["name"],
                "away_team_id": aid,
                "away_team": fx["away"]["name"],
                "home_goals": hg,
                "away_goals": ag,
                "decided_on_penalties": False,
                "penalty_winner": None,
                "has_lineups": False,
                "has_player_stats": False,
                "has_xg": False,
            }
            path = sdir / "matches" / f"{mid}.json"
            if path.exists():
                data = load(path)
                content = data.get("content") or {}
                hs = (data.get("header") or {}).get("status") or {}
                loser = hs.get("whoLostOnPenalties")
                row["decided_on_penalties"] = bool(loser)
                if loser:
                    # The header uses the club's name at the time, so compare against it.
                    header_home = (((data.get("header") or {}).get("teams") or [{}])[0]).get("name")
                    row["penalty_winner"] = fx["away"]["name"] if loser == header_home else fx["home"]["name"]

                events = ((content.get("matchFacts") or {}).get("events") or {}).get("events") or []
                for e in events:
                    if e.get("type") != "Goal" or e.get("isPenaltyShootoutEvent"):
                        continue
                    desc = str(e.get("goalDescription") or e.get("suffix") or "").lower()
                    own = bool(e.get("ownGoal"))
                    goal_rows.append(
                        {"season": season, "match_id": mid, "minute": e.get("time"),
                         "team_id": (hid if e.get("isHome") else aid) if not own else (aid if e.get("isHome") else hid),
                         "player_id": e.get("playerId") or None, "player": e.get("fullName") or e.get("nameStr"),
                         "own_goal": own, "penalty": "pen" in desc, "assist": e.get("assistStr")}
                    )
                lineup = lineup_info(content)
                row["has_lineups"] = bool(lineup)

                for side, stats in zip(("home", "away"), team_stats(content)):
                    tid = hid if side == "home" else aid
                    gf, ga = (hg, ag) if side == "home" else (ag, hg)
                    team_rows.append(
                        {"season": season, "match_id": mid, "team_id": tid, "team": team_names[tid],
                         "opponent_id": aid if side == "home" else hid, "is_home": side == "home",
                         "goals": gf, "goals_against": ga, **stats}
                    )
                row["has_xg"] = any(r.get("expected_goals") is not None for r in team_rows[-2:])

                pstats = content.get("playerStats") or {}
                row["has_player_stats"] = bool(pstats)
                for p in pstats.values():
                    pid = int(p["id"])
                    if pid <= 0:
                        # A few players have no FotMob id; give each a stable id from their name.
                        pid = -zlib.crc32(str(p.get("name")).encode())
                    li = lineup.get(pid, {})
                    vals = player_stat_values(p)
                    if not vals.get("minutes_played"):
                        continue
                    slot = li.get("slot")
                    usual = li.get("usual_position_id")
                    if usual is None or usual < 0:
                        usual = p.get("usualPosition")
                    player_rows.append(
                        {"season": season, "match_id": mid, "player_id": pid, "player": p.get("name"),
                         "team_id": int(p["teamId"]), "team": team_names.get(int(p["teamId"]), p.get("teamName")),
                         "is_goalkeeper": bool(p.get("isGoalkeeper")), "started": li.get("started"),
                         "slot": slot, "role": role_from_slot(slot), "usual_position_id": usual,
                         "country": li.get("country"), "country_code": li.get("country_code"), **vals}
                    )

                for s in (content.get("shotmap") or {}).get("shots") or []:
                    shot_rows.append(
                        {"season": season, "match_id": mid, "shot_id": s.get("id"), "team_id": s.get("teamId"),
                         "player_id": s.get("playerId"), "player": s.get("playerName"), "minute": s.get("min"),
                         "period": s.get("period"), "event": s.get("eventType"), "situation": s.get("situation"),
                         "shot_type": s.get("shotType"), "x": s.get("x"), "y": s.get("y"),
                         "xg": s.get("expectedGoals"), "xgot": s.get("expectedGoalsOnTarget"),
                         "on_target": s.get("isOnTarget"), "blocked": s.get("isBlocked"),
                         "own_goal": s.get("isOwnGoal"), "is_goal": s.get("eventType") == "Goal"}
                    )
            matches.append(row)

    m = pd.DataFrame(matches)
    t = pd.DataFrame(team_rows)
    p = pd.DataFrame(player_rows)
    s = pd.DataFrame(shot_rows)
    gl = pd.DataFrame(goal_rows)

    # A stat that FotMob tracked in a match but left blank for a player means zero.
    stat_cols = [c for c in p.columns if c not in {
        "season", "match_id", "player_id", "player", "team_id", "team", "is_goalkeeper", "started",
        "slot", "role", "usual_position_id", "country", "country_code", "rating_title"}]
    tracked = p.groupby("match_id")[stat_cols].transform(lambda c: c.notna().any())
    p[stat_cols] = p[stat_cols].where(~(tracked & p[stat_cols].isna()), 0)

    # Main role: the slot a player started in most often; fall back to FotMob's usual position.
    starts = p.dropna(subset=["role"])
    main_role = starts.groupby("player_id")["role"].agg(lambda r: Counter(r).most_common(1)[0][0])
    info = p.sort_values("season").groupby("player_id").agg(
        player=("player", "last"), country=("country", lambda c: c.dropna().iloc[-1] if c.notna().any() else None),
        country_code=("country_code", lambda c: c.dropna().iloc[-1] if c.notna().any() else None),
        usual_position_id=("usual_position_id", lambda c: c.dropna().mode().iloc[0] if c.notna().any() else None),
        seasons=("season", "nunique"), matches=("match_id", "nunique"), starts=("started", "sum"),
        minutes=("minutes_played", "sum"), last_team=("team", "last"),
    )
    info["main_role"] = main_role
    info["position_group"] = [
        POSITION_GROUP.get(r) if isinstance(r, str) else FALLBACK_GROUP.get(u)
        for r, u in zip(info["main_role"], info["usual_position_id"])
    ]
    info["usual_position"] = info["usual_position_id"].map(USUAL_POSITION)
    info["is_indian"] = info["country_code"].eq("IND")
    p["position_group"] = p["player_id"].map(info["position_group"])

    teams = pd.DataFrame(
        [{"team_id": k, "team": v, "former_names": FORMER_NAMES.get(v, "")} for k, v in sorted(team_names.items())]
    )
    span = m.melt(id_vars="season", value_vars=["home_team_id", "away_team_id"], value_name="team_id")
    seasons_per_team = span.groupby("team_id")["season"].agg(["min", "max", "nunique"])
    teams = teams.join(seasons_per_team.rename(columns={"min": "first_season", "max": "last_season", "nunique": "seasons"}), on="team_id")

    # Early seasons have no player ids on goals: match them by exact name where that name is unique.
    if not gl.empty:
        gl["team_id"] = gl.team_id.astype(int)
        known = p.groupby("player")["player_id"].agg(lambda x: x.iloc[0] if x.nunique() == 1 else None).dropna()
        missing = gl.player_id.isna()
        gl.loc[missing, "player_id"] = gl.loc[missing, "player"].map(known)
        gl["team"] = gl.team_id.map(team_names)

    m.to_csv(OUT / "matches.csv", index=False)
    gl.to_csv(OUT / "goals.csv", index=False)
    t.to_csv(OUT / "team_matches.csv", index=False)
    p.to_csv(OUT / "player_matches.csv", index=False)
    s.to_csv(OUT / "shots.csv", index=False)
    info.reset_index().to_csv(OUT / "players.csv", index=False)
    teams.to_csv(OUT / "teams.csv", index=False)

    print(f"matches {len(m)}, team rows {len(t)}, player rows {len(p)}, shots {len(s)}, "
          f"players {len(info)}, clubs {len(teams)}, goals {len(gl)}")


if __name__ == "__main__":
    main()
