import json
import unittest

from fastapi.testclient import TestClient

from app.main import app


class AgentRouteTests(unittest.TestCase):
    def test_agent_chat_exposes_box_selection_boundary(self):
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/chat",
            data={
                "message": "把沙发换成深色布艺沙发",
                "context": json.dumps({
                    "has_uploaded_image": True,
                    "generated_image": "/output/demo.png",
                    "view_mode": "preview",
                    "has_selected_mask": False,
                    "style": "modern_minimalist",
                    "room_type": "living_room",
                }, ensure_ascii=False),
                "history": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["action"], "request_box_selection")
        self.assertEqual(body["data"]["ui_hint"], "refine")
