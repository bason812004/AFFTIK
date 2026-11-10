import os
import re
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx
from backend.app.database import get_setting
from backend.app.services.script_parser import parse_gemini_scripts
from backend.app.config import PROJECTS_DIR

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

class GeminiApiService:
    """
    Direct Google Gemini REST API Client.
    Allows 100% headless execution without launching any web browser.
    Supports script generation (Gemini Flash) and image generation (Imagen 3).
    """

    def get_api_key(self) -> str:
        key = get_setting("gemini_api_key")
        if not key:
            key = os.environ.get("GEMINI_API_KEY", "")
        return key.strip()

    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    async def generate_scripts(
        self,
        project_id: str,
        prompt: str,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates 3 script options using Gemini 1.5/2.0 Flash REST API.
        Runs completely in background in ~2-4 seconds.
        """
        api_key = self.get_api_key()
        if not api_key:
            return {"success": False, "error": "Chưa cấu hình Gemini API Key"}

        model = get_setting("gemini_model", "gemini-1.5-flash")
        url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}"

        parts: List[Dict[str, Any]] = [{"text": prompt}]

        # Include product/character image if available
        if image_path and os.path.exists(image_path):
            try:
                mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
                with open(image_path, "rb") as img_f:
                    img_data = base64.b64encode(img_f.read()).decode("utf-8")
                parts.insert(0, {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": img_data
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to attach image to Gemini API: {e}")

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 4096,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    err_msg = res.text
                    try:
                        err_json = res.json()
                        err_msg = err_json.get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    return {"success": False, "error": f"Gemini API lỗi ({res.status_code}): {err_msg}"}

                data = res.json()
                raw_text = ""
                candidates = data.get("candidates", [])
                if candidates:
                    parts_out = candidates[0].get("content", {}).get("parts", [])
                    for p in parts_out:
                        raw_text += p.get("text", "")

                if not raw_text:
                    return {"success": False, "error": "Gemini API không trả về nội dung kịch bản"}

                # Save raw script to project folder
                script_file = PROJECTS_DIR / project_id / "scripts" / "gemini_api_scripts.md"
                script_file.write_text(raw_text, encoding="utf-8")

                parsed = parse_gemini_scripts(raw_text)
                return {
                    "success": True,
                    "raw_text": raw_text,
                    "parsed": parsed,
                    "count": len(parsed.get("options", []))
                }
        except Exception as e:
            logger.error(f"Gemini API generate_scripts error: {e}")
            return {"success": False, "error": f"Lỗi kết nối Gemini API: {str(e)}"}

    async def generate_character_image(
        self,
        project_id: str,
        prompt: str,
        reference_image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates commercial 9:16 character image using Google Imagen 3 API.
        Saves output to data/projects/{project_id}/character/character_primary.png.
        """
        api_key = self.get_api_key()
        if not api_key:
            return {"success": False, "error": "Chưa cấu hình Gemini API Key"}

        # Try Imagen 3 endpoint
        url = f"{GEMINI_API_BASE}/models/imagen-3.0-generate-002:predict?key={api_key}"

        payload = {
            "instances": [{
                "prompt": prompt
            }],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "9:16",
                "outputOptions": {
                    "mimeType": "image/png"
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    preds = data.get("predictions", [])
                    if preds and "bytesBase64Encoded" in preds[0]:
                        b64_img = preds[0]["bytesBase64Encoded"]
                        img_bytes = base64.b64decode(b64_img)
                        save_path = PROJECTS_DIR / project_id / "character" / "character_primary.png"
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        save_path.write_bytes(img_bytes)

                        return {
                            "success": True,
                            "image_path": str(save_path),
                            "url": f"/data/projects/{project_id}/character/character_primary.png",
                            "method": "imagen3_api"
                        }

                # If Imagen 3 is not supported or returns error, return detailed message
                err_text = res.text
                try:
                    err_json = res.json()
                    err_text = err_json.get("error", {}).get("message", err_text)
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": f"Imagen API lỗi ({res.status_code}): {err_text}",
                    "fallback_to_web": True
                }
        except Exception as e:
            return {"success": False, "error": f"Lỗi gọi Imagen API: {str(e)}", "fallback_to_web": True}

    async def analyze_product_image(self, image_path: str) -> Dict[str, Any]:
        """
        Analyzes the product image to dynamically extract product details.
        """
        api_key = self.get_api_key()
        if not api_key or not os.path.exists(image_path):
            return {"success": False, "error": "Chưa cấu hình API key hoặc file ảnh không tồn tại"}

        model = get_setting("gemini_model", "gemini-1.5-flash")
        url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}"

        prompt = (
            "Hãy nhìn vào bức ảnh sản phẩm này và đọc kỹ bao bì, nhãn mác để phân tích làm video tiếp thị TikTok Affiliate.\n"
            "Trả về DUY NHẤT một khối JSON theo định dạng sau:\n"
            "```json\n"
            "{\n"
            '  "product_name": "<Tên sản phẩm đọc được rõ ràng từ bao bì hoặc hình dáng thực tế>",\n'
            '  "category": "<Ngành hàng chuẩn xác>",\n'
            '  "benefits": "<Tác dụng, công dụng và công năng nổi bật nhất của sản phẩm, đánh mạnh vào giải quyết nỗi đau>",\n'
            '  "highlights": "<2-3 điểm bán hàng vượt trội nhất về chất liệu, thiết kế, tính năng>",\n'
            '  "target_customer": "<Đối tượng khách hàng mục tiêu>",\n'
            '  "offer": "Ưu đãi trợ giá đặc biệt và miễn phí giao hàng hôm nay",\n'
            '  "price": "Ưu đãi giá tốt hôm nay",\n'
            '  "scene1_dialogue": "<Lời thoại tiếng Việt Cảnh 1 dài đúng 42 từ, giọng nữ miền Bắc tự nhiên: mở đầu thu hút (Hook) và giới thiệu trực tiếp tên + công dụng cốt lõi của sản phẩm trong ảnh. TUYỆT ĐỐI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP: không dùng từ cấm như 100%, trị dứt điểm, rẻ nhất, sập sàn, inbox...>",\n'
            '  "scene2_dialogue": "<Lời thoại tiếng Việt Cảnh 2 dài đúng 42 từ, giọng nữ miền Bắc tự nhiên: nêu bật chất liệu, độ bền/an toàn của sản phẩm trong ảnh và kêu gọi bấm ngay vào giỏ hàng bên dưới. TUYỆT ĐỐI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP: không dùng từ cấm như 100%, trị dứt điểm, rẻ nhất, sập sàn, inbox...>"\n'
            "}\n"
            "```"
        )

        try:
            mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
            with open(image_path, "rb") as img_f:
                img_data = base64.b64encode(img_f.read()).decode("utf-8")

            payload = {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": img_data}},
                        {"text": prompt}
                    ]
                }],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
            }

            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
                        json_str = match.group(1) if match else raw_text
                        try:
                            parsed_json = json.loads(json_str.strip())
                            from backend.app.services.prompt_templates import sanitize_tiktok_dialogue
                            from backend.app.services.pipeline_runner import ensure_42_words
                            if parsed_json.get("scene1_dialogue"):
                                parsed_json["scene1_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(parsed_json["scene1_dialogue"]))
                            if parsed_json.get("scene2_dialogue"):
                                parsed_json["scene2_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(parsed_json["scene2_dialogue"]))
                            return {"success": True, "data": parsed_json}
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"analyze_product_image API error: {e}")

        return {"success": False, "error": "Không thể phân tích ảnh qua API"}

gemini_api_service = GeminiApiService()

