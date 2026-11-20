import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class DeletePlayerEndpointTest(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        os.environ["SUPERBALON_DB_PATH"] = self.temp_db.name

        module_path = Path(__file__).resolve().parents[1] / "backend" / "app.py"
        spec = importlib.util.spec_from_file_location("superbalon_backend", module_path)
        self.backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.backend)
        self.backend.init_db()
        self.client = TestClient(self.backend.app)

    def tearDown(self):
        if hasattr(self, "client"):
            self.client.close()
        if "SUPERBALON_DB_PATH" in os.environ:
            del os.environ["SUPERBALON_DB_PATH"]

    @staticmethod
    def _ctx(group_id, season_id=None):
        headers = {"X-Group-Id": str(group_id)}
        if season_id is not None:
            headers["X-Season-Id"] = str(season_id)
        return headers

    def test_two_devices_in_different_groups_do_not_collide(self):
        group_a = self.client.post("/groups", json={"name": "Grupo A", "password": ""}).json()
        group_b = self.client.post("/groups", json={"name": "Grupo B", "password": ""}).json()
        device_a = self._ctx(group_a["id"], group_a["season_id"])
        device_b = self._ctx(group_b["id"], group_b["season_id"])

        # Intercalado: antes, el último en entrar a un grupo cambiaba el contexto de todos.
        self.assertEqual(self.client.post("/players", json={"name": "Ana"}, headers=device_a).status_code, 200)
        self.client.post("/groups/login", json={"group_id": group_b["id"], "password": ""})
        self.assertEqual(self.client.post("/players", json={"name": "Beto"}, headers=device_b).status_code, 200)
        self.assertEqual(self.client.post("/players", json={"name": "Carla"}, headers=device_a).status_code, 200)

        names_a = [p["name"] for p in self.client.get("/players", headers=device_a).json()]
        names_b = [p["name"] for p in self.client.get("/players", headers=device_b).json()]
        self.assertEqual(names_a, ["Ana", "Carla"])
        self.assertEqual(names_b, ["Beto"])

        self.assertEqual(self.client.get("/config", headers=device_a).json()["group_name"], "Grupo A")
        self.assertEqual(self.client.get("/config", headers=device_b).json()["group_name"], "Grupo B")

    def test_season_from_another_group_is_not_used(self):
        group_a = self.client.post("/groups", json={"name": "Grupo A", "password": ""}).json()
        group_b = self.client.post("/groups", json={"name": "Grupo B", "password": ""}).json()
        config = self.client.get("/config", headers=self._ctx(group_a["id"], group_b["season_id"])).json()
        self.assertEqual(config["current_group_id"], group_a["id"])
        self.assertEqual(config["current_season_id"], group_a["season_id"])

    def test_writes_without_group_are_rejected(self):
        response = self.client.post("/players", json={"name": "Ana"})
        self.assertEqual(response.status_code, 400)

    def test_login_with_wrong_password_is_rejected_and_returns_season(self):
        group = self.client.post("/groups", json={"name": "Privado", "password": "1234"}).json()
        bad = self.client.post("/groups/login", json={"group_id": group["id"], "password": "nope"})
        self.assertEqual(bad.status_code, 403)
        ok = self.client.post("/groups/login", json={"group_id": group["id"], "password": "1234"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["season_id"], group["season_id"])

    def test_default_config_requires_explicit_group_and_season_selection(self):
        config_response = self.client.get("/config")
        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(config_response.json()["current_group_id"], 0)
        self.assertEqual(config_response.json()["current_season_id"], 0)

    def test_config_accepts_numeric_group_and_season_selection(self):
        group_response = self.client.post("/groups", json={"name": "Grupo test", "password": ""})
        self.assertEqual(group_response.status_code, 200)
        group_id = group_response.json()["id"]

        season_response = self.client.post("/seasons", json={"group_id": group_id, "name": "Temporada 2026"})
        self.assertEqual(season_response.status_code, 200)
        season_id = season_response.json()["id"]

        config_response = self.client.post(
            "/config",
            json={"current_group_id": group_id, "current_season_id": season_id},
        )
        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(config_response.json()["current_group_id"], group_id)
        self.assertEqual(config_response.json()["current_season_id"], season_id)

    def test_delete_single_player_removes_player_from_group(self):
        group_response = self.client.post("/groups", json={"name": "Grupo test", "password": ""})
        self.assertEqual(group_response.status_code, 200)
        headers = self._ctx(group_response.json()["id"])

        player_response = self.client.post("/players", json={"name": "Ana"}, headers=headers)
        self.assertEqual(player_response.status_code, 200)
        player_id = player_response.json()["id"]

        delete_response = self.client.delete(f"/players/{player_id}", headers=headers)
        self.assertEqual(delete_response.status_code, 200)

        list_response = self.client.get("/players", headers=headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

    def test_production_without_database_url_uses_local_fallback(self):
        os.environ["RAILWAY_ENVIRONMENT"] = "production"
        os.environ.pop("DATABASE_URL", None)

        try:
            module_path = Path(__file__).resolve().parents[1] / "backend" / "app.py"
            spec = importlib.util.spec_from_file_location("superbalon_backend_prod", module_path)
            backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(backend)
            self.assertFalse(backend.USE_POSTGRES)
        finally:
            os.environ.pop("RAILWAY_ENVIRONMENT", None)

    def test_match_payload_accepts_schedule_location_and_notes(self):
        group_response = self.client.post("/groups", json={"name": "Grupo fixture", "password": ""})
        self.assertEqual(group_response.status_code, 200)
        group_id = group_response.json()["id"]

        season_response = self.client.post("/seasons", json={"group_id": group_id, "name": "Temporada prueba"})
        self.assertEqual(season_response.status_code, 200)
        season_id = season_response.json()["id"]
        headers = self._ctx(group_id, season_id)

        player_a = self.client.post("/players", json={"name": "Ana"}, headers=headers)
        player_b = self.client.post("/players", json={"name": "Beto"}, headers=headers)
        self.assertEqual(player_a.status_code, 200)
        self.assertEqual(player_b.status_code, 200)

        team_response = self.client.post("/teams/generate", json={"team_size": 1}, headers=headers)
        self.assertEqual(team_response.status_code, 200)
        teams = self.client.get("/teams", headers=headers).json()
        self.assertGreaterEqual(len(teams), 2)

        response = self.client.post(
            "/matches",
            json={
                "home_team_id": teams[0]["id"],
                "away_team_id": teams[1]["id"],
                "home_goals": 2,
                "away_goals": 1,
                "match_date": "2026-11-11T20:00",
                "location": "Parque Rivadavia",
                "notes": "Equipo 1 con remera roja",
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)

        matches = self.client.get("/matches", headers=headers).json()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["location"], "Parque Rivadavia")
        self.assertEqual(matches[0]["notes"], "Equipo 1 con remera roja")

        all_players = matches[0]["home_players"] + matches[0]["away_players"]
        self.assertIn("Ana", all_players)
        self.assertIn("Beto", all_players)


if __name__ == "__main__":
    unittest.main()
