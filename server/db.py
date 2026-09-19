# -*- coding: utf-8 -*-
"""SQLite persistence layer (SQLAlchemy).

Tables:
- uppers(uid PK, name, face, subscribed)   ← 订阅名单的唯一数据源
- videos(bvid PK, uid, title, cover, desc, pub_ts, play, url)
- dynamics(dyn_id PK, uid, type, text, pub_ts, url)
- summaries(id PK autoincrement, date, period, content, model, created_ts)

All writes for videos/dynamics use UPSERT for incremental dedup.
"""
import time
from contextlib import contextmanager
from typing import Iterable, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import declarative_base, sessionmaker

import config

Base = declarative_base()

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class Upper(Base):
    __tablename__ = "uppers"
    uid = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    face = Column(String, nullable=True)
    # 1=订阅中, 0=已取消(保留历史数据, 重新订阅即恢复); config 仅作首次引导
    subscribed = Column(Integer, nullable=False, default=1)


class Video(Base):
    __tablename__ = "videos"
    bvid = Column(String, primary_key=True)  # stores "av{aid}"
    uid = Column(String, nullable=False, index=True)
    title = Column(Text)
    cover = Column(Text)
    desc = Column(Text)
    pub_ts = Column(Integer, index=True)
    play = Column(Integer)
    url = Column(Text)
    subtitle = Column(Text)  # B站字幕全文（AI字幕/CC字幕）
    summary = Column(Text)   # LLM 生成的单视频摘要


class Dynamic(Base):
    __tablename__ = "dynamics"
    dyn_id = Column(String, primary_key=True)
    uid = Column(String, nullable=False, index=True)
    type = Column(String)
    text = Column(Text)
    pub_ts = Column(Integer, index=True)
    url = Column(Text)


class Summary(Base):
    __tablename__ = "summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, index=True)
    period = Column(String)
    content = Column(Text)
    model = Column(String)
    created_ts = Column(Integer)


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    Base.metadata.create_all(engine)
    _migrate_columns()
    seed_uppers()


def _migrate_columns():
    """Lightweight migration: ADD COLUMN for tables created before a column
    existed (create_all won't alter existing tables)."""
    wanted = {
        "videos": [("subtitle", "TEXT"), ("summary", "TEXT")],
        "uppers": [("subscribed", "INTEGER NOT NULL DEFAULT 1")],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in cols:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def seed_uppers():
    """Bootstrap the configured UP masters on first run.

    uppers 表本身就是订阅名单：.env 的 UP_UIDS 仅在对应行不存在时引导插入，
    不会重新激活用户已取消订阅（subscribed=0）的 UP 主。
    """
    with session_scope() as s:
        for uid in config.UP_UIDS:
            existing = s.get(Upper, str(uid))
            if existing is None:
                s.add(Upper(uid=str(uid), name=config.up_name(uid), face=None,
                            subscribed=1))
            elif existing.subscribed:
                existing.name = config.up_name(uid)


def subscribed_uids() -> list:
    """当前订阅中的 UID 列表（爬取/总结以此为准）。

    DB 尚未初始化（如表还不存在）时回退到 config.UP_UIDS，保证模块导入期
    的调用（如 crawler_runner._load_state）不炸。
    """
    try:
        with session_scope() as s:
            rows = s.execute(
                select(Upper.uid).where(Upper.subscribed == 1)
            ).scalars().all()
            return [str(u) for u in rows]
    except Exception:
        return [str(u) for u in config.UP_UIDS]


def subscribed_uppers() -> list:
    """当前订阅中的 (uid, name) 列表，供状态展示用。"""
    try:
        with session_scope() as s:
            rows = s.execute(
                select(Upper.uid, Upper.name).where(Upper.subscribed == 1)
            ).all()
            return [{"uid": str(uid), "name": name} for uid, name in rows]
    except Exception:
        return [{"uid": str(u), "name": config.up_name(u)} for u in config.UP_UIDS]


def add_upper(uid: str, name: str, face=None) -> bool:
    """加入订阅。返回 True=新增/恢复, False=原本就在订阅中。"""
    uid = str(uid).strip()
    with session_scope() as s:
        existing = s.get(Upper, uid)
        if existing is None:
            s.add(Upper(uid=uid, name=name, face=face, subscribed=1))
            return True
        if existing.subscribed:
            return False
        existing.subscribed = 1
        if name:
            existing.name = name
        if face and not existing.face:
            existing.face = face
        return True


def remove_upper(uid: str) -> bool:
    """取消订阅（保留其视频/动态历史数据）。返回 True=确实取消了订阅。"""
    uid = str(uid).strip()
    with session_scope() as s:
        existing = s.get(Upper, uid)
        if existing is None or not existing.subscribed:
            return False
        existing.subscribed = 0
        return True


# ---------------------------------------------------------------------------
# UPSERT helpers
# ---------------------------------------------------------------------------
def upsert_videos(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    n = 0
    with session_scope() as s:
        for r in rows:
            stmt = sqlite_insert(Video).values(**r)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Video.bvid],
                set_={
                    "title": stmt.excluded.title,
                    "cover": stmt.excluded.cover,
                    "desc": stmt.excluded.desc,
                    "pub_ts": stmt.excluded.pub_ts,
                    "play": stmt.excluded.play,
                    "url": stmt.excluded.url,
                },
            )
            s.execute(stmt)
            n += 1
    return n


def upsert_dynamics(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    n = 0
    with session_scope() as s:
        for r in rows:
            stmt = sqlite_insert(Dynamic).values(**r)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Dynamic.dyn_id],
                set_={
                    "type": stmt.excluded.type,
                    "text": stmt.excluded.text,
                    "pub_ts": stmt.excluded.pub_ts,
                    "url": stmt.excluded.url,
                },
            )
            s.execute(stmt)
            n += 1
    return n


def update_upper_face(uid: str, face: Optional[str]):
    if not face:
        return
    with session_scope() as s:
        u = s.get(Upper, str(uid))
        if u is not None and not u.face:
            u.face = face


def update_video_subtitle(bvid: str, text: str, desc: str = "",
                          play: Optional[int] = None, pubdate: Optional[int] = None):
    """写字幕，并可选回填 view 接口的元数据（feed 拿不到的字段）。"""
    with session_scope() as s:
        v = s.get(Video, bvid)
        if v is None:
            return
        if text:
            v.subtitle = text
        if desc:
            v.desc = desc
        if play:
            v.play = int(play)
        if pubdate:
            v.pub_ts = int(pubdate)


def update_video_summary(bvid: str, summary: str):
    with session_scope() as s:
        v = s.get(Video, bvid)
        if v is not None:
            v.summary = summary


def list_videos_missing_summary_since(since_ts: int) -> list:
    """近 since_ts 内、还没有 AI 摘要的视频（批量回填用，跨所有 UP）。"""
    with session_scope() as s:
        rows = (
            s.execute(
                select(Video)
                .where(
                    Video.pub_ts >= since_ts,
                    (Video.summary.is_(None)) | (Video.summary == ""),
                )
                .order_by(Video.pub_ts.desc())
            )
            .scalars()
            .all()
        )
        return [
            {"bvid": r.bvid, "uid": r.uid, "title": r.title or "",
             "desc": r.desc or "", "pub_ts": r.pub_ts, "url": r.url or ""}
            for r in rows
        ]


def recent_videos_unsummarized(uid: str, since_ts: int, limit: int = 5) -> list:
    """近期新发布且还没有 AI 摘要的视频（字幕/摘要补充流程的工作队列）。"""
    with session_scope() as s:
        rows = (
            s.execute(
                select(Video)
                .where(
                    Video.uid == str(uid),
                    Video.pub_ts >= since_ts,
                    (Video.summary.is_(None)) | (Video.summary == ""),
                )
                .order_by(Video.pub_ts.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {"bvid": r.bvid, "title": r.title, "desc": r.desc,
             "pub_ts": r.pub_ts, "url": r.url}
            for r in rows
        ]


def insert_summary(date: str, period: str, content: str, model: str) -> int:
    with session_scope() as s:
        row = Summary(
            date=date,
            period=period,
            content=content,
            model=model,
            created_ts=int(time.time()),
        )
        s.add(row)
        s.flush()
        return row.id


# ---------------------------------------------------------------------------
# query helpers (return plain dicts matching API contract)
# ---------------------------------------------------------------------------
def list_uppers() -> list:
    out = []
    with session_scope() as s:
        uppers = (
            s.execute(select(Upper).where(Upper.subscribed == 1))
            .scalars()
            .all()
        )
        for u in uppers:
            vc = s.execute(
                select(func.count()).select_from(Video).where(Video.uid == u.uid)
            ).scalar_one()
            dc = s.execute(
                select(func.count()).select_from(Dynamic).where(Dynamic.uid == u.uid)
            ).scalar_one()
            out.append(
                {
                    "uid": u.uid,
                    "name": u.name,
                    "face": u.face,
                    "video_count": vc,
                    "dynamic_count": dc,
                    "last_crawl_ts": None,  # filled by caller from state
                }
            )
    return out


def list_videos(uid: str, limit: int = 30, offset: int = 0) -> list:
    with session_scope() as s:
        rows = (
            s.execute(
                select(Video)
                .where(Video.uid == str(uid))
                .order_by(Video.pub_ts.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            {
                "bvid": r.bvid,
                "uid": r.uid,
                "title": r.title,
                "cover": r.cover,
                "pub_ts": r.pub_ts,
                "play": int(r.play) if r.play is not None else 0,
                "url": r.url,
                "desc": r.desc,
                "summary": r.summary,
            }
            for r in rows
        ]


def list_dynamics(uid: str, limit: int = 30, offset: int = 0) -> list:
    with session_scope() as s:
        rows = (
            s.execute(
                select(Dynamic)
                .where(Dynamic.uid == str(uid))
                .order_by(Dynamic.pub_ts.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [
            {
                "dyn_id": r.dyn_id,
                "uid": r.uid,
                "type": r.type,
                "text": r.text,
                "pub_ts": r.pub_ts,
                "url": r.url,
            }
            for r in rows
        ]


def list_summaries(date: Optional[str] = None) -> list:
    with session_scope() as s:
        q = select(Summary)
        if date:
            q = q.where(Summary.date == date).order_by(Summary.created_ts.desc())
        else:
            q = q.order_by(Summary.created_ts.desc()).limit(10)
        rows = s.execute(q).scalars().all()
        return [
            {
                "id": r.id,
                "date": r.date,
                "period": r.period,
                "content": r.content,
                "model": r.model,
                "created_ts": r.created_ts,
            }
            for r in rows
        ]


def recent_videos_since(uid: str, since_ts: int) -> list:
    with session_scope() as s:
        rows = (
            s.execute(
                select(Video)
                .where(Video.uid == str(uid), Video.pub_ts >= since_ts)
                .order_by(Video.pub_ts.desc())
            )
            .scalars()
            .all()
        )
        return [
            {"bvid": r.bvid, "title": r.title, "desc": r.desc,
             "summary": r.summary, "pub_ts": r.pub_ts, "url": r.url}
            for r in rows
        ]


def recent_dynamics_since(uid: str, since_ts: int) -> list:
    with session_scope() as s:
        rows = (
            s.execute(
                select(Dynamic)
                .where(Dynamic.uid == str(uid), Dynamic.pub_ts >= since_ts)
                .order_by(Dynamic.pub_ts.desc())
            )
            .scalars()
            .all()
        )
        return [
            {"dyn_id": r.dyn_id, "type": r.type, "text": r.text,
             "pub_ts": r.pub_ts, "url": r.url}
            for r in rows
        ]
