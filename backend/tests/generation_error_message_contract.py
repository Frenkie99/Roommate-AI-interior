import unittest
from pathlib import Path


class GenerationErrorMessageContractTests(unittest.TestCase):
    def test_provider_errors_are_not_exposed_to_users(self):
        route_source = (
            Path(__file__).resolve().parents[1] / "app" / "routes" / "image.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '"图片生成服务暂时繁忙，本次未扣除体验次数，请稍后重试"',
            route_source,
        )
        self.assertNotIn(
            '"message": result.get("msg", "生成失败")',
            route_source,
        )
        self.assertIn("IMAGE_GENERATION_TIMEOUT_SECONDS", route_source)
        self.assertIn("await asyncio.wait_for(", route_source)
        self.assertIn("status_code=504", route_source)


if __name__ == "__main__":
    unittest.main()
