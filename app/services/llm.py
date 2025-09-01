from __future__ import annotations

import httpx
from typing import Optional

from app.config import settings


async def deepseek_complete(prompt: str, system: Optional[str] = None, max_tokens: int = 512) -> str:
    """Call DeepSeek completion endpoint to generate helpful text."""
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120) as client:  # Увеличиваем таймаут до 2 минут
        r = await client.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()






