import asyncio
import importlib.util
import io
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image

from app.services.llm_client import LLMClient
from app.utils.prompt_builder import (
    build_prompt_v2,
    llm_analysis_has_prompt_context,
    normalize_llm_analysis,
)


ANALYSIS_FIXTURE = {
    "room_analysis": {
        "room_type": "living_room",
        "space_description": (
            "rectangular room with an east-facing floor-to-ceiling window"
        ),
        "physical_features": "2.6m ceiling and concrete floor",
        "lighting_analysis": "soft morning light from the east",
    },
    "design_recommendations": {
        "layout_suggestion": "keep the window axis open",
        "furniture_placement": "place a low sofa against the west wall",
        "color_scheme": "warm beige and walnut",
        "lighting_design": "indirect cove lighting",
    },
}


class PromptAnalysisContractTests(unittest.TestCase):
    def test_nested_analysis_builds_the_same_prompt_as_service_result(self):
        client = LLMClient()
        parsed = client._parse_llm_response(
            json.dumps(ANALYSIS_FIXTURE),
            "modern_luxury",
            "living_room",
            "keep it airy",
        )

        data = parsed["data"]
        rebuilt = build_prompt_v2(
            "modern_luxury",
            "living_room",
            data["analysis"],
            "keep it airy",
        )

        self.assertTrue(data["analysis_valid"])
        self.assertEqual(rebuilt, data["enhanced_prompt"])
        self.assertIn("## SPACE CONTEXT:", rebuilt)
        self.assertIn("## DESIGN LOGIC (AI Analysis):", rebuilt)
        self.assertNotIn("## ROOM LAYOUT (Standard):", rebuilt)
        self.assertNotIn("## COLOR PALETTE:", rebuilt)

    def test_prompt_section_snapshot_keeps_v2_structure_and_dynamic_order(self):
        prompt = build_prompt_v2(
            "modern_luxury",
            "living_room",
            ANALYSIS_FIXTURE,
            "keep it airy",
        )
        sections = [
            line.split(":", 1)[0]
            for line in prompt.splitlines()
            if line.startswith("## ")
        ]

        self.assertEqual(
            sections,
            [
                "## ROLE",
                "## ATMOSPHERE & VIBE",
                "## SPACE CONTEXT",
                "## DESIGN LOGIC (AI Analysis)",
                "## MATERIAL & FINISHES",
                "## LIGHTING SCHEME",
                "## FURNITURE STYLE",
                "## SOFT FURNISHINGS",
                "## USER REQUIREMENTS",
                "## QUALITY",
            ],
        )
        self.assertIn("CRITICAL STRUCTURAL CONSTRAINTS", prompt)
        self.assertNotIn("Transform this living room into", prompt.splitlines()[0])

    def test_normalization_accepts_partial_dict_and_rejects_wrong_types(self):
        partial, is_valid = normalize_llm_analysis({
            "room_analysis": "not-a-dict",
            "design_recommendations": {
                "layout_suggestion": "keep the center open",
            },
        })

        self.assertTrue(is_valid)
        self.assertEqual(partial["room_analysis"], {})
        self.assertTrue(llm_analysis_has_prompt_context(partial))
        self.assertEqual(normalize_llm_analysis([]), ({}, False))
        self.assertEqual(normalize_llm_analysis({}), ({
            "room_analysis": {},
            "design_recommendations": {},
        }, False))

    def test_malformed_or_empty_response_is_explicit_static_fallback(self):
        client = LLMClient()

        for content, expected_reason in (
            ('{"room_analysis":', "json_parse_error"),
            ("{}", "invalid_analysis_structure"),
        ):
            with self.subTest(content=content):
                parsed = client._parse_llm_response(
                    content,
                    "modern_luxury",
                    "living_room",
                    None,
                )
                data = parsed["data"]

                self.assertEqual(parsed["code"], 0)
                self.assertFalse(data["analysis_valid"])
                self.assertEqual(data["fallback_reason"], expected_reason)
                self.assertNotIn("## SPACE CONTEXT:", data["enhanced_prompt"])


@unittest.skipUnless(
    importlib.util.find_spec("fastapi") and importlib.util.find_spec("aiofiles"),
    "route contract test requires backend runtime dependencies",
)
class GenerateRouteContractTests(unittest.TestCase):
    @staticmethod
    def _jpeg_bytes():
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), "white").save(buffer, format="JPEG")
        return buffer.getvalue()

    def _run_route(self, llm_result):
        from app.routes import image as image_route
        from app.services.auth_service import AuthUser, GenerationReservation

        class Upload:
            async def read(self):
                return GenerateRouteContractTests._jpeg_bytes()

        generated = {
            "code": 0,
            "data": {
                "images": [{"mime_type": "image/jpeg", "data": b"fake"}],
                "used_model": "mock-model",
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_dir = os.path.join(tmp_dir, "input")
            output_dir = os.path.join(tmp_dir, "output")
            os.makedirs(input_dir)
            os.makedirs(output_dir)
            trace_writer = Mock()

            with (
                patch.dict(os.environ, {"USE_LLM_PROMPT": "true"}),
                patch.object(image_route, "INPUT_DIR", input_dir),
                patch.object(image_route, "OUTPUT_DIR", output_dir),
                patch.object(
                    image_route.image_processor,
                    "validate_image",
                    return_value=(True, ""),
                ),
                patch.object(
                    image_route.image_processor,
                    "preprocess",
                    side_effect=lambda value: value,
                ),
                patch.object(
                    image_route.llm_client,
                    "analyze_room_and_generate_prompt",
                    AsyncMock(return_value=llm_result),
                ),
                patch.object(
                    image_route,
                    "generate_design_image",
                    AsyncMock(return_value=generated),
                ) as generate_mock,
                patch.object(
                    image_route,
                    "reserve_generation_or_raise",
                    return_value=GenerationReservation(
                        id=1,
                        user_id=1,
                        endpoint="/api/v1/generate",
                        quota={"remaining": 2},
                    ),
                ),
                patch.object(image_route, "write_trace", trace_writer),
            ):
                response = asyncio.run(image_route.generate_renovation_image(
                    image=Upload(),
                    style="modern_luxury",
                    room_type="living_room",
                    custom_prompt="keep it airy",
                    aspect_ratio="4:3",
                    image_size="1K",
                    session_id="test-session",
                    current_user=AuthUser(
                        id=1,
                        username="test-user",
                        generation_used=0,
                        generation_limit=3,
                    ),
                ))

        prompt = generate_mock.await_args.kwargs["prompt"]
        trace = trace_writer.call_args.args[0]
        return prompt, json.loads(response.body), trace, response.status_code

    def test_generate_route_injects_nested_analysis_into_generation_prompt(self):
        llm_result = {
            "code": 0,
            "message": "success",
            "data": {
                "analysis": ANALYSIS_FIXTURE,
                "analysis_valid": True,
                "fallback_reason": "",
                "enhanced_prompt": build_prompt_v2(
                    "modern_luxury",
                    "living_room",
                    ANALYSIS_FIXTURE,
                    "keep it airy",
                ),
                "vision_used": True,
            },
        }

        prompt, body, trace, status_code = self._run_route(llm_result)

        self.assertEqual(status_code, 200)
        self.assertEqual(body["data"]["prompt"], prompt)
        self.assertIn("## SPACE CONTEXT:", prompt)
        self.assertIn("## DESIGN LOGIC (AI Analysis):", prompt)
        self.assertEqual(trace["enhanced_prompt"], prompt)
        self.assertEqual(trace["prompt_source"], "llm_vision")
        self.assertTrue(trace["metadata"]["analysis_valid"])
        self.assertTrue(trace["metadata"]["prompt_context_applied"])

    def test_generate_route_uses_static_prompt_for_invalid_analysis(self):
        llm_result = {
            "code": 0,
            "message": "LLM 响应不可用，已使用静态提示词",
            "data": {
                "analysis": {"raw_response": "truncated"},
                "analysis_valid": False,
                "fallback_reason": "json_parse_error",
                "enhanced_prompt": "ignored service fallback",
                "vision_used": True,
            },
        }

        prompt, _, trace, _ = self._run_route(llm_result)

        self.assertNotIn("## SPACE CONTEXT:", prompt)
        self.assertNotIn("## DESIGN LOGIC (AI Analysis):", prompt)
        self.assertEqual(trace["prompt_source"], "static_on_error")
        self.assertFalse(trace["vision_analysis_ok"])
        self.assertFalse(trace["metadata"]["analysis_valid"])
        self.assertFalse(trace["metadata"]["prompt_context_applied"])
        self.assertEqual(
            trace["metadata"]["llm_fallback_reason"],
            "json_parse_error",
        )


if __name__ == "__main__":
    unittest.main()
