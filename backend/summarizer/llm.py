"""
AI 总结模块
使用 DeepSeek V4 Pro (通过 SenseAudio API) 生成每日总结
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
import aiosqlite

from config import (
    SENSETIME_KEY, LLM_API_URL, LLM_MODEL, DB_PATH, UPPERS,
)


SUMMARY_SYSTEM_PROMPT = """你是一位专业的股市财经内容分析助手。你的任务是：
1. 阅读多位B站财经UP主的最新视频和动态内容
2. 提炼每位UP主的核心观点、市场判断和操作建议
3. 对比不同UP主的观点异同
4. 总结当前市场的整体情绪和热点方向

请用简洁清晰的结构化格式输出总结，包含以下部分：
- 【市场概览】：整体市场情绪和方向判断
- 【各UP主观点】：逐位列出每位UP主的核心观点
- 【热点方向】：当前讨论较多的板块/题材
- 【观点对比】：不同UP主之间的观点异同
- 【风险提示】：需要注意的风险点

注意：内容仅供参考，不构成投资建议。"""


def _build_summary_prompt(videos_data: list, dynamics_data: list) -> str:
    """构建发送给LLM的提示词"""
    upper_names = [u["name"] for u in UPPERS]
    parts = [f"以下是 {len(upper_names)} 位B站UP主在近期发布的视频和动态内容，请分析总结：\n\n"]

    # 按UP主分组
    upper_map = {u["name"]: u for u in UPPERS}

    for name in upper_names:
        u = upper_map[name]
        upper_videos = [v for v in videos_data if v.get("upper_name") == name]
        upper_dynamics = [d for d in dynamics_data if d.get("upper_name") == name]

        if not upper_videos and not upper_dynamics:
            continue

        parts.append(f"\n{'='*40}")
        parts.append(f"【{name}】")
        parts.append(f"{'='*40}\n")

        if upper_videos:
            parts.append("视频：")
            for v in upper_videos[:10]:  # 限制数量避免token过多
                parts.append(f"  - [{v.get('pub_date','')}] {v.get('title','')}")
                if v.get("description"):
                    parts.append(f"    描述: {v['description'][:200]}")
        else:
            parts.append("视频：(无)")

        if upper_dynamics:
            parts.append("\n动态：")
            for d in upper_dynamics[:10]:
                parts.append(f"  - [{d.get('pub_date','')}] {d.get('content','')[:300]}")
        else:
            parts.append("\n动态：(无)")

    parts.append("\n\n请根据以上内容生成总结。")
    return "".join(parts)


async def generate_summary(period: str = "full") -> dict:
    """
    生成AI总结
    period: 'morning' (9点), 'afternoon' (17点), 'full' (全天)
    """
    if not SENSETIME_KEY:
        return {
            "status": "error",
            "message": "未配置 sensetime_key，请在 .env 文件中设置",
        }

    now = datetime.now()
    summary_date = now.strftime("%Y-%m-%d")

    # 根据周期确定时间范围
    if period == "morning":
        start_time = (now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    elif period == "afternoon":
        start_time = now.replace(hour=9, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
    else:
        start_time = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    # 从数据库读取自上次总结以来的新内容
    videos_data = []
    dynamics_data = []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 获取上次总结时间
        cur = await db.execute(
            "SELECT MAX(created_at) as last_time FROM summaries WHERE summary_date=?",
            (summary_date,),
        )
        row = await cur.fetchone()
        last_summary_time = row["last_time"] if row and row["last_time"] else start_time

        # 获取新视频
        cur = await db.execute(
            """SELECT v.*, u.name as upper_name
               FROM videos v JOIN uppers u ON v.upper_id = u.id
               WHERE v.pub_date >= ?
               ORDER BY v.pub_date DESC""",
            (last_summary_time,),
        )
        for row in await cur.fetchall():
            videos_data.append(dict(row))

        # 获取新动态
        cur = await db.execute(
            """SELECT d.*, u.name as upper_name
               FROM dynamics d JOIN uppers u ON d.upper_id = u.id
               WHERE d.pub_date >= ?
               ORDER BY d.pub_date DESC""",
            (last_summary_time,),
        )
        for row in await cur.fetchall():
            dynamics_data.append(dict(row))

    if not videos_data and not dynamics_data:
        return {
            "status": "skip",
            "summary_date": summary_date,
            "message": "没有新的内容需要总结",
        }

    # 构建提示词
    prompt = _build_summary_prompt(videos_data, dynamics_data)

    # 调用 LLM
    headers = {
        "Authorization": f"Bearer {SENSETIME_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "stream": False,
        "max_tokens": 4096,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(LLM_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 保存到数据库
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO summaries (summary_date, summary_period, content) VALUES (?, ?, ?)",
                    (summary_date, period, content),
                )
                await db.commit()

            return {
                "status": "success",
                "summary_date": summary_date,
                "content": content,
                "message": f"总结完成，涵盖{len(videos_data)}条视频和{len(dynamics_data)}条动态",
            }
    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "message": f"API调用失败: {e.response.status_code} - {e.response.text[:200]}",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"总结生成失败: {str(e)}",
        }
