"""
Gemini Image Generation 客户端
双供应商架构:
  - Google AI Studio 直连（主力，需 GEMINI_API_KEY）
  - API易 代理（备选，需 APIYI_KEY 或 LLM_APIYI_KEY）
"""

import os
import base64
import httpx
import logging
from typing import Optional, List
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GetGoModel(str, Enum):
    """支持的 Gemini 模型列表"""
    GEMINI_3_PRO_IMAGE = "gemini-3-pro-image-preview"
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image"
    GEMINI_25_FLASH_IMAGE_PREVIEW = "gemini-2.5-flash-image-preview"


class AspectRatio(str, Enum):
    """支持的宽高比"""
    RATIO_1_1 = "1:1"
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_4_3 = "4:3"
    RATIO_3_4 = "3:4"


class ImageSize(str, Enum):
    """支持的图片大小"""
    SIZE_1K = "1K"
    SIZE_2K = "2K"
    SIZE_4K = "4K"


# ---------------------------------------------------------------------------
# Shared helpers (Google & APIYI both use Gemini API format)
# ---------------------------------------------------------------------------

def _image_to_base64(image_data: bytes) -> str:
    return base64.b64encode(image_data).decode('utf-8')


def _base64_to_image(base64_str: str) -> bytes:
    return base64.b64decode(base64_str)


def _detect_mime_type(image_data: bytes) -> str:
    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    elif image_data[:2] == b'\xff\xd8':
        return "image/jpeg"
    elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"


def _build_gemini_payload(
    prompt: str,
    reference_image: Optional[bytes],
    aspect_ratio: str,
    image_size: str,
) -> dict:
    """Build Gemini API request payload (shared across providers)"""
    parts = []
    if reference_image:
        mime_type = _detect_mime_type(reference_image)
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": _image_to_base64(reference_image)
            }
        })
    parts.append({"text": prompt})

    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size
            }
        }
    }


def _parse_gemini_response(result: dict) -> dict:
    """Parse Gemini API response and extract image data (shared across providers)"""
    candidates = result.get("candidates", [])
    if not candidates:
        return {"code": -1, "msg": "API returned empty candidates", "data": None}

    images = []
    for candidate in candidates:
        for part in candidate.get("content", {}).get("parts", []):
            inline_data = part.get("inlineData", {})
            image_b64 = inline_data.get("data", "")
            if image_b64:
                images.append({
                    "data": _base64_to_image(image_b64),
                    "mime_type": inline_data.get("mimeType", "image/jpeg")
                })

    if not images:
        return {"code": -1, "msg": "No image data in response", "data": None}

    return {"code": 0, "msg": "success", "data": {"images": images}}


# ---------------------------------------------------------------------------
# Google AI Studio direct client (PRIMARY)
# ---------------------------------------------------------------------------

class GoogleAIDirectClient:
    """Google AI Studio direct — bypass middleman, call Gemini API natively"""

    BASE_URL = "https://generativelanguage.googleapis.com"
    MAX_RETRIES = 3

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )

    @property
    def api_key(self) -> Optional[str]:
        return os.getenv("GEMINI_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _build_url(self, model_name: str) -> str:
        model = model_name.value if hasattr(model_name, 'value') else str(model_name)
        return f"{self.BASE_URL}/v1beta/models/{model}:generateContent?key={self.api_key}"

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model: str = GetGoModel.GEMINI_3_PRO_IMAGE,
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1,
    ) -> dict:
        """Call Google Gemini API directly to generate interior design images"""
        if not self.is_configured:
            return {"code": -1, "msg": "GEMINI_API_KEY not configured", "data": None}

        payload = _build_gemini_payload(prompt, reference_image, aspect_ratio, image_size)
        api_url = self._build_url(model)

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[Google] attempt {attempt + 1}/{self.MAX_RETRIES}, model: {model}")

                response = await self.client.post(
                    api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )

                if response.status_code == 200:
                    parsed = _parse_gemini_response(response.json())
                    if parsed.get("code") == 0 and parsed.get("data"):
                        parsed["data"]["used_model"] = str(model)
                        parsed["data"]["provider"] = "google_direct"
                        logger.info(f"[Google] success, {len(parsed['data']['images'])} image(s)")
                    return parsed

                error_text = response.text
                logger.warning(f"[Google] HTTP {response.status_code}: {error_text[:300]}")

                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    continue

                return {
                    "code": -1,
                    "msg": f"Google API error ({response.status_code}): {error_text[:200]}",
                    "data": None
                }

            except httpx.TimeoutException as e:
                logger.warning(f"[Google] timeout: {e}")
                last_error = f"timeout: {e}"
                continue
            except httpx.HTTPError as e:
                logger.warning(f"[Google] network error: {e}")
                last_error = f"network: {e}"
                continue
            except Exception as e:
                logger.error(f"[Google] unexpected: {e}")
                last_error = f"unexpected: {e}"
                continue

        return {
            "code": -1,
            "msg": f"Google API failed after {self.MAX_RETRIES} retries: {last_error}",
            "data": None,
        }

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# APIYI proxy client (FALLBACK)
# ---------------------------------------------------------------------------

class GetGoAPIClient:
    """APIYI proxy client — access Gemini via api.apiyi.com"""

    MAX_RETRIES = 3
    BASE_URL = "https://api.apiyi.com"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )

    @property
    def api_key(self) -> Optional[str]:
        return os.getenv("APIYI_KEY") or os.getenv("LLM_APIYI_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        if not self.api_key:
            raise ValueError("APIYI_KEY or LLM_APIYI_KEY not set")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _build_url(self, model_name: str) -> str:
        model = model_name.value if hasattr(model_name, 'value') else str(model_name)
        return f"{self.BASE_URL}/v1beta/models/{model}:generateContent"

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model: str = GetGoModel.GEMINI_3_PRO_IMAGE,
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1,
    ) -> dict:
        """Call APIYI Gemini API to generate interior design images"""
        if not self.is_configured:
            return {"code": -1, "msg": "APIYI_KEY / LLM_APIYI_KEY not configured", "data": None}

        payload = _build_gemini_payload(prompt, reference_image, aspect_ratio, image_size)
        api_url = self._build_url(model)

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[APIYI] attempt {attempt + 1}/{self.MAX_RETRIES}, model: {model}")

                response = await self.client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    parsed = _parse_gemini_response(response.json())
                    if parsed.get("code") == 0 and parsed.get("data"):
                        parsed["data"]["used_model"] = str(model)
                        parsed["data"]["provider"] = "apiyi"
                        logger.info(f"[APIYI] success, {len(parsed['data']['images'])} image(s)")
                    return parsed

                error_text = response.text
                logger.warning(f"[APIYI] HTTP {response.status_code}: {error_text[:300]}")

                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    continue

                return {
                    "code": -1,
                    "msg": f"APIYI error ({response.status_code}): {error_text[:200]}",
                    "data": None
                }

            except httpx.TimeoutException as e:
                logger.warning(f"[APIYI] timeout: {e}")
                last_error = f"timeout: {e}"
                continue
            except httpx.HTTPError as e:
                logger.warning(f"[APIYI] network error: {e}")
                last_error = f"network: {e}"
                continue
            except Exception as e:
                logger.error(f"[APIYI] unexpected: {e}")
                last_error = f"unexpected: {e}"
                continue

        return {
            "code": -1,
            "msg": f"APIYI failed after {self.MAX_RETRIES} retries: {last_error}",
            "data": None,
        }

    async def generate_with_fallback(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model_priority: Optional[List[str]] = None,
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1,
    ) -> dict:
        """APIYI model-level fallback (kept for backward compatibility)"""
        if model_priority is None:
            model_priority = [GetGoModel.GEMINI_3_PRO_IMAGE, GetGoModel.GEMINI_25_FLASH_IMAGE]

        last_error = None
        for model in model_priority:
            result = await self.generate_image(
                prompt=prompt, reference_image=reference_image,
                model=model, aspect_ratio=aspect_ratio,
                image_size=image_size, number_of_images=number_of_images,
            )
            if result.get("code") == 0:
                return result

            error_msg = result.get("msg", "")
            last_error = error_msg
            if "timeout" in error_msg.lower() or "500" in error_msg or "503" in error_msg:
                continue
            return result

        return {
            "code": -1,
            "msg": f"APIYI all models failed. Last error: {last_error}",
            "data": None,
        }

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Custom Gemini-compatible providers (NEW API / ONE API style platforms)
# Configure via env vars: CUSTOM_API_1_URL, CUSTOM_API_1_KEY, CUSTOM_API_1_MODELS
# ---------------------------------------------------------------------------

class CustomGeminiProvider:
    """Configurable Gemini-native provider (e.g., NEW API / ONE API platforms)"""

    MAX_RETRIES = 3

    def __init__(self, name: str, base_url: str, api_key: str, models: List[str]):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.models = models
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self.base_url and self.models)

    def _build_url(self, model_name: str) -> str:
        return f"{self.base_url}/v1beta/models/{model_name}:generateContent"

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }

    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model: str = "",
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1,
    ) -> dict:
        """Call custom Gemini-compatible API to generate images"""
        if not model:
            model = self.models[0] if self.models else "gemini-2.5-flash-image"

        payload = _build_gemini_payload(prompt, reference_image, aspect_ratio, image_size)
        api_url = self._build_url(model)

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[{self.name}] attempt {attempt + 1}/{self.MAX_RETRIES}, model: {model}")

                response = await self.client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    parsed = _parse_gemini_response(response.json())
                    if parsed.get("code") == 0 and parsed.get("data"):
                        parsed["data"]["used_model"] = str(model)
                        parsed["data"]["provider"] = self.name
                        logger.info(f"[{self.name}] success, {len(parsed['data']['images'])} image(s)")
                    return parsed

                error_text = response.text
                logger.warning(f"[{self.name}] HTTP {response.status_code}: {error_text[:300]}")

                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    continue

                return {
                    "code": -1,
                    "msg": f"{self.name} error ({response.status_code}): {error_text[:200]}",
                    "data": None
                }

            except httpx.TimeoutException as e:
                logger.warning(f"[{self.name}] timeout: {e}")
                last_error = f"timeout: {e}"
                continue
            except httpx.HTTPError as e:
                logger.warning(f"[{self.name}] network error: {e}")
                last_error = f"network: {e}"
                continue
            except Exception as e:
                logger.error(f"[{self.name}] unexpected: {e}")
                last_error = f"unexpected: {e}"
                continue

        return {
            "code": -1,
            "msg": f"{self.name} failed after {self.MAX_RETRIES} retries: {last_error}",
            "data": None,
        }

    async def close(self):
        await self.client.aclose()


def _load_custom_providers() -> List[CustomGeminiProvider]:
    """Load custom Gemini providers from CUSTOM_API_* env vars"""
    providers = []
    for i in range(1, 11):  # support up to 10 custom providers, gaps allowed
        url = os.getenv(f"CUSTOM_API_{i}_URL")
        key = os.getenv(f"CUSTOM_API_{i}_KEY")
        if not url or not key:
            continue  # skip gaps, don't break
        name = os.getenv(f"CUSTOM_API_{i}_NAME", f"custom_{i}")
        models_str = os.getenv(f"CUSTOM_API_{i}_MODELS", "gemini-2.5-flash-image")
        models = [m.strip() for m in models_str.split(",") if m.strip()]
        providers.append(CustomGeminiProvider(name, url, key, models))
        logger.info(f"[Providers] loaded custom provider '{name}': {url} ({len(models)} models)")
    return providers


# ---------------------------------------------------------------------------
# Multi-provider fallback chain
# ---------------------------------------------------------------------------

_google_client: Optional[GoogleAIDirectClient] = None
_apiyi_client: Optional[GetGoAPIClient] = None


def _get_google_client() -> GoogleAIDirectClient:
    global _google_client
    if _google_client is None:
        _google_client = GoogleAIDirectClient()
    return _google_client


def _get_apiyi_client() -> GetGoAPIClient:
    global _apiyi_client
    if _apiyi_client is None:
        _apiyi_client = GetGoAPIClient()
    return _apiyi_client


async def generate_design_image(
    prompt: str,
    reference_image: Optional[bytes] = None,
    model_priority: Optional[List[str]] = None,
    aspect_ratio: str = AspectRatio.RATIO_4_3,
    image_size: str = ImageSize.SIZE_1K,
    number_of_images: int = 1,
) -> dict:
    """
    Generate interior design renderings with multi-provider auto-fallback.

    Priority: Custom providers (CUSTOM_API_*) → APIYI
    Within each provider, models are tried in order.
    """
    if model_priority is None:
        model_priority = [GetGoModel.GEMINI_3_PRO_IMAGE, GetGoModel.GEMINI_25_FLASH_IMAGE]

    # --- Tier 1: Custom Gemini-compatible providers (burn existing balance first) ---
    for provider in _load_custom_providers():
        if not provider.is_configured:
            continue
        logger.info(f"[Fallback] trying custom provider '{provider.name}'...")
        for model in provider.models:
            result = await provider.generate_image(
                prompt=prompt, reference_image=reference_image,
                model=model, aspect_ratio=aspect_ratio,
                image_size=image_size, number_of_images=number_of_images,
            )
            if result.get("code") == 0:
                logger.info(f"[Fallback] ✅ {provider.name} SUCCESS (model: {model})")
                return result

            error_msg = result.get("msg", "")
            logger.warning(f"[Fallback] ❌ {provider.name} FAILED: {error_msg[:100]}")
            if "timeout" not in error_msg.lower() and "500" not in error_msg and "503" not in error_msg:
                break
            logger.info(f"[Fallback] ↪ {provider.name} temporary error, trying next model...")

    # --- Tier 2: APIYI proxy (last resort) ---
    apiyi = _get_apiyi_client()
    if apiyi.is_configured:
        logger.info("[Fallback] trying APIYI (last resort)...")
        for model in model_priority:
            result = await apiyi.generate_image(
                prompt=prompt, reference_image=reference_image,
                model=model, aspect_ratio=aspect_ratio,
                image_size=image_size, number_of_images=number_of_images,
            )
            if result.get("code") == 0:
                logger.info(f"[Fallback] ✅ APIYI SUCCESS (model: {model})")
                return result

            error_msg = result.get("msg", "")
            logger.warning(f"[Fallback] ❌ APIYI FAILED: {error_msg[:100]}")
            if "timeout" not in error_msg.lower() and "500" not in error_msg and "503" not in error_msg:
                break
            logger.info(f"[Fallback] ↪ APIYI temporary error, trying next model...")

    return {
        "code": -1,
        "msg": "All providers and models exhausted. Check API key configuration.",
        "data": None,
    }


# ---------------------------------------------------------------------------
# Backward-compatible exports
# ---------------------------------------------------------------------------

DEFAULT_MODEL_PRIORITY = [
    GetGoModel.GEMINI_3_PRO_IMAGE,
    GetGoModel.GEMINI_25_FLASH_IMAGE,
]

# Legacy global instance (for callers that haven't migrated to generate_design_image)
getgoapi_client = GetGoAPIClient()
