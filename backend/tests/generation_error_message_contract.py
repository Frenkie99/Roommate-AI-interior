import unittest
from pathlib import Path


class GenerationErrorMessageContractTests(unittest.TestCase):
    def test_provider_errors_are_not_exposed_to_users(self):
        route_source = (
            Path(__file__).resolve().parents[1] / "app" / "routes" / "image.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'GENERATION_UNAVAILABLE_MESSAGE = "当前时段的体验额度暂时已用完，请稍后再试"',
            route_source,
        )
        self.assertNotIn(
            '"message": result.get("msg", "生成失败")',
            route_source,
        )


if __name__ == "__main__":
    unittest.main()
