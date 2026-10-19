"""Hacker News MCP Server (hackernews3-mcp).

基于 mcp 2.x 的 MCPServer，提供 Hacker News 资讯、搜索、评论与用户查询能力。

数据源：
- Firebase API : https://hacker-news.firebaseio.com/v0
- Algolia 搜索 : https://hn.algolia.com/api/v1
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

HN_API = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_API = "https://hn.algolia.com/api/v1"

mcp = MCPServer(
    name="hackernews3-mcp",
    title="Hacker News MCP Server",
    description="查询 Hacker News 的热门/最新资讯、按 ID 获取内容、全文搜索、查看用户与评论。",
    version="1.0.0",
)


def _iso_time(ts: int | float | None) -> str | None:
    """把 Unix 时间戳转成 ISO 8601 字符串。"""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _format_story(item: dict[str, Any]) -> dict[str, Any]:
    """把 HN item 精简为对 LLM 友好的结构。"""
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "score": item.get("score"),
        "author": item.get("by"),
        "time": _iso_time(item.get("time")),
        "comments": item.get("descendants"),
        "type": item.get("type"),
    }


def _format_comment(item: dict[str, Any]) -> dict[str, Any]:
    """精简评论结构。"""
    return {
        "id": item.get("id"),
        "author": item.get("author") or item.get("by"),
        "time": _iso_time(item.get("created_at_i") or item.get("time")),
        "text": (item.get("text") or item.get("comment_text") or "").strip()[:500],
        "children": [
            _format_comment(c) for c in item.get("children", [])[:5]
        ],
    }


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    """GET 并解析 JSON，出错时抛出带上下文的异常。"""
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def _get_stories(category: str, limit: int) -> list[dict[str, Any]]:
    """拉取某个榜单的 N 条故事。"""
    limit = max(1, min(limit, 50))
    async with httpx.AsyncClient(timeout=15.0) as client:
        ids: list[int] = await _fetch_json(client, f"{HN_API}/{category}.json")
        ids = ids[:limit]
        items = await asyncio.gather(
            *(_fetch_json(client, f"{HN_API}/item/{i}.json") for i in ids)
        )
    return [
        _format_story(it)
        for it in items
        if isinstance(it, dict) and not it.get("deleted")
    ]


@mcp.tool(description="获取 Hacker News 首页热门故事（Top Stories）")
async def get_top_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回当前最热门的 N 条故事。"""
    return await _get_stories("topstories", limit)


@mcp.tool(description="获取 Hacker News 最新故事（New Stories）")
async def get_new_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回最新的 N 条故事。"""
    return await _get_stories("newstories", limit)


@mcp.tool(description="获取 Hacker News 高分故事（Best Stories）")
async def get_best_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回当前得分最高的 N 条故事。"""
    return await _get_stories("beststories", limit)


@mcp.tool(description="获取 Ask HN 提问（Ask Stories）")
async def get_ask_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回最新的 N 条 Ask HN 提问。"""
    return await _get_stories("askstories", limit)


@mcp.tool(description="获取 Show HN 作品展示（Show Stories）")
async def get_show_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回最新的 N 条 Show HN 作品。"""
    return await _get_stories("showstories", limit)


@mcp.tool(description="获取 Hacker News 招聘信息（Job Stories）")
async def get_job_stories(limit: int = 10) -> list[dict[str, Any]]:
    """返回最新的 N 条招聘信息。"""
    return await _get_stories("jobstories", limit)


@mcp.tool(description="按 ID 获取 Hacker News 单条内容（故事/评论/招聘/投票等）")
async def get_item(item_id: int) -> dict[str, Any]:
    """根据 item id 获取原始内容详情。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        item = await _fetch_json(client, f"{HN_API}/item/{item_id}.json")
    if item is None:
        return {"error": f"item {item_id} 不存在"}
    item["time"] = _iso_time(item.get("time"))
    return item


@mcp.tool(description="在 Hacker News 上全文搜索故事/评论（基于 Algolia API）")
async def search_stories(query: str, limit: int = 10, tags: str = "story") -> list[dict[str, Any]]:
    """搜索 HN 内容，tags 可选 story / comment / ask_hn / show_hn 等。"""
    limit = max(1, min(limit, 50))
    url = f"{ALGOLIA_API}/search"
    params = {"query": query, "tags": tags, "hitsPerPage": limit}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "id": hit.get("objectID"),
            "title": hit.get("title"),
            "url": hit.get("url"),
            "author": hit.get("author"),
            "points": hit.get("points"),
            "num_comments": hit.get("num_comments"),
            "created_at": hit.get("created_at"),
            "story_text": (hit.get("story_text") or "").strip()[:300],
        }
        for hit in data.get("hits", [])
    ]


@mcp.tool(description="获取 Hacker News 用户信息")
async def get_user(username: str) -> dict[str, Any]:
    """返回用户 karma、创建时间、简介等。"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        user = await _fetch_json(client, f"{HN_API}/user/{username}.json")
    if user is None:
        return {"error": f"用户 {username} 不存在"}
    return {
        "id": user.get("id"),
        "karma": user.get("karma"),
        "created": _iso_time(user.get("created")),
        "about": (user.get("about") or "").strip()[:500],
        "submitted_count": len(user.get("submitted") or []),
    }


@mcp.tool(description="获取某条故事及其热门评论")
async def get_story_with_comments(item_id: int, comment_limit: int = 20) -> dict[str, Any]:
    """通过 Algolia items 接口获取故事与评论树。"""
    limit = max(1, min(comment_limit, 50))
    url = f"{ALGOLIA_API}/items/{item_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        data = await _fetch_json(client, url)

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "url": data.get("url"),
        "author": data.get("author"),
        "points": data.get("points"),
        "created_at": data.get("created_at"),
        "story_text": (data.get("text") or "").strip()[:1000],
        "comments": [_format_comment(c) for c in data.get("children", [])[:limit]],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
