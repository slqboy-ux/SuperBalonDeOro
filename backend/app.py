from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

DB_PATH = Path(__file__).resolve().parent / "data.db"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="SuperBalon MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_players (
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(team_id, player_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                home_team_id INTEGER NOT NULL,
                away_team_id INTEGER NOT NULL,
                home_goals INTEGER NOT NULL DEFAULT 0,
                away_goals INTEGER NOT NULL DEFAULT 0,
                played_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(home_team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY(away_team_id) REFERENCES teams(id) ON DELETE CASCADE,
                CHECK (home_team_id <> away_team_id)
            )
            """
        )

        defaults = {
            "season_name": "Temporada 2026",
            "tagline": "Pega la lista de amigos, arma equipos y seguí la tabla en segundos.",
            "brand": "SUPERBALON DE ORO",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

        conn.commit()


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    return {
        "brand": data.get("brand", "SuperBalon"),
        "season_name": data.get("season_name", "Temporada 2026"),
        "tagline": data.get("tagline", "Liga casual de amigos"),
    }


@app.post("/config")
def update_config(payload: dict[str, str]) -> dict[str, str]:
    season_name = (payload.get("season_name") or "").strip()
    tagline = (payload.get("tagline") or "").strip()
    brand = (payload.get("brand") or "").strip()

    with get_conn() as conn:
        if season_name:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('season_name', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (season_name,),
            )
        if tagline:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('tagline', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (tagline,),
            )
        if brand:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('brand', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (brand,),
            )
        conn.commit()

    return get_config()


@app.get("/players")
def get_players() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name FROM players ORDER BY name ASC"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/players")
def create_player(payload: dict[str, str]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")

    with get_conn() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO players (name) VALUES (?)",
                (name,),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Ese jugador ya existe") from None

    return {"id": cursor.lastrowid, "name": name}


@app.delete("/players")
def delete_players() -> dict[str, str]:
    with get_conn() as conn:
        conn.execute("DELETE FROM players")
        conn.execute("DELETE FROM team_players")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM teams")
        conn.commit()
    return {"status": "all_players_removed"}


@app.get("/teams")
def get_teams() -> list[dict[str, Any]]:
    with get_conn() as conn:
        team_rows = conn.execute(
            "SELECT id, name FROM teams ORDER BY id"
        ).fetchall()

        result: list[dict[str, Any]] = []
        for team in team_rows:
            members = conn.execute(
                """
                SELECT p.id, p.name
                FROM team_players tp
                INNER JOIN players p ON p.id = tp.player_id
                WHERE tp.team_id = ?
                ORDER BY p.name ASC
                """,
                (team["id"],),
            ).fetchall()
            result.append({
                "id": team["id"],
                "name": team["name"],
                "players": [dict(member) for member in members],
            })
    return result


@app.post("/teams/generate")
def generate_teams(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    team_size = int(data.get("team_size") or 2)
    if team_size < 1:
        raise HTTPException(status_code=400, detail="El tamaño del equipo debe ser mayor a 0")

    with get_conn() as conn:
        players = conn.execute("SELECT id, name FROM players ORDER BY name ASC").fetchall()
        if len(players) < 2:
            raise HTTPException(status_code=400, detail="Necesitás al menos 2 jugadores para armar equipos")

        conn.execute("DELETE FROM team_players")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM teams")

        shuffled = [row for row in players]
        random.shuffle(shuffled)

        teams: list[dict[str, Any]] = []
        current_team: list[sqlite3.Row] = []
        for player in shuffled:
            current_team.append(player)
            if len(current_team) == team_size:
                teams.append(current_team)
                current_team = []

        if current_team:
            # last partial team, keep as is
            teams.append(current_team)

        if not teams:
            raise HTTPException(status_code=400, detail="No se pudieron generar equipos")

        for index, squad in enumerate(teams, start=1):
            team_name = f"Equipo {index}"
            cursor = conn.execute(
                "INSERT INTO teams (name) VALUES (?)",
                (team_name,),
            )
            team_id = cursor.lastrowid
            for player in squad:
                conn.execute(
                    "INSERT INTO team_players (team_id, player_id) VALUES (?, ?)",
                    (team_id, player["id"]),
                )

        conn.commit()

    return {"status": "teams_generated", "count": len(teams)}


@app.get("/matches")
def get_matches() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
                   ht.name AS home_name, at.name AS away_name, m.played_at
            FROM matches m
            INNER JOIN teams ht ON ht.id = m.home_team_id
            INNER JOIN teams at ON at.id = m.away_team_id
            ORDER BY m.played_at DESC, m.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/matches")
def add_match(payload: dict[str, Any]) -> dict[str, Any]:
    home_team_id = int(payload.get("home_team_id") or 0)
    away_team_id = int(payload.get("away_team_id") or 0)
    home_goals = int(payload.get("home_goals") or 0)
    away_goals = int(payload.get("away_goals") or 0)

    if home_team_id == away_team_id:
        raise HTTPException(status_code=400, detail="El equipo local y visitante no pueden ser iguales")
    if home_goals < 0 or away_goals < 0:
        raise HTTPException(status_code=400, detail="Los goles no pueden ser negativos")

    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM teams WHERE id IN (?, ?)",
            (home_team_id, away_team_id),
        ).fetchall()
        if len(exists) != 2:
            raise HTTPException(status_code=400, detail="Uno o ambos equipos no existen")

        cursor = conn.execute(
            """
            INSERT INTO matches (home_team_id, away_team_id, home_goals, away_goals)
            VALUES (?, ?, ?, ?)
            """,
            (home_team_id, away_team_id, home_goals, away_goals),
        )
        conn.commit()

    return {"id": cursor.lastrowid, "status": "match_saved"}


@app.get("/standings")
def get_standings() -> list[dict[str, Any]]:
    with get_conn() as conn:
        player_rows = conn.execute("SELECT id, name FROM players ORDER BY name ASC").fetchall()
        match_rows = conn.execute(
            """
            SELECT home_team_id, away_team_id, home_goals, away_goals
            FROM matches
            ORDER BY id ASC
            """
        ).fetchall()

        standings: list[dict[str, Any]] = []
        for player in player_rows:
            stats = {
                "player_id": player["id"],
                "player_name": player["name"],
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "points": 0,
            }

            for match in match_rows:
                home_team_id = match["home_team_id"]
                away_team_id = match["away_team_id"]
                home_goals = match["home_goals"]
                away_goals = match["away_goals"]

                home_players = conn.execute(
                    "SELECT player_id FROM team_players WHERE team_id = ?",
                    (home_team_id,),
                ).fetchall()
                away_players = conn.execute(
                    "SELECT player_id FROM team_players WHERE team_id = ?",
                    (away_team_id,),
                ).fetchall()

                home_player_ids = {row["player_id"] for row in home_players}
                away_player_ids = {row["player_id"] for row in away_players}

                if player["id"] in home_player_ids or player["id"] in away_player_ids:
                    stats["played"] += 1

                    if player["id"] in home_player_ids:
                        stats["goals_for"] += home_goals
                        stats["goals_against"] += away_goals
                        if home_goals > away_goals:
                            stats["wins"] += 1
                            stats["points"] += 3
                        elif home_goals < away_goals:
                            stats["losses"] += 1
                        else:
                            stats["draws"] += 1
                            stats["points"] += 1
                    else:
                        stats["goals_for"] += away_goals
                        stats["goals_against"] += home_goals
                        if away_goals > home_goals:
                            stats["wins"] += 1
                            stats["points"] += 3
                        elif away_goals < home_goals:
                            stats["losses"] += 1
                        else:
                            stats["draws"] += 1
                            stats["points"] += 1

            stats["goal_difference"] = stats["goals_for"] - stats["goals_against"]
            standings.append(stats)

        standings.sort(
            key=lambda item: (
                item["points"],
                item["goal_difference"],
                item["goals_for"],
                item["player_name"],
            ),
            reverse=True,
        )

        for index, row in enumerate(standings, start=1):
            row["position"] = index

        return standings


@app.get("/summary")
def get_summary() -> dict[str, Any]:
    standings = get_standings()
    champion = standings[0] if standings else None
    config = get_config()
    return {
        "brand": config["brand"],
        "season_name": config["season_name"],
        "tagline": config["tagline"],
        "total_players": len(get_players()),
        "total_teams": len(get_teams()),
        "total_matches": len(get_matches()),
        "champion": champion,
        "standings": standings,
    }


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
