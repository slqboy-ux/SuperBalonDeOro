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

    def test_delete_single_player_removes_player_from_group(self):
        group_response = self.client.post("/groups", json={"name": "Grupo test", "password": ""})
        self.assertEqual(group_response.status_code, 200)

        player_response = self.client.post("/players", json={"name": "Ana"})
        self.assertEqual(player_response.status_code, 200)
        player_id = player_response.json()["id"]

        delete_response = self.client.delete(f"/players/{player_id}")
        self.assertEqual(delete_response.status_code, 200)

        list_response = self.client.get("/players")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])


if __name__ == "__main__":
    unittest.main()
