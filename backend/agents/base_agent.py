import os
import httpx
from typing import AsyncGenerator
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Initialize the Gen AI client once
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in environment!")
else:
    print(f"[DEBUG] Gemini Client initialized with key: {api_key[:8]}...")

client = genai.Client(api_key=api_key)


class BaseAgent:
    MODEL = "gemini-2.0-flash-lite"

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if self.n8n_webhook_url:
            print(f"[DEBUG] BaseAgent initialized with n8n URL: {self.n8n_webhook_url}")
        else:
            print("[WARN] BaseAgent initialized WITHOUT N8N_WEBHOOK_URL!")

    async def _call_n8n(self, prompt: str) -> str:
        """Call n8n webhook as a proxy for Gemini."""
        if not self.n8n_webhook_url or "your-domain" in self.n8n_webhook_url:
            return None
        
        payload = {
            "system_prompt": self.system_prompt,
            "prompt": prompt,
            "model": self.MODEL
        }
        
        print(f"[INFO] Proxying request to n8n: {self.n8n_webhook_url}")
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    self.n8n_webhook_url,
                    json=payload,
                    timeout=90.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract text from common n8n response structures
                if isinstance(data, str): return data
                if isinstance(data, dict):
                    for key in ["output", "text", "content", "result"]:
                        if key in data: return str(data[key])
                return str(data)
        except Exception as e:
            print(f"[WARN] n8n proxy failed: {e}. Falling back to local Gemini...")
            return None

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Yield text chunks. Tries n8n proxy first."""
        n8n_res = await self._call_n8n(prompt)
        if n8n_res:
            yield n8n_res
            return

        try:
            async for chunk in await client.aio.models.generate_content_stream(
                model=self.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0.7,
                ),
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n[ERROR: {e}]"

    def generate(self, prompt: str) -> str:
        """Synchronous generation (used by ideas). Tries n8n proxy first."""
        if self.n8n_webhook_url and "your-domain" not in self.n8n_webhook_url:
            try:
                print(f"[INFO] Sync proxying to n8n: {self.n8n_webhook_url}")
                payload = {"system_prompt": self.system_prompt, "prompt": prompt}
                res = httpx.post(self.n8n_webhook_url, json=payload, timeout=90.0)
                res.raise_for_status()
                data = res.json()
                # Extraction
                if isinstance(data, dict):
                    if "ideas" in data: return str(data["ideas"])
                    for key in ["output", "text", "content", "result"]:
                        if key in data: return str(data[key])
                return str(data)
            except Exception as e:
                print(f"[WARN] Sync n8n proxy failed: {e}")

        try:
            response = client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0.7,
                ),
            )
            return response.text
        except Exception as e:
            print(f"[ERROR] Gemini generation failed: {e}")
            raise e
