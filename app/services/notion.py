from __future__ import annotations

import httpx
from typing import Any, Dict

from app.config import settings


BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {settings.notion_api_key}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


async def create_goal_page(data: Dict[str, Any]) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        payload = {
            "parent": {"database_id": settings.notion_database_goals},
            "properties": data,
        }
        r = await client.post(f"{BASE_URL}/pages", json=payload, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("id", "")


async def create_task_page(data: Dict[str, Any]) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        payload = {
            "parent": {"database_id": settings.notion_database_tasks},
            "properties": data,
        }
        r = await client.post(f"{BASE_URL}/pages", json=payload, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("id", "")






