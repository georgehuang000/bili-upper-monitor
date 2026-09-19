"""
Pydantic 数据模型
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Upper(BaseModel):
    id: int
    name: str
    uid: int
    avatar: str = ""
    fans_count: int = 0


class Video(BaseModel):
    id: int
    upper_id: int
    bvid: str
    title: str
    description: str = ""
    pub_date: str
    play_count: int = 0
    danmaku_count: int = 0
    like_count: int = 0
    coin_count: int = 0
    favorite_count: int = 0
    share_count: int = 0
    cover_url: str = ""
    crawled_at: str = ""

    @property
    def bilibili_url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"


class Dynamic(BaseModel):
    id: int
    upper_id: int
    dynamic_id: str
    dynamic_type: str = ""
    content: str = ""
    pub_date: str
    pictures: str = "[]"
    crawled_at: str = ""

    @property
    def bilibili_url(self) -> str:
        return f"https://t.bilibili.com/{self.dynamic_id}"


class Summary(BaseModel):
    id: int
    summary_date: str
    summary_period: str = "full"
    content: str
    created_at: str


class CrawlResult(BaseModel):
    upper_name: str
    new_videos: int = 0
    new_dynamics: int = 0
    status: str = "success"
    message: str = ""


class SummaryResult(BaseModel):
    status: str = "success"
    summary_date: str = ""
    content: str = ""
    message: str = ""
