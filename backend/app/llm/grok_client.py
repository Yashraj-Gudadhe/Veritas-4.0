import json
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logger import logger

class GrokClient:
    """
    Primary Reasoning Engine: Groq
    Executes Layer 2 clinical synthesis and structured reasoning.
    Sends only minimal extracted claims and evidence summaries to maximize speed, privacy, and credit savings.
    """

    @classmethod
    async def generate_reasoning(
        cls,
        prompt: str,
        system_instruction: str = "You are VERITAS, an evidence-auditing medical decision intelligence engine. Output strictly valid JSON."
    ) -> Optional[Dict[str, Any]]:
        if not settings.GROQ_API_KEY:
            logger.info("GROQ_API_KEY not configured. Skipping Groq primary call.")
            return None

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=settings.GROQ_TIMEOUT_SEC) as client:
                url = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"
                resp = await client.post(url, json=payload, headers=headers)
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    logger.info(f"Groq reasoning successful using model {settings.GROQ_MODEL}.")
                    return parsed
                else:
                    logger.warning(f"Groq API returned status {resp.status_code}: {resp.text}")
                    return None
        except Exception as e:
            logger.warning(f"Groq API request failed or timed out: {str(e)}")
            return None
