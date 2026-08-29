import importlib
import os
import sys
import unittest
from queue import Full
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class ServerLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.backend = Mock()
        cls.backend.create_tts_task.return_value = "task"
        sys.modules.pop("server", None)
        with (
            patch.dict(os.environ, {"BASE_STATIC_URL": "https://example.test/audio"}),
            patch("wrapper.GenieWrapper", return_value=cls.backend),
        ):
            cls.server = importlib.import_module("server")
        cls.client = TestClient(cls.server.app)

    def setUp(self) -> None:
        self.backend.create_tts_task.reset_mock(return_value=True, side_effect=True)
        self.backend.create_tts_task.return_value = "task"

    @staticmethod
    def _payload() -> dict[str, str]:
        return {
            "character_name": "character",
            "reference_audio_id": "reference",
            "reference_audio_text": "reference text",
            "text": "text",
        }

    def test_limits_task_creation_to_100_per_ip_per_day(self) -> None:
        headers = {"x-client-ip": "203.0.113.10"}
        for _ in range(100):
            response = self.client.post("/tasks", json=self._payload(), headers=headers)
            self.assertEqual(response.status_code, 200)

        response = self.client.post("/tasks", json=self._payload(), headers=headers)

        self.assertEqual(response.status_code, 429)
        self.assertIn("retry-after", response.headers)

    def test_returns_503_when_task_queue_is_full(self) -> None:
        self.backend.create_tts_task.side_effect = Full

        response = self.client.post(
            "/tasks",
            json=self._payload(),
            headers={"x-client-ip": "203.0.113.11"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "60")


if __name__ == "__main__":
    unittest.main()
