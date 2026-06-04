from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class LLMClient:
    def __init__(self, parameters: dict[str, Any], model_profile: str | None = None):
        llm_cfg = parameters["llm"]
        self.provider = llm_cfg.get("provider", "deepseek")
        self.api_key = os.getenv(llm_cfg.get("api_key_env", "DEEPSEEK_API_KEY"), "")
        self.base_url = os.getenv(
            llm_cfg.get("base_url_env", "DEEPSEEK_BASE_URL"),
            llm_cfg.get("default_base_url", "https://api.deepseek.com"),
        ).rstrip("/")
        profiles = llm_cfg.get("profiles", {})
        self.profile = model_profile or llm_cfg.get("default_profile", "strong")
        profile_cfg = profiles.get(self.profile, {})
        model_env = profile_cfg.get("model_env")
        default_model = profile_cfg.get("default_model") or llm_cfg.get("default_model", "deepseek-v4-pro")
        legacy_env = llm_cfg.get("legacy_model_env", "DEEPSEEK_MODEL")
        self.model = os.getenv(model_env, "") if model_env else ""
        if not self.model and self.profile == "strong":
            self.model = os.getenv(legacy_env, "")
        if not self.model:
            self.model = default_model

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            return {
                "provider": self.provider,
                "model": self.model,
                "model_profile": self.profile,
                "status": "skipped_no_api_key",
                "content": {},
            }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {
                "provider": self.provider,
                "model": self.model,
                "model_profile": self.profile,
                "status": "error",
                "error": str(exc),
                "content": {},
            }
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"raw": content}
        return {
            "provider": self.provider,
            "model": self.model,
            "model_profile": self.profile,
            "status": "ok",
            "content": parsed,
        }
