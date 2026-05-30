import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _install_streamlit_stub():
    if "streamlit" not in sys.modules:
        sys.modules["streamlit"] = types.SimpleNamespace()


def _install_chromadb_stub():
    if "chromadb" not in sys.modules:
        chromadb = types.ModuleType("chromadb")

        class PersistentClient:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("stubbed chromadb")

        chromadb.PersistentClient = PersistentClient
        sys.modules["chromadb"] = chromadb

    if "chromadb.config" not in sys.modules:
        config = types.ModuleType("chromadb.config")

        class Settings:
            def __init__(self, *args, **kwargs):
                pass

        config.Settings = Settings
        sys.modules["chromadb.config"] = config


def _install_cv2_stub():
    if "cv2" not in sys.modules:
        cv2 = types.ModuleType("cv2")
        cv2.COLOR_RGB2GRAY = 0
        cv2.Canny = lambda arr, threshold1, threshold2: arr
        cv2.cvtColor = lambda arr, code: arr
        sys.modules["cv2"] = cv2
    if "skimage" not in sys.modules:
        skimage = types.ModuleType("skimage")
        metrics = types.ModuleType("skimage.metrics")
        metrics.structural_similarity = lambda *args, **kwargs: 1.0
        sys.modules["skimage"] = skimage
        sys.modules["skimage.metrics"] = metrics


class EvalPathSandboxTests(unittest.TestCase):
    def setUp(self):
        _install_streamlit_stub()

    def test_image_comparison_resolves_only_eval_data_and_output_paths(self):
        component = importlib.import_module("evals.ui.components.image_comparison")

        output = component._resolve("output/demo.png")
        self.assertEqual(output, (component.PROJECT_ROOT / "output/demo.png").resolve())

        data = component._resolve("data/images/demo.png")
        self.assertEqual(data, (component.EVALS_DIR / "data/images/demo.png").resolve())

        evals_data = component._resolve("evals/data/images/demo.png")
        self.assertEqual(evals_data, (component.PROJECT_ROOT / "evals/data/images/demo.png").resolve())

        absolute_data = component._resolve(str((component.EVALS_DIR / "data/images/demo.png").resolve()))
        self.assertEqual(absolute_data, (component.EVALS_DIR / "data/images/demo.png").resolve())

        self.assertIsNone(component._resolve("/etc/passwd"))
        self.assertIsNone(component._resolve("../secrets.txt"))

    def test_badcase_score_normalization_ignores_missing_scores(self):
        panel = importlib.import_module("evals.ui.components.badcase_panel")

        value = panel._normalize_score({"clip_score": 0.5, "fid": None})

        self.assertEqual(value, 0.5)


class ResultStoreTests(unittest.TestCase):
    def test_load_corrupted_json_returns_empty_corrupted_result(self):
        from evals.executor.result_store import ResultStore

        path = ROOT / "evals" / "data" / "tmp_corrupted_results.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        self.addCleanup(lambda: path.exists() and path.unlink())

        data = ResultStore(str(path)).load()

        self.assertEqual(data["total_results"], 0)
        self.assertEqual(data["results"], [])
        self.assertTrue(data["metadata"]["corrupted"])


class ScorerContractTests(unittest.TestCase):
    def test_score_batch_forwards_pair_metadata(self):
        from evals.scorer.base import BaseScorer

        class RecordingScorer(BaseScorer):
            @property
            def name(self):
                return "recording"

            @property
            def description(self):
                return "recording"

            def score(self, input_path, output_path, prompt="", **kwargs):
                return kwargs

        pair = SimpleNamespace(
            input_path="input.png",
            output_path="output.png",
            prompt="make it modern",
            style="modern_luxury",
            room_type="living_room",
            tags=["warm"],
        )

        self.assertEqual(
            RecordingScorer().score_batch([pair])[0],
            {"style": "modern_luxury", "room_type": "living_room", "tags": ["warm"]},
        )

    def test_summary_skips_none_scores(self):
        _install_cv2_stub()
        from evals.executor.runner import Runner

        Runner()._print_summary([
            SimpleNamespace(scores={"fid": None, "clip_score": 0.4}),
            SimpleNamespace(scores={"fid": None, "clip_score": 0.6}),
        ])


class KnowledgeServiceTests(unittest.TestCase):
    def setUp(self):
        _install_chromadb_stub()

    def test_chroma_where_filter_uses_and_for_multiple_metadata_keys(self):
        service_module = importlib.import_module("app.services.knowledge_service")
        KnowledgeService = service_module.KnowledgeService

        self.assertIsNone(KnowledgeService._build_where_filter(None, None))
        self.assertEqual(
            KnowledgeService._build_where_filter("modern", None),
            {"style": "modern"},
        )
        self.assertEqual(
            KnowledgeService._build_where_filter("modern", "living_room"),
            {"$and": [{"style": "modern"}, {"room_type": "living_room"}]},
        )

    def test_empty_result_can_include_error_code(self):
        service_module = importlib.import_module("app.services.knowledge_service")
        result = service_module.KnowledgeService.__new__(service_module.KnowledgeService)._empty_result(
            "failed",
            error="internal",
        )

        self.assertEqual(result["error"], "internal")


class SegmentationMaskTests(unittest.TestCase):
    def test_point_overlay_is_converted_to_real_mask_base64(self):
        segment = importlib.import_module("app.routes.segment")

        self.assertTrue(hasattr(segment, "_mask_base64_from_overlay"))


class BackendHardeningStaticTests(unittest.TestCase):
    def test_backend_no_longer_logs_key_prefix_or_exposes_docs_by_default(self):
        main_py = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")

        self.assertNotIn("api_key[:15]", main_py)
        self.assertNotIn("llm_api_key[:15]", main_py)
        self.assertIn("docs_url=", main_py)
        self.assertIn("openapi_url=", main_py)

    def test_route_errors_do_not_echo_internal_exception_strings(self):
        segment_py = (ROOT / "backend" / "app" / "routes" / "segment.py").read_text(encoding="utf-8")
        knowledge_py = (ROOT / "backend" / "app" / "routes" / "knowledge.py").read_text(encoding="utf-8")

        self.assertNotIn("str(e)", segment_py)
        self.assertNotIn("str(e)", knowledge_py)


if __name__ == "__main__":
    unittest.main()
