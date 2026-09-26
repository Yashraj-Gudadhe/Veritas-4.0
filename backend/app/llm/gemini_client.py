import json
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logger import logger

class GeminiClient:
    """
    Fallback Reasoning Engine: Google Gemini API
    Activated ONLY when Grok fails, times out, rate limits, or is unavailable.
    """

    @classmethod
    async def generate_reasoning(
        cls,
        prompt: str,
        system_instruction: str = "You are VERITAS, an evidence-auditing medical decision intelligence engine. Output strictly valid JSON."
    ) -> Optional[Dict[str, Any]]:
        if not settings.GEMINI_API_KEY:
            logger.info("GEMINI_API_KEY not configured.")
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_instruction}\n\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT_SEC) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_val = candidates[0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text_val)
                        logger.info("Gemini fallback reasoning successful.")
                        return parsed
                else:
                    logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
                    return None
        except Exception as e:
            logger.warning(f"Gemini API fallback error: {str(e)}")
            return None
        return None

    @classmethod
    async def extract_image_text(cls, image_bytes: bytes, mime_type: str) -> str:
        """
        Uses Gemini Vision capability to extract clinical text and describe findings from an uploaded image.
        """
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured. Cannot process image.")
            return "Image processing failed: Vision AI is not configured."

        import base64
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "Analyze this medical document or image. Extract all readable text, tables, and data accurately. If it is an image (like an X-ray or skin lesion), provide a detailed clinical description of the findings. Structure the output clearly."
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": b64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_val = candidates[0]["content"]["parts"][0]["text"]
                        logger.info("Gemini Vision processing successful.")
                        return text_val
                else:
                    logger.warning(f"Gemini Vision API returned status {resp.status_code}: {resp.text}")
                    return f"Image processing failed: API returned {resp.status_code}"
        except Exception as e:
            logger.warning(f"Gemini Vision API error: {str(e)}")
            return f"Image processing failed: {str(e)}"
        return "Image processing failed: No response generated."
