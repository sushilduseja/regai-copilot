import httpx
from abc import ABC, abstractmethod
from typing import Optional


class CompletionProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        ...

    async def complete_async(self, prompt: str, system_prompt: str = "") -> str:
        return self.complete(prompt, system_prompt)


class NVIDIACompletionProvider(CompletionProvider):
    def __init__(self, api_key: str, model: str = "meta/llama-3.1-8b-instruct"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://integrate.api.nvidia.com/v1"

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        resp = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def complete_async(self, prompt: str, system_prompt: str = "") -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


class CompletionService:
    def __init__(self, provider: Optional[CompletionProvider] = None):
        self._provider = provider

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        if not self._provider:
            raise RuntimeError("No completion provider configured")
        return self._provider.complete(prompt, system_prompt)

    async def complete_async(self, prompt: str, system_prompt: str = "") -> str:
        if not self._provider:
            raise RuntimeError("No completion provider configured")
        return await self._provider.complete_async(prompt, system_prompt)