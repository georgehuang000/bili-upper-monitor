# -*- coding: utf-8 -*-
"""FastAPI application exposing the monitoring API.

Run:  cd server; ./.venv/Scripts/python.exe -m uvicorn main:app --port 9000
"""
import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
import db
import bili_api
import bili_login
import crawler_runner
import diagnostics
import summarizer
import scheduler


def _setup_logging():
    """让应用日志（爬取/enrich 轨迹）真正输出到 stdout。

    此前没人调用 basicConfig，root logger 停在 WARNING，导致
    `logger.info("[crawler] uid=... enrich: ...")` 这类排查关键信息
    在服务里完全看不到（journalctl 里只有 warning）。
    """
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx/httpcore 每个请求都打 INFO，太吵
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("main")

# UP 主 UID：3 位以上纯数字（B站 UID 实际均 ≥ 6 位，放宽以兼容历史号）
_UID_RE = re.compile(r"^\d{3,}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="B站UP主投资内容监控", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/uppers")
def get_uppers():
    rows = db.list_uppers()
    for r in rows:
        r["last_crawl_ts"] = crawler_runner.last_crawl_ts(r["uid"])
        r["last_error"] = crawler_runner.last_error(r["uid"])
    return rows


# --- 订阅管理：搜索 / 添加 / 取消订阅 ---

class AddUpperReq(BaseModel):
    uid: str
    name: str = ""  # 可选，仅当 B站信息拉取失败时兜底展示


@app.get("/api/uppers/search")
def search_uppers(q: str = Query(..., min_length=1, max_length=50)):
    """订阅搜索：纯数字输入按 UID 直查用户卡片，否则按昵称关键词搜索。

    返回 {candidates: [{uid, name, face, fans, sign?, videos?}]}。
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="搜索词不能为空")
    try:
        if _UID_RE.match(q):
            try:
                card = asyncio.run(bili_api.fetch_user_card(q))
                return {"candidates": [{**card, "sign": ""}]}
            except bili_api.BiliApiError as e:
                if e.code == -404:
                    raise HTTPException(status_code=404,
                                        detail=f"未找到 UID 为 {q} 的用户")
                # card 接口被风控等情况下退回关键词搜索
        return {"candidates": asyncio.run(bili_api.search_users(q))}
    except HTTPException:
        raise
    except bili_api.BiliApiError as e:
        raise HTTPException(status_code=502,
                            detail=f"B站接口异常({e.code}): {e.message or '请稍后再试'}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"B站接口异常: {e}")


@app.post("/api/uppers")
def add_upper(req: AddUpperReq):
    """加入订阅。成功后立即在后台抓取该 UP 主一轮，让首页卡片尽快有数据。"""
    uid = req.uid.strip()
    if not _UID_RE.match(uid):
        raise HTTPException(status_code=400, detail="UID 必须是纯数字")

    name = req.name.strip()
    face = None
    try:
        card = asyncio.run(bili_api.fetch_user_card(uid))
        name = card.get("name") or name
        face = card.get("face")
    except bili_api.BiliApiError as e:
        if e.code == -404:
            raise HTTPException(status_code=404,
                                detail=f"UID {uid} 在B站不存在，请检查后重试")
        if not name:
            raise HTTPException(
                status_code=502,
                detail=f"无法从B站确认该 UID({e.code})，请稍后再试或改用搜索选择",
            )
    if not name:
        raise HTTPException(status_code=400, detail="缺少 UP 主昵称")

    if not db.add_upper(uid, name, face):
        return {"ok": True, "already": True, "message": f"{name} 已在订阅中"}

    # 登录态失效时后台抓取会被跳过，提示语要说实话，别让用户以为已经在抓了
    login_ok = not crawler_runner.STATE.get("login_required", False)
    crawl_started = crawler_runner.start_single_bg(uid)
    if crawl_started and login_ok:
        msg = f"已订阅 {name}，正在后台抓取其最新内容"
    elif crawl_started:
        msg = f"已订阅 {name}，但B站登录态已失效、暂未抓取内容，请先在顶栏「扫码登录」"
    else:
        msg = f"已订阅 {name}，将随下一轮爬取抓取其内容"
    return {"ok": True, "already": False, "crawl_started": crawl_started,
            "login_required": not login_ok, "message": msg}


@app.delete("/api/uppers/{uid}")
def remove_upper(uid: str):
    """取消订阅（保留其历史数据，重新添加即恢复）。"""
    if db.remove_upper(uid):
        return {"ok": True, "message": "已取消订阅"}
    raise HTTPException(status_code=404, detail="该 UP 主不在订阅中")


@app.get("/api/uppers/{uid}/videos")
def get_videos(uid: str, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0)):
    return db.list_videos(uid, limit=limit, offset=offset)


@app.get("/api/uppers/{uid}/dynamics")
def get_dynamics(uid: str, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0)):
    return db.list_dynamics(uid, limit=limit, offset=offset)


@app.get("/api/summaries")
def get_summaries(date: str | None = Query(None)):
    return db.list_summaries(date=date)


@app.get("/api/status")
def get_status():
    # 登录态缓存过期时后台复查一次（非阻塞），让登录失效在网页上及时可见，
    # 不必等到下一轮爬取才发现
    crawler_runner.maybe_refresh_login_state()
    return {
        "uppers": crawler_runner.get_status_uppers(),
        "crawling": crawler_runner.is_crawling(),
        "summarizing": summarizer.is_summarizing(),
        "login_required": crawler_runner.STATE.get("login_required", False),
        "login_checked_ts": crawler_runner.login_checked_ts(),
        "last_summary_error": crawler_runner.STATE.get("last_summary_error"),
    }


@app.get("/api/diagnostics")
def get_diagnostics():
    """一站式诊断快照（排错先看这个）。不含任何凭据值。"""
    return diagnostics.snapshot()


@app.post("/api/crawl")
def post_crawl():
    if not crawler_runner.start_full_round_bg():
        return {"ok": False, "message": "已在爬取中，请稍后再试"}
    return {"ok": True, "message": "已启动后台爬取任务"}


@app.post("/api/summarize")
def post_summarize():
    if not summarizer.start_generate_bg(period="manual"):
        return {"ok": False, "message": "已在生成总结中，请稍后再试"}
    return {"ok": True, "message": "已启动后台总结任务"}


# --- 扫码登录：生成二维码 / 轮询结果 / 检测登录态 ---

@app.post("/api/login/qrcode")
async def login_qrcode():
    """生成 B站登录二维码（前端展示，用 B站 App 扫码）。"""
    try:
        return await bili_login.create_qr()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"二维码生成失败：{e}")


@app.get("/api/login/qrcode/poll")
async def login_qrcode_poll(key: str = Query(..., min_length=8, max_length=128)):
    """轮询扫码状态；确认后登录态写入 .env 并即时生效（无需重启）。"""
    try:
        return await bili_login.poll_qr(key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"轮询失败：{e}")


@app.get("/api/login/status")
async def login_status():
    """主动检测登录态是否有效。"""
    return await bili_login.check_status()


# --- serve the built frontend (web/dist) so one process handles everything ---
# Must be registered after the /api routes: this catch-all resolves any
# non-API GET to a static file, falling back to the SPA entry point so
# react-router paths like /upper/123 work on direct page loads.
WEB_DIST = config.WORKSPACE_ROOT / "web" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path:
        candidate = (WEB_DIST / full_path).resolve()
        try:
            candidate.relative_to(WEB_DIST.resolve())
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            return FileResponse(candidate)
    return FileResponse(WEB_DIST / "index.html")
