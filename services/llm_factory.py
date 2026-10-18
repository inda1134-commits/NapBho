import json, os, re
from typing import Any

class LLMFactory:
    def __init__(self, provider="openai", api_key="", model="", temperature=0.1, max_tokens=2500):
        self.provider = (provider or "openai").lower()
        self.api_key = api_key or self._env_key()
        self.model = model or os.getenv("LLM_MODEL", "")
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)

    def _env_key(self):
        return {
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "google": os.getenv("GOOGLE_API_KEY", ""),
            "anthropic": os.getenv("ANTHROPIC_API_KEY", "")
        }.get(self.provider, "")

    @property
    def available(self):
        return bool(self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw = self.generate_text(system_prompt, user_prompt)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            raise ValueError("LLM 응답에서 JSON 객체를 찾을 수 없습니다.")
        return json.loads(raw[start:end+1])

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.available:
            raise RuntimeError("API 키가 설정되지 않았습니다.")
        if self.provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            model = self.model or "gpt-4.1-mini"
            resp = client.chat.completions.create(
                model=model, temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}]
            )
            return resp.choices[0].message.content or ""
        if self.provider == "google":
            from google import genai
            client = genai.Client(api_key=self.api_key)
            model = self.model or "gemini-2.5-flash"
            resp = client.models.generate_content(
                model=model, contents=f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER:\n{user_prompt}"
            )
            return resp.text or ""
        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            model = self.model or "claude-3-5-haiku-latest"
            resp = client.messages.create(
                model=model, max_tokens=self.max_tokens, temperature=self.temperature,
                system=system_prompt, messages=[{"role":"user","content":user_prompt}]
            )
            return "".join(getattr(x, "text", "") for x in resp.content)
        raise ValueError(f"지원하지 않는 공급자: {self.provider}")
