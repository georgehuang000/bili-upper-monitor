"""
SQLite 数据库初始化与连接管理
"""
import aiosqlite
from config import DB_PATH

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS uppers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    uid INTEGER NOT NULL,
    avatar TEXT DEFAULT '',
    fans_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upper_id INTEGER NOT NULL,
    bvid TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    pub_date TEXT NOT NULL,
    play_count INTEGER DEFAULT 0,
    danmaku_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    coin_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    cover_url TEXT DEFAULT '',
    crawled_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (upper_id) REFERENCES uppers(id)
);

CREATE TABLE IF NOT EXISTS dynamics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upper_id INTEGER NOT NULL,
    dynamic_id TEXT NOT NULL UNIQUE,
    dynamic_type TEXT DEFAULT '',
    content TEXT DEFAULT '',
    pub_date TEXT NOT NULL,
    pictures TEXT DEFAULT '[]',
    crawled_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (upper_id) REFERENCES uppers(id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,
    summary_period TEXT DEFAULT 'full',
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upper_id INTEGER,
    crawl_type TEXT NOT NULL,
    status TEXT DEFAULT 'success',
    new_count INTEGER DEFAULT 0,
    message TEXT DEFAULT '',
    crawled_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


async def init_db():
    """初始化数据库表"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()


async def get_db():
    """获取数据库连接"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def ensure_uppers():
    """确保所有UP主都写入数据库"""
    from config import UPPERS
    async with aiosqlite.connect(DB_PATH) as db:
        for u in UPPERS:
            await db.execute(
                """INSERT INTO uppers (name, uid) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET uid=excluded.uid
                WHERE excluded.uid != 0""",
                (u["name"], u["uid"]),
            )
        await db.commit()
