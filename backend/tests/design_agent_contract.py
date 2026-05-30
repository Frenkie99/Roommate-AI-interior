import asyncio
import unittest
from unittest.mock import AsyncMock

from app.services.inpaint_service import inpaint_service


class InpaintServiceContractTests(unittest.TestCase):
    def test_inpaint_service_exposes_refine_methods(self):
        self.assertTrue(callable(getattr(inpaint_service, "inpaint", None)))
        self.assertTrue(callable(getattr(inpaint_service, "replace_furniture", None)))
        self.assertTrue(callable(getattr(inpaint_service, "replace_decoration", None)))
        self.assertTrue(getattr(inpaint_service, "model", None))


class DesignAgentRoutingTests(unittest.TestCase):
    def test_local_edit_without_mask_requests_box_selection(self):
        from app.services.design_agent import DesignAgent

        refine_tool = AsyncMock()
        agent = DesignAgent(
            knowledge_tool=AsyncMock(),
            generate_tool=AsyncMock(),
            refine_tool=refine_tool,
        )

        result = asyncio.run(agent.handle_chat(
            message="把沙发换成深色布艺沙发",
            context={
                "has_uploaded_image": True,
                "generated_image": "/output/demo.png",
                "view_mode": "preview",
                "has_selected_mask": False,
                "style": "modern_minimalist",
                "room_type": "living_room",
            },
            history=[],
        ))

        self.assertEqual(result["action"], "request_box_selection")
        self.assertEqual(result["ui_hint"], "refine")
        refine_tool.assert_not_awaited()

    def test_selected_mask_routes_to_refine_region(self):
        from app.services.design_agent import DesignAgent

        refine_tool = AsyncMock(return_value={"result_image": "data:image/png;base64,abc"})
        agent = DesignAgent(
            knowledge_tool=AsyncMock(),
            generate_tool=AsyncMock(),
            refine_tool=refine_tool,
        )

        result = asyncio.run(agent.handle_chat(
            message="换成深色布艺沙发",
            context={
                "has_uploaded_image": True,
                "generated_image": "/output/demo.png",
                "view_mode": "refine",
                "has_selected_mask": True,
                "style": "modern_minimalist",
                "room_type": "living_room",
            },
            history=[],
        ))

        self.assertEqual(result["action"], "refine_region")
        self.assertEqual(result["state_patch"]["generated_image"], "data:image/png;base64,abc")
        self.assertIsNone(result["state_patch"]["selected_mask"])
        refine_tool.assert_awaited_once()
