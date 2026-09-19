"""
项目配置：UP主列表、API Key、常量等
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# SenseAudio API 配置
SENSETIME_KEY = os.getenv("sensetime_key", "")
LLM_API_URL = "https://api.senseaudio.cn/v1/chat/completions"
LLM_MODEL = "deepseek-v4-pro"

# B站 API 基础地址
BILI_API_BASE = "https://api.bilibili.com"
BILI_SPACE_BASE = "https://space.bilibili.com"

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "monitor.db")

# UP主列表 (UID 已确认的填入，未确认的留 0 运行时解析)
UPPERS = [
    {"name": "莫大韭菜", "uid": 525121722},
    {"name": "笨笨的韭菜", "uid": 11473291},
    {"name": "擒龙先生", "uid": 3546929266952873},
    {"name": "史诗级韭菜", "uid": 322005137},
    {"name": "七加一不怕", "uid": 0},        # 需运行时搜索解析
    {"name": "来去由心", "uid": 0},           # 需运行时搜索解析 (可能为"来去由心998")
    {"name": "机构一手调研-福总", "uid": 0},  # 需运行时搜索解析
]

# 爬虫请求配置
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求间隔 (秒)
CRAWL_DELAY_MIN = 1.0
CRAWL_DELAY_MAX = 3.0

# 每次抓取视频数量
VIDEO_PAGE_SIZE = 30
# 每次抓取动态数量
DYNAMIC_PAGE_SIZE = 20
