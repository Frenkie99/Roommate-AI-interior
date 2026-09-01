import asyncio
import base64
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services import getgoapi_client as image_client


def _response(status_code, payload, headers=None):
    request = httpx.Request("POST", "https://api.example.test/generate")
    return httpx.Response(
        status_code,
        json=payload,
        headers=headers,
        request=request,
    )


class ImageProviderRetryContractTests(unittest.TestCase):
    def test_429_is_retried_with_backoff(self):
        client = image_client.GetGoAPIClient()
        client.client.post = AsyncMock(side_effect=[
            _response(429, {"error": {"message": "high demand"}}),
            _response(200, {
                "candidates": [{
                    "content": {"parts": [{
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(b"image").decode(),
                        }
                    }]}
                }]
            }),
        ])

        with (
            patch.dict(os.environ, {"APIYI_KEY": "test-key"}),
            patch.object(
                image_client,
                "_wait_before_retry",
                AsyncMock(),
            ) as wait_mock,
        ):
            result = asyncio.run(client.generate_image("draw a room"))

        self.assertEqual(result["code"], 0)
        self.assertEqual(client.client.post.await_count, 2)
        wait_mock.assert_awaited_once()
        asyncio.run(client.close())

    def test_non_transient_model_error_still_tries_next_model(self):
        provider = AsyncMock()
        provider.name = "custom-test"
        provider.models = ["bad-model", "working-model"]
        provider.is_configured = True
        provider.generate_image.side_effect = [
            {"code": -1, "msg": "model unavailable", "status_code": 400},
            {
                "code": 0,
                "msg": "success",
                "data": {"images": [{"data": b"image"}]},
            },
        ]

        with patch.object(
            image_client, "_load_custom_providers", return_value=[provider]
        ):
            result = asyncio.run(image_client.generate_design_image("draw a room"))

        self.assertEqual(result["code"], 0)
        self.assertEqual(provider.generate_image.await_count, 2)
        provider.close.assert_awaited_once()

    def test_apiyi_flash_model_is_the_primary_route(self):
        apiyi = AsyncMock()
        apiyi.is_configured = True
        apiyi.generate_image.return_value = {
            "code": 0,
            "msg": "success",
            "data": {"images": [{"data": b"image"}]},
        }

        with (
            patch.object(image_client, "_get_apiyi_client", return_value=apiyi),
            patch.object(image_client, "_load_custom_providers") as custom_loader,
        ):
            result = asyncio.run(image_client.generate_design_image("draw a room"))

        self.assertEqual(result["code"], 0)
        self.assertEqual(
            apiyi.generate_image.await_args.kwargs["model"],
            image_client.GetGoModel.GEMINI_25_FLASH_IMAGE,
        )
        custom_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
