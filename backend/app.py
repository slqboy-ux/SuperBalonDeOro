from __future__ import annotations

import os
import random
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data.db"
DB_PATH = Path(os.environ.get("SUPERBALON_DB_PATH", str(DEFAULT_DB_PATH)))
DATABASE_URL = os.environ.get("DATABASE_URL")


def _is_production_environment() -> bool:
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RENDER")
        or os.environ.get("APP_ENV") == "production"
    )


if _is_production_environment() and not DATABASE_URL:
    print(
        "WARNING: DATABASE_URL no está configurada en producción. "
        "La app va a usar SQLite local hasta que la base persistente esté conectada."
    )

if _is_production_environment() and DATABASE_URL and psycopg is None:
    print(
        "WARNING: psycopg no está disponible. "
        "La app va a usar SQLite local aunque el entorno sea de producción."
    )

USE_POSTGRES = bool(DATABASE_URL and psycopg is not None)

frontend_candidates = [
    BASE_DIR / "frontend",
    BASE_DIR.parent / "frontend",
]
FRONTEND_DIR = next((candidate for candidate in frontend_candidates if candidate.exists()), frontend_candidates[0])

if not FRONTEND_DIR.exists():
    raise RuntimeError(f"Frontend directory not found. Checked: {[str(path) for path in frontend_candidates]}")

app = FastAPI(title="SuperBalon MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_query(query: str, params: Any) -> tuple[str, Any]:
    if not USE_POSTGRES:
        return query, params
    if params is None:
        return query, params
    return query.replace("?", "%s"), params


def get_conn():
    if USE_POSTGRES:
        conn = psycopg.connect(DATABASE_URL, autocommit=False)
        conn.row_factory = dict_row

        original_execute = conn.execute

        def execute(query: str, params: Any = None, *args: Any, **kwargs: Any):
            normalized_query, normalized_params = normalize_query(query, params)
            return original_execute(normalized_query, normalized_params, *args, **kwargs)

        conn.execute = execute
        return conn

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def last_insert_id(cursor: Any) -> Any:
    try:
        row = cursor.fetchone()
    except Exception:
        row = None

    if row is not None:
        if isinstance(row, dict):
            return row.get("id")
        return row[0]

    if hasattr(cursor, "lastrowid") and cursor.lastrowid is not None:
        return cursor.lastrowid
    return None


def ensure_column(table_name: str, column_name: str, column_sql: str) -> None:
    with get_conn() as conn:
        if USE_POSTGRES:
            existing = conn.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
                (table_name, column_name),
            ).fetchone()
            if existing is None:
                conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_sql}')
            conn.commit()
            return

        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not any(column[1] == column_name for column in columns):
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        conn.commit()


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
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                password TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_id INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, group_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_id INTEGER NOT NULL DEFAULT 1,
                season_id INTEGER NOT NULL DEFAULT 1,
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
                group_id INTEGER NOT NULL DEFAULT 1,
                season_id INTEGER NOT NULL DEFAULT 1,
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

        group_count = conn.execute("SELECT COUNT(*) AS total FROM groups").fetchone()["total"]
        if group_count == 0:
            group_cursor = conn.execute("INSERT INTO groups (name) VALUES (?) RETURNING id", ("Mi grupo",))
            default_group_id = last_insert_id(group_cursor)
            conn.execute(
                "INSERT INTO seasons (group_id, name) VALUES (?, ?)",
                (default_group_id, "Primer Temporada"),
            )

        if group_count == 0 or conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0] == 0:
            existing_group = conn.execute("SELECT id FROM groups ORDER BY id ASC LIMIT 1").fetchone()
            if existing_group:
                conn.execute(
                    "INSERT INTO seasons (group_id, name) VALUES (?, ?)",
                    (existing_group["id"], "Primer Temporada"),
                )

        ensure_column("groups", "password", "TEXT DEFAULT ''")
        ensure_column("players", "group_id", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("teams", "group_id", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("teams", "season_id", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("matches", "group_id", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("matches", "season_id", "INTEGER NOT NULL DEFAULT 1")

        conn.execute(
            "UPDATE players SET group_id = COALESCE(group_id, 1) WHERE group_id IS NULL"
        )
        conn.execute(
            "UPDATE teams SET group_id = COALESCE(group_id, 1), season_id = COALESCE(season_id, 1) WHERE group_id IS NULL OR season_id IS NULL"
        )
        conn.execute(
            "UPDATE matches SET group_id = COALESCE(group_id, 1), season_id = COALESCE(season_id, 1) WHERE group_id IS NULL OR season_id IS NULL"
        )

        conn.commit()


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_current_group_id() -> int:
    with get_conn() as conn:
        value = conn.execute(
            "SELECT value FROM settings WHERE key = 'current_group_id'"
        ).fetchone()
    if value is None or (value["value"] is None):
        return 0
    try:
        parsed = int(str(value["value"]).strip())
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def get_group_name(group_id: int | None = None) -> str:
    current_group_id = group_id if group_id is not None else get_current_group_id()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM groups WHERE id = ?",
            (current_group_id,),
        ).fetchone()
    return row["name"] if row else "Mi grupo"


def get_current_season_id() -> int:
    current_group_id = get_current_group_id()
    with get_conn() as conn:
        value = conn.execute(
            "SELECT value FROM settings WHERE key = 'current_season_id'"
        ).fetchone()
        if value is None or (value["value"] is None):
            return 0
        try:
            season_id = int(str(value["value"]).strip())
        except (TypeError, ValueError):
            return 0
        season = conn.execute(
            "SELECT id FROM seasons WHERE id = ? AND group_id = ?",
            (season_id, current_group_id),
        ).fetchone()
        if season is not None:
            return int(season["id"])
        if current_group_id <= 0:
            return 0
        fallback = conn.execute(
            "SELECT id FROM seasons WHERE group_id = ? ORDER BY id ASC LIMIT 1",
            (current_group_id,),
        ).fetchone()
        if fallback is None:
            return 0
        return int(fallback["id"])


def get_season_name(season_id: int | None = None) -> str:
    current_group_id = get_current_group_id()
    season_value = season_id if season_id is not None else get_current_season_id()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM seasons WHERE id = ? AND group_id = ?",
            (season_value, current_group_id),
        ).fetchone()
    return row["name"] if row else "Primer Temporada"


@app.get("/config")
def get_config() -> dict[str, str | int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
    return {
        "brand": data.get("brand", "SuperBalon"),
        "season_name": get_season_name(current_season_id),
        "tagline": data.get("tagline", "Liga casual de amigos"),
        "group_name": get_group_name(current_group_id),
        "current_group_id": current_group_id,
        "current_season_id": current_season_id,
    }


@app.post("/config")
def update_config(payload: dict[str, Any]) -> dict[str, str | int]:
    season_name = (payload.get("season_name") or "").strip()
    tagline = (payload.get("tagline") or "").strip()
    brand = (payload.get("brand") or "").strip()
    current_group_id = payload.get("current_group_id")
    current_season_id = payload.get("current_season_id")

    def parse_non_negative_int(value: Any, field_name: str) -> int:
        if value is None or value == "":
            raise HTTPException(status_code=400, detail=f"{field_name} requerido")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{field_name} inválido") from exc
        if parsed < 0:
            raise HTTPException(status_code=400, detail=f"{field_name} inválido")
        return parsed

    with get_conn() as conn:
        if season_name:
            selected_season_id = parse_non_negative_int(current_season_id, "current_season_id") if current_season_id else get_current_season_id()
            exists = conn.execute(
                "SELECT 1 FROM seasons WHERE id = ? AND group_id = ?",
                (selected_season_id, get_current_group_id()),
            ).fetchone()
            if exists:
                conn.execute(
                    "UPDATE seasons SET name = ? WHERE id = ?",
                    (season_name, selected_season_id),
                )
            else:
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
        if current_group_id is not None and current_group_id != "":
            group_id = parse_non_negative_int(current_group_id, "current_group_id")
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('current_group_id', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(group_id),),
            )
        if current_season_id is not None and current_season_id != "":
            season_id = parse_non_negative_int(current_season_id, "current_season_id")
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('current_season_id', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(season_id),),
            )
            season_row = conn.execute(
                "SELECT group_id FROM seasons WHERE id = ?",
                (season_id,),
            ).fetchone()
            if season_row:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES ('current_group_id', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(season_row["group_id"]),),
                )
        conn.commit()

    return get_config()


@app.get("/players")
def get_players() -> list[dict[str, Any]]:
    current_group_id = get_current_group_id()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name FROM players WHERE group_id = ? ORDER BY name ASC",
            (current_group_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/players")
def create_player(payload: dict[str, str]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")

    current_group_id = get_current_group_id()
    with get_conn() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO players (name, group_id) VALUES (?, ?)",
                (name, current_group_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Ese jugador ya existe en este grupo") from None
        except Exception as exc:  # pragma: no cover - PostgreSQL path
            if psycopg is not None and isinstance(exc, psycopg.IntegrityError):
                raise HTTPException(status_code=400, detail="Ese jugador ya existe en este grupo") from None
            raise

    return {"id": last_insert_id(cursor), "name": name, "group_id": current_group_id}


@app.delete("/players/{player_id}")
def delete_player(player_id: int) -> dict[str, str | int]:
    current_group_id = get_current_group_id()
    with get_conn() as conn:
        player = conn.execute(
            "SELECT id FROM players WHERE id = ? AND group_id = ?",
            (player_id, current_group_id),
        ).fetchone()
        if player is None:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")

        conn.execute("DELETE FROM team_players WHERE player_id = ?", (player_id,))
        conn.execute("DELETE FROM players WHERE id = ? AND group_id = ?", (player_id, current_group_id))
        conn.commit()
    return {"status": "player_removed", "player_id": player_id}


@app.delete("/players")
def delete_players() -> dict[str, str]:
    current_group_id = get_current_group_id()
    with get_conn() as conn:
        team_ids = conn.execute(
            "SELECT id FROM teams WHERE group_id = ?",
            (current_group_id,),
        ).fetchall()
        if team_ids:
            team_ids_list = [row["id"] for row in team_ids]
            placeholders = ", ".join("?" for _ in team_ids_list)
            conn.execute(f"DELETE FROM team_players WHERE team_id IN ({placeholders})", team_ids_list)
            conn.execute(f"DELETE FROM matches WHERE group_id = ?", (current_group_id,))
            conn.execute(f"DELETE FROM teams WHERE group_id = ?", (current_group_id,))
        conn.execute("DELETE FROM players WHERE group_id = ?", (current_group_id,))
        conn.commit()
    return {"status": "all_players_removed"}


@app.get("/teams")
def get_teams() -> list[dict[str, Any]]:
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
    with get_conn() as conn:
        team_rows = conn.execute(
            "SELECT id, name FROM teams WHERE group_id = ? AND season_id = ? ORDER BY id",
            (current_group_id, current_season_id),
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
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
    if team_size < 1:
        raise HTTPException(status_code=400, detail="El tamaño del equipo debe ser mayor a 0")

    with get_conn() as conn:
        players = conn.execute(
            "SELECT id, name FROM players WHERE group_id = ? ORDER BY name ASC",
            (current_group_id,),
        ).fetchall()
        if len(players) < 2:
            raise HTTPException(status_code=400, detail="Necesitás al menos 2 jugadores para armar equipos")

        conn.execute("DELETE FROM team_players WHERE team_id IN (SELECT id FROM teams WHERE group_id = ? AND season_id = ?)", (current_group_id, current_season_id))
        conn.execute("DELETE FROM teams WHERE group_id = ? AND season_id = ?", (current_group_id, current_season_id))

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
            teams.append(current_team)

        if not teams:
            raise HTTPException(status_code=400, detail="No se pudieron generar equipos")

        for index, squad in enumerate(teams, start=1):
            team_name = f"Equipo {index}"
            cursor = conn.execute(
                "INSERT INTO teams (name, group_id, season_id) VALUES (?, ?, ?)",
                (team_name, current_group_id, current_season_id),
            )
            team_id = last_insert_id(cursor)
            for player in squad:
                conn.execute(
                    "INSERT INTO team_players (team_id, player_id) VALUES (?, ?)",
                    (team_id, player["id"]),
                )

        conn.commit()

    return {"status": "teams_generated", "count": len(teams)}


@app.get("/matches")
def get_matches() -> list[dict[str, Any]]:
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
                   ht.name AS home_name, at.name AS away_name, m.played_at
            FROM matches m
            INNER JOIN teams ht ON ht.id = m.home_team_id
            INNER JOIN teams at ON at.id = m.away_team_id
            WHERE m.group_id = ? AND m.season_id = ?
            ORDER BY m.played_at DESC, m.id DESC
            """,
            (current_group_id, current_season_id),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/matches")
def add_match(payload: dict[str, Any]) -> dict[str, Any]:
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
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
            "SELECT 1 FROM teams WHERE id IN (?, ?) AND group_id = ? AND season_id = ?",
            (home_team_id, away_team_id, current_group_id, current_season_id),
        ).fetchall()
        if len(exists) != 2:
            raise HTTPException(status_code=400, detail="Uno o ambos equipos no existen en la temporada actual")

        cursor = conn.execute(
            """
            INSERT INTO matches (group_id, season_id, home_team_id, away_team_id, home_goals, away_goals)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (current_group_id, current_season_id, home_team_id, away_team_id, home_goals, away_goals),
        )
        conn.commit()

    return {"id": last_insert_id(cursor), "status": "match_saved"}


@app.get("/standings")
def get_standings() -> list[dict[str, Any]]:
    current_group_id = get_current_group_id()
    current_season_id = get_current_season_id()
    with get_conn() as conn:
        player_rows = conn.execute(
            "SELECT id, name FROM players WHERE group_id = ? ORDER BY name ASC",
            (current_group_id,),
        ).fetchall()
        match_rows = conn.execute(
            """
            SELECT home_team_id, away_team_id, home_goals, away_goals
            FROM matches
            WHERE group_id = ? AND season_id = ?
            ORDER BY id ASC
            """,
            (current_group_id, current_season_id),
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


@app.get("/groups")
def get_groups() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, password FROM groups ORDER BY id ASC").fetchall()
    result = []
    for row in rows:
        password_value = (row["password"] or "").strip()
        result.append({
            "id": row["id"],
            "name": row["name"],
            "password": password_value,
            "has_password": bool(password_value),
        })
    return result


@app.post("/groups/login")
def login_group(payload: dict[str, Any]) -> dict[str, Any]:
    group_id_raw = payload.get("group_id")
    try:
        group_id = int(group_id_raw) if group_id_raw is not None else 0
    except (TypeError, ValueError):
        group_id = 0
    password = (payload.get("password") or "").strip()
    if group_id <= 0:
        raise HTTPException(status_code=400, detail="Grupo inválido")

    with get_conn() as conn:
        group = conn.execute(
            "SELECT id, password FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if group is None:
            raise HTTPException(status_code=404, detail="Grupo no encontrado")

        stored_password = (group["password"] or "").strip()
        if stored_password and stored_password != password:
            raise HTTPException(status_code=403, detail="Contraseña incorrecta")

        season = conn.execute(
            "SELECT id FROM seasons WHERE group_id = ? ORDER BY id ASC LIMIT 1",
            (group_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('current_group_id', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(group_id),),
        )
        conn.commit()

    return {"ok": True, "group_id": group_id}


@app.post("/groups")
def create_group(payload: dict[str, str]) -> dict[str, Any]:
    name = (payload.get("name") or "").strip() or "Mi grupo"
    password = (payload.get("password") or "").strip()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO groups (name, password) VALUES (?, ?)",
            (name, password),
        )
        group_id = last_insert_id(cursor)
        season_name = "Primer Temporada"
        season_cursor = conn.execute(
            "INSERT INTO seasons (group_id, name) VALUES (?, ?)",
            (group_id, season_name),
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("current_group_id", str(group_id)),
        )
        conn.commit()
    return {"id": group_id, "name": name, "password": password, "has_password": bool(password), "season_id": last_insert_id(season_cursor)}


@app.get("/seasons")
def get_seasons() -> list[dict[str, Any]]:
    current_group_id = get_current_group_id()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, group_id, name FROM seasons WHERE group_id = ? ORDER BY id ASC",
            (current_group_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/seasons")
def create_season(payload: dict[str, str]) -> dict[str, Any]:
    group_id = int(payload.get("group_id") or get_current_group_id())
    name = (payload.get("name") or "").strip() or "Primer Temporada"
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO seasons (group_id, name) VALUES (?, ?)",
            (group_id, name),
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("current_group_id", str(group_id)),
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("current_season_id", str(last_insert_id(cursor))),
        )
        conn.commit()
    return {"id": last_insert_id(cursor), "group_id": group_id, "name": name}


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
