# -*- coding: utf-8 -*-
"""Configuration for the server backend.

Loads the workspace-root .env (../.env relative to this file) and exposes
constants used across the app. The secret `sensetime_key` is read but never
printed or logged.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# --- paths ---
SERVER_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SERVER_DIR.parent
ENV_PATH = WORKSPACE_ROOT / ".env"

# MediaCrawler integration paths (legacy fallback mode only; the pure API
# mode never touches these). venv layout differs between Windows and Linux.
MEDIACRAWLER_DIR = WORKSPACE_ROOT / "external" / "MediaCrawler"
if os.name == "nt":
    MC_PYTHON = MEDIACRAWLER_DIR / ".venv" / "Scripts" / "python.exe"
else:
    MC_PYTHON = MEDIACRAWLER_DIR / ".venv" / "bin" / "python"
MC_CONFIG_FILE = MEDIACRAWLER_DIR / "config" / "bilibili_config.py"
MC_JSON_DIR = MEDIACRAWLER_DIR / "data" / "bili" / "json"
MC_LOGIN_DATA_DIR = MEDIACRAWLER_DIR / "browser_data" / "bili_user_data_dir"

# local server data
DB_PATH = SERVER_DIR / "data.db"
TMP_DIR = SERVER_DIR / "tmp"

# load env from workspace root
load_dotenv(dotenv_path=ENV_PATH)


def _get(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val.strip() if val is not None else default


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except (TypeError, ValueError):
        return default


# --- LLM gateway ---
# The secret is read here but MUST NOT be printed/logged anywhere.
SENSETIME_KEY = _get("sensetime_key")
LLM_BASE_URL = _get("LLM_BASE_URL", "https://api.senseaudio.cn/v1")
LLM_MODEL = _get("LLM_MODEL", "deepseek-v4-pro")
LLM_MODEL_FALLBACK = _get("LLM_MODEL_FALLBACK", "deepseek-v4-flash")

# --- UP master list (uid -> name) ---
# 仅作首次启动的引导种子：init_db 时把这里(或 .env UP_UIDS)的 UID 写入
# uppers 表。此后订阅名单以数据库为准，增删请在网页端「监控名单」操作；
# 这里或 .env 的改动不会重新激活已取消订阅的 UP 主。
UP_NAMES = {
    "525121722": "莫大韭菜",
    "11473291": "笨笨的韭菜",
    "3546929266952873": "擒龙先生",
    "322005137": "史诗级韭菜",
    "396958144": "七加一不怕",
    "11430504": "来去由心",
    "3546976515786791": "机构一手调研-福总",
}

# UP_UIDS: prefer .env order if present, else the dict order above
_env_uids = _get("UP_UIDS")
if _env_uids:
    UP_UIDS = [u.strip() for u in _env_uids.split(",") if u.strip()]
else:
    UP_UIDS = list(UP_NAMES.keys())


def up_name(uid: str) -> str:
    return UP_NAMES.get(str(uid), str(uid))


# --- scheduler ---
CRAWL_MORNING = _get("CRAWL_MORNING", "08:00")
CRAWL_EVENING = _get("CRAWL_EVENING", "18:00")
AUTO_CRAWL_ON_START = _get("AUTO_CRAWL_ON_START", "false").lower() in ("1", "true", "yes")

# --- logging ---
# 应用日志级别。默认 INFO：把爬取/enrich 轨迹打到 stdout，便于 journalctl 排错。
LOG_LEVEL = _get("LOG_LEVEL", "INFO").upper()

# --- crawler ---
CRAWL_TIMEOUT_PER_UID = 300  # seconds (5 minutes)
# UID 之间的请求间隔。空间 feed 接口对连续请求很敏感（实测同一轮里前几个
# UID 成功、后面的陆续 -352），间隔给足可显著降低触发率；.env 可覆盖。
CRAWL_SLEEP_MIN = _get_int("CRAWL_SLEEP_MIN", 12)
CRAWL_SLEEP_MAX = _get_int("CRAWL_SLEEP_MAX", 20)
# dynamics pass uses larger spacing to dodge -352 rate-tripping on
# back-to-back feed/space calls
DYN_SLEEP_MIN = _get_int("DYN_SLEEP_MIN", 10)
DYN_SLEEP_MAX = _get_int("DYN_SLEEP_MAX", 20)

# --- summarizer ---
SUMMARY_INPUT_MAX_CHARS = _get_int("SUMMARY_INPUT_MAX_CHARS", 16000)
SUMMARY_LOOKBACK_HOURS = 24
# 逐视频摘要：送入 LLM 的字幕截断长度（8万字符≈4.5小时口播，v4-flash 128k上下文可容纳）
SUMMARY_VIDEO_INPUT_MAX_CHARS = _get_int("SUMMARY_VIDEO_INPUT_MAX_CHARS", 80000)
# 字幕入库全文上限（20万字符≈8小时直播回放）
SUBTITLE_MAX_CHARS = _get_int("SUBTITLE_MAX_CHARS", 200000)

# --- Bilibili Cookie (for pure API crawler) ---
# 从 .env 读取登录态，如：BILI_SESSDATA=xxx\nBILI_JCT=xxx\nBILI_BUVID3=xxx\nBILI_DEDEUSERID=xxx
BILI_SESSDATA = _get("BILI_SESSDATA")
BILI_JCT = _get("BILI_JCT")
BILI_BUVID3 = _get("BILI_BUVID3")
BILI_BUVID4 = _get("BILI_BUVID4")
BILI_DEDEUSERID = _get("BILI_DEDEUSERID")

# 是否启用纯 API 模式（True=不用 MediaCrawler 子进程）
USE_PURE_API = _get("USE_PURE_API", "true").lower() in ("1", "true", "yes")

# --- CORS ---
CORS_ORIGINS = ["http://localhost:5173"]
