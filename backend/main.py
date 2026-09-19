"""
FastAPI 主入口
- 初始化数据库
- 配置定时任务
- 提供 REST API 接口
"""
import sys
import os

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite

from config import DB_PATH, UPPERS
from database import init_db, ensure_uppers
from scheduler import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理"""
    # 初始化数据库
    await init_db()
    await ensure_uppers()
    print("[启动] 数据库初始化完成")

    # 解析未知UID
    from crawler.bilibili import resolve_uids
    await resolve_uids()

    # 启动定时任务
    sched = setup_scheduler()
    sched.start()
    print("[启动] 定时任务已启动")
    print(f"  - 每小时整点爬取")
    print(f"  - 每天 09:00 上午总结")
    print(f"  - 每天 17:00 下午总结")
    print(f"[启动] 服务运行在 http://localhost:8000")

    yield

    # 关闭
    sched.shutdown()
    print("[关闭] 定时任务已停止")


app = FastAPI(
    title="B站UP主监控",
    description="爬取B站财经UP主视频和动态，生成AI每日总结",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────
#  API 接口
# ──────────────────────────────────────────

@app.get("/api/uppers")
async def get_uppers():
    """获取所有UP主列表"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM uppers ORDER BY id")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


@app.get("/api/videos")
async def get_videos(
    upper_id: int = Query(default=0, description="UP主ID，0表示全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取视频列表"""
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if upper_id > 0:
            cur = await db.execute(
                """SELECT v.*, u.name as upper_name, u.uid as upper_uid
                   FROM videos v JOIN uppers u ON v.upper_id = u.id
                   WHERE v.upper_id = ?
                   ORDER BY v.pub_date DESC LIMIT ? OFFSET ?""",
                (upper_id, page_size, offset),
            )
        else:
            cur = await db.execute(
                """SELECT v.*, u.name as upper_name, u.uid as upper_uid
                   FROM videos v JOIN uppers u ON v.upper_id = u.id
                   ORDER BY v.pub_date DESC LIMIT ? OFFSET ?""",
                (page_size, offset),
            )
        rows = await cur.fetchall()
        videos = [dict(r) for r in rows]
        # 添加B站链接
        for v in videos:
            v["bilibili_url"] = f"https://www.bilibili.com/video/{v['bvid']}"
            v["upper_url"] = f"https://space.bilibili.com/{v['upper_uid']}"
        return {"videos": videos, "page": page, "page_size": page_size}


@app.get("/api/dynamics")
async def get_dynamics(
    upper_id: int = Query(default=0, description="UP主ID，0表示全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取动态列表"""
    offset = (page - 1) * page_size
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if upper_id > 0:
            cur = await db.execute(
                """SELECT d.*, u.name as upper_name, u.uid as upper_uid
                   FROM dynamics d JOIN uppers u ON d.upper_id = u.id
                   WHERE d.upper_id = ?
                   ORDER BY d.pub_date DESC LIMIT ? OFFSET ?""",
                (upper_id, page_size, offset),
            )
        else:
            cur = await db.execute(
                """SELECT d.*, u.name as upper_name, u.uid as upper_uid
                   FROM dynamics d JOIN uppers u ON d.upper_id = u.id
                   ORDER BY d.pub_date DESC LIMIT ? OFFSET ?""",
                (page_size, offset),
            )
        rows = await cur.fetchall()
        dynamics = [dict(r) for r in rows]
        for d in dynamics:
            d["bilibili_url"] = f"https://t.bilibili.com/{d['dynamic_id']}"
            d["upper_url"] = f"https://space.bilibili.com/{d['upper_uid']}"
        return {"dynamics": dynamics, "page": page, "page_size": page_size}


@app.get("/api/summaries")
async def get_summaries(
    date: str = Query(default="", description="日期 YYYY-MM-DD，空表示最新"),
):
    """获取AI总结"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if date:
            cur = await db.execute(
                "SELECT * FROM summaries WHERE summary_date = ? ORDER BY created_at DESC",
                (date,),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM summaries ORDER BY created_at DESC LIMIT 5"
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


@app.get("/api/stats")
async def get_stats():
    """获取统计数据"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT COUNT(*) as count FROM videos")
        video_count = (await cur.fetchone())["count"]

        cur = await db.execute("SELECT COUNT(*) as count FROM dynamics")
        dynamic_count = (await cur.fetchone())["count"]

        cur = await db.execute("SELECT COUNT(*) as count FROM summaries")
        summary_count = (await cur.fetchone())["count"]

        cur = await db.execute(
            "SELECT COUNT(*) as count FROM uppers WHERE uid != 0"
        )
        active_uppers = (await cur.fetchone())["count"]

        cur = await db.execute("SELECT COUNT(*) as count FROM uppers")
        total_uppers = (await cur.fetchone())["count"]

        # 最近爬取日志
        cur = await db.execute(
            "SELECT * FROM crawl_logs ORDER BY crawled_at DESC LIMIT 10"
        )
        recent_logs = [dict(r) for r in await cur.fetchall()]

        return {
            "total_videos": video_count,
            "total_dynamics": dynamic_count,
            "total_summaries": summary_count,
            "active_uppers": active_uppers,
            "total_uppers": total_uppers,
            "recent_logs": recent_logs,
        }


@app.post("/api/crawl")
async def trigger_crawl():
    """手动触发爬取"""
    from crawler.bilibili import crawl_all_uppers
    results = await crawl_all_uppers()
    return {"status": "success", "results": results}


@app.post("/api/summarize")
async def trigger_summarize(
    period: str = Query(default="full", description="总结周期: morning/afternoon/full"),
):
    """手动触发AI总结"""
    from summarizer.llm import generate_summary
    result = await generate_summary(period=period)
    return result


@app.get("/")
async def root():
    return {"message": "B站UP主监控 API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
