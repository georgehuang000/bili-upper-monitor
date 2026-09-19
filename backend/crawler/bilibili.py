"""
B站爬虫模块
- 爬取UP主视频列表
- 爬取UP主动态列表
- UID 搜索解析
"""
import asyncio
import random
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import httpx
import aiosqlite

from config import (
    BILI_API_BASE, BILI_SPACE_BASE, REQUEST_HEADERS,
    CRAWL_DELAY_MIN, CRAWL_DELAY_MAX,
    VIDEO_PAGE_SIZE, DYNAMIC_PAGE_SIZE, UPPERS, DB_PATH,
)
from crawler.wbi import wbi_signer


async def _delay():
    """随机延时，避免触发风控"""
    await asyncio.sleep(random.uniform(CRAWL_DELAY_MIN, CRAWL_DELAY_MAX))


async def _get_client() -> httpx.AsyncClient:
    """创建 httpx 客户端"""
    return httpx.AsyncClient(
        headers=REQUEST_HEADERS,
        timeout=15.0,
        follow_redirects=True,
    )


# ──────────────────────────────────────────
#  UID 搜索解析
# ──────────────────────────────────────────

async def search_user_by_name(name: str, client: httpx.AsyncClient) -> Optional[int]:
    """
    通过B站搜索API查找用户UID
    注意：搜索API可能需要Cookie，此处尽力尝试
    """
    url = f"{BILI_API_BASE}/x/web-interface/search/type"
    params = {
        "search_type": "bili_user",
        "keyword": name,
        "page": 1,
        "page_size": 5,
    }
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("code") == 0:
            results = data.get("data", {}).get("result", [])
            for r in results:
                if name in r.get("uname", "") or r.get("uname", "") in name:
                    return r["mid"]
            # 如果没有精确匹配，返回第一个结果
            if results:
                return results[0]["mid"]
    except Exception:
        pass
    return None


async def resolve_uids():
    """
    对 uid=0 的UP主，尝试通过搜索API解析UID
    同时更新WBI签名密钥
    """
    unresolved = [u for u in UPPERS if u["uid"] == 0]
    if not unresolved:
        return

    async with await _get_client() as client:
        await wbi_signer.update_keys(client)
        for u in unresolved:
            uid = await search_user_by_name(u["name"], client)
            if uid:
                u["uid"] = uid
                print(f"[解析] {u['name']} -> UID:{uid}")
            else:
                print(f"[警告] 无法解析 {u['name']} 的UID，请手动在 config.py 中填写")
            await _delay()


# ──────────────────────────────────────────
#  UP主信息
# ──────────────────────────────────────────

async def fetch_user_info(uid: int, client: httpx.AsyncClient) -> Optional[dict]:
    """获取UP主基本信息"""
    url = f"{BILI_API_BASE}/x/space/wbi/acc/info"
    params = {"mid": uid}
    params = wbi_signer.sign(params)
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("code") == 0:
            info = data["data"]
            return {
                "uid": uid,
                "name": info.get("name", ""),
                "avatar": info.get("face", ""),
                "fans_count": 0,  # 粉丝数需要另外的接口
            }
    except Exception as e:
        print(f"[错误] 获取用户信息失败 uid={uid}: {e}")
    return None


async def fetch_user_fans(uid: int, client: httpx.AsyncClient) -> int:
    """获取UP主粉丝数"""
    url = f"{BILI_API_BASE}/x/relation/stat"
    params = {"vmid": uid}
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("code") == 0:
            return data["data"].get("follower", 0)
    except Exception:
        pass
    return 0


# ──────────────────────────────────────────
#  视频爬取
# ──────────────────────────────────────────

async def fetch_videos(uid: int, client: httpx.AsyncClient, page_size: int = VIDEO_PAGE_SIZE) -> List[dict]:
    """
    获取UP主最新视频列表
    API: /x/space/wbi/arc/search
    """
    url = f"{BILI_API_BASE}/x/space/wbi/arc/search"
    params = {
        "mid": uid,
        "ps": page_size,
        "pn": 1,
        "order": "pubdate",  # 按发布时间排序（最新）
        "platform": "web",
    }
    params = wbi_signer.sign(params)
    videos = []
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("code") == 0:
            vlist = data.get("data", {}).get("list", {}).get("vlist", [])
            for v in vlist:
                videos.append({
                    "bvid": v.get("bvid", ""),
                    "title": v.get("title", ""),
                    "description": v.get("description", ""),
                    "pub_date": datetime.fromtimestamp(v.get("created", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                    "play_count": v.get("play", 0),
                    "danmaku_count": v.get("video_review", 0),
                    "cover_url": v.get("pic", ""),
                    "uid": uid,
                })
    except Exception as e:
        print(f"[错误] 获取视频列表失败 uid={uid}: {e}")
    return videos


async def save_videos(upper_id: int, uid: int, videos: List[dict]) -> int:
    """将视频保存到数据库（去重）"""
    if not videos:
        return 0
    new_count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for v in videos:
            try:
                cur = await db.execute(
                    """INSERT INTO videos
                    (upper_id, bvid, title, description, pub_date, play_count, danmaku_count, cover_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bvid) DO UPDATE SET
                        play_count=excluded.play_count,
                        danmaku_count=excluded.danmaku_count,
                        cover_url=excluded.cover_url
                    """,
                    (upper_id, v["bvid"], v["title"], v["description"],
                     v["pub_date"], v["play_count"], v["danmaku_count"], v["cover_url"]),
                )
                if cur.rowcount > 0:
                    new_count += 1
            except Exception:
                pass
        await db.commit()
    return new_count


# ──────────────────────────────────────────
#  动态爬取
# ──────────────────────────────────────────

def _extract_dynamic_content(item: dict) -> Tuple[str, str, List[str]]:
    """从动态数据中提取文字内容和图片"""
    dyn_type = item.get("type", "DYNAMIC_TYPE_UNKNOWN")
    modules = item.get("modules", {})
    module_dynamic = modules.get("module_dynamic", {})

    # 提取文字内容
    desc = module_dynamic.get("desc", {})
    content_text = desc.get("text", "") if desc else ""

    # 如果是转发动态，提取原文
    orig = module_dynamic.get("orig", {})
    if orig:
        orig_text = orig.get("text", "")
        content_text = f"[转发] {orig_text}\n---\n{content_text}"

    # 如果是视频动态
    major = module_dynamic.get("major", {})
    if major:
        opus = major.get("opus", {})
        if opus:
            summary_text = opus.get("summary", {}).get("text", "")
            title = opus.get("title", "")
            if title:
                content_text = f"[视频] {title}\n{summary_text}\n{content_text}"
            else:
                content_text = f"[专栏] {summary_text}\n{content_text}"
        archive = major.get("archive", {})
        if archive:
            content_text = f"[视频] {archive.get('title','')}\n{content_text}"
        draw = major.get("draw", {})
        if draw:
            items = draw.get("items", [])
            pictures = [it.get("src", "") for it in items if it.get("src")]
            return dyn_type, content_text, pictures

    # 提取图片
    pictures = []
    if major:
        opus_pics = major.get("opus", {}).get("pics", [])
        pictures = [p.get("url", "") for p in opus_pics if p.get("url")]

    # 从 additional 中提取
    additional = module_dynamic.get("additional", {})
    if additional:
        # 附加内容（如投票等）
        pass

    return dyn_type, content_text, pictures


async def fetch_dynamics(uid: int, client: httpx.AsyncClient, page_size: int = DYNAMIC_PAGE_SIZE) -> List[dict]:
    """
    获取UP主最新动态
    API: /x/polymer/web-dynamic/v1/feed/space
    """
    url = f"{BILI_API_BASE}/x/polymer/web-dynamic/v1/feed/space"
    params = {
        "host_mid": uid,
        "offset": "",
        "platform": "web",
        "features": "itemOpusStyle",
    }
    dynamics = []
    try:
        resp = await client.get(url, params=params)
        data = resp.json()
        if data.get("code") == 0:
            items = data.get("data", {}).get("items", [])
            for item in items[:page_size]:
                dyn_type, content, pictures = _extract_dynamic_content(item)
                # 提取动态ID
                id_str = item.get("id_str", "")
                # 提取发布时间
                pub_ts = item.get("pub_ts", 0)
                pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M:%S") if pub_ts else ""

                dynamics.append({
                    "dynamic_id": id_str,
                    "dynamic_type": dyn_type,
                    "content": content,
                    "pub_date": pub_date,
                    "pictures": json.dumps(pictures),
                    "uid": uid,
                })
    except Exception as e:
        print(f"[错误] 获取动态列表失败 uid={uid}: {e}")
    return dynamics


async def save_dynamics(upper_id: int, uid: int, dynamics: List[dict]) -> int:
    """将动态保存到数据库（去重）"""
    if not dynamics:
        return 0
    new_count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for d in dynamics:
            try:
                cur = await db.execute(
                    """INSERT INTO dynamics
                    (upper_id, dynamic_id, dynamic_type, content, pub_date, pictures)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(dynamic_id) DO UPDATE SET
                        content=excluded.content,
                        pictures=excluded.pictures
                    """,
                    (upper_id, d["dynamic_id"], d["dynamic_type"],
                     d["content"], d["pub_date"], d["pictures"]),
                )
                if cur.rowcount > 0:
                    new_count += 1
            except Exception:
                pass
        await db.commit()
    return new_count


# ──────────────────────────────────────────
#  统一爬取入口
# ──────────────────────────────────────────

async def crawl_all_uppers() -> List[dict]:
    """
    爬取所有UP主的视频和动态
    返回爬取结果列表
    """
    from database import ensure_uppers
    await ensure_uppers()

    results = []
    async with await _get_client() as client:
        # 先更新WBI密钥
        await wbi_signer.update_keys(client)

        for u in UPPERS:
            name = u["name"]
            uid = u["uid"]
            if uid == 0:
                results.append({
                    "upper_name": name,
                    "new_videos": 0,
                    "new_dynamics": 0,
                    "status": "skip",
                    "message": "UID未解析，跳过",
                })
                continue

            print(f"[爬取] {name} (UID:{uid}) ...")

            # 获取UP主ID
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute("SELECT id FROM uppers WHERE name=?", (name,))
                row = await cur.fetchone()
                if not row:
                    results.append({
                        "upper_name": name,
                        "new_videos": 0,
                        "new_dynamics": 0,
                        "status": "error",
                        "message": "UP主未在数据库中",
                    })
                    continue
                upper_id = row["id"]

            # 爬取视频
            videos = await fetch_videos(uid, client)
            new_videos = await save_videos(upper_id, uid, videos)
            await _delay()

            # 爬取动态
            dynamics = await fetch_dynamics(uid, client)
            new_dynamics = await save_dynamics(upper_id, uid, dynamics)
            await _delay()

            print(f"  -> 视频: {len(videos)}条 (新增{new_videos}), 动态: {len(dynamics)}条 (新增{new_dynamics})")

            # 记录日志
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO crawl_logs (upper_id, crawl_type, status, new_count, message) VALUES (?, ?, ?, ?, ?)",
                    (upper_id, "video", "success", new_videos, f"获取{len(videos)}条视频"),
                )
                await db.execute(
                    "INSERT INTO crawl_logs (upper_id, crawl_type, status, new_count, message) VALUES (?, ?, ?, ?, ?)",
                    (upper_id, "dynamic", "success", new_dynamics, f"获取{len(dynamics)}条动态"),
                )
                await db.commit()

            results.append({
                "upper_name": name,
                "new_videos": new_videos,
                "new_dynamics": new_dynamics,
                "status": "success",
                "message": f"视频{len(videos)}条, 动态{len(dynamics)}条",
            })

    return results
