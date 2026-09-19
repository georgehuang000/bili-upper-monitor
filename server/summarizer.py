# -*- coding: utf-8 -*-
"""Daily investment-content report generation via the DeepSeek LLM gateway.

- Collects the last 24h of new videos (title + desc) and dynamics text per UP.
- Builds a grouped Chinese prompt, truncated to ~8000 chars.
- Calls deepseek-v4-pro (fallback deepseek-v4-flash) through the OpenAI SDK
  pointed at the SenseTime gateway. Retries twice on failure.
- Persists the markdown result into the summaries table.
"""
import threading
import time
from datetime import datetime

from openai import OpenAI

import config
import db
import crawler_runner

_client = None
# independent mutex for summarization (separate from the crawl lock)
_summarize_lock = threading.Lock()


def _client_instance():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.SENSETIME_KEY, base_url=config.LLM_BASE_URL)
    return _client


def _build_prompt(period_label: str):
    since_ts = int(time.time()) - config.SUMMARY_LOOKBACK_HOURS * 3600
    sections = []
    has_any = False
    for u in db.subscribed_uppers():
        uid = u["uid"]
        name = u["name"]
        videos = db.recent_videos_since(uid, since_ts)
        dynamics = db.recent_dynamics_since(uid, since_ts)
        if not videos and not dynamics:
            continue
        has_any = True
        buf = [f"## UP主：{name}（uid={uid}）"]
        if videos:
            buf.append("### 近24小时新视频")
            for v in videos:
                d = (v.get("desc") or "").strip()
                d = f"，简介：{d}" if d else ""
                s = (v.get("summary") or "").strip()
                s = f"\n  AI摘要：{s}" if s else ""
                buf.append(f"- 标题：{v['title']}{d}{s} 链接：{v['url']}")
        if dynamics:
            buf.append("### 近24小时新动态")
            for dy in dynamics:
                txt = (dy.get("text") or "").strip().replace("\n", " ")
                buf.append(f"- [{dy.get('type')}] {txt} 链接：{dy['url']}")
        sections.append("\n".join(buf))

    material = "\n\n".join(sections)
    if len(material) > config.SUMMARY_INPUT_MAX_CHARS:
        material = material[: config.SUMMARY_INPUT_MAX_CHARS] + "\n...(内容过长已截断)"

    system = (
        "你是一名专业的财经/投资内容分析助手。请基于给定的B站UP主近24小时"
        "投稿视频与动态素材，生成一份结构清晰的中文投资内容日报（Markdown格式）。"
    )
    user = (
        f"以下是{period_label}截至现在近24小时内，各投资类UP主的新内容素材：\n\n"
        f"{material}\n\n"
        "请生成一份Markdown日报，要求：\n"
        "1. 顶部一段整体综述（当日投资观点/情绪概览）；\n"
        "2. 按【UP主】分小节，每节概括其核心观点、关注标的、风险提示；\n"
        "3. 每条要点后保留对应来源链接（用Markdown链接）；\n"
        "4. 语言精炼、客观，不臆造未提供的信息；\n"
        "5. 结尾附一句风险免责声明。"
    )
    return system, user, has_any


def _call_llm(system: str, user: str):
    """Try primary model, then fallback; each with retries. Returns (content, model)."""
    client = _client_instance()
    models = [config.LLM_MODEL, config.LLM_MODEL_FALLBACK]
    last_err = None
    for model in models:
        for attempt in range(3):  # 1 try + 2 retries
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.4,
                    timeout=120,
                )
                content = resp.choices[0].message.content
                if content and content.strip():
                    return content, model
                last_err = "empty response"
            except Exception as ex:
                last_err = str(ex)
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"LLM call failed: {last_err}")


def summarize_video(title: str, desc: str, subtitle_text: str) -> str:
    """基于字幕为单个视频生成 80~150 字核心观点摘要（纯文本，入库展示用）。"""
    subtitle_text = (subtitle_text or "").strip()[: config.SUMMARY_VIDEO_INPUT_MAX_CHARS]
    system = "你是专业的财经内容编辑，擅长把长视频字幕提炼成准确、信息密度高的摘要。"
    user = (
        f"以下是B站视频的字幕内容（可能截断）。\n"
        f"标题：{title}\n"
        f"简介：{desc or '无'}\n\n"
        f"{subtitle_text}\n\n"
        "请用中文写一段80~150字的核心观点摘要：概括该视频讨论的行情/标的与结论，"
        "保留关键数字和明确观点，不要客套话，不要逐句复述，"
        "直接输出摘要正文，不要任何标题、格式符号或免责声明。"
    )
    content, _ = _call_llm(system, user)
    return content.strip()


def generate(period: str = "manual"):
    """Generate and persist a report. period in {morning, evening, manual}.

    NOTE: does NOT manage the summarizing mutex itself; callers must go through
    start_generate_bg() or generate_sync().
    """
    try:
        crawler_runner.STATE["last_summary_error"] = None
        label = {"morning": "今日早间", "evening": "今日晚间"}.get(period, "手动触发")
        system, user, has_any = _build_prompt(label)
        if not has_any:
            user += "\n\n注意：近24小时暂无新增素材，请生成一份说明当前无新增内容的简短日报。"
        content, model = _call_llm(system, user)
        date = datetime.now().strftime("%Y-%m-%d")
        sid = db.insert_summary(date=date, period=period, content=content, model=model)
        return {"ok": True, "id": sid, "model": model, "date": date}
    except Exception as ex:
        crawler_runner.STATE["last_summary_error"] = str(ex)
        raise


def _try_begin_summarize() -> bool:
    """Atomically claim the summarize mutex. Returns False if already running."""
    with _summarize_lock:
        if crawler_runner.STATE["summarizing"]:
            return False
        crawler_runner.STATE["summarizing"] = True
        return True


def _end_summarize():
    with _summarize_lock:
        crawler_runner.STATE["summarizing"] = False


def generate_sync(period: str = "manual") -> bool:
    """Guarded synchronous generation (used by the scheduler).
    Returns False without doing anything if a summarization is already running."""
    if not _try_begin_summarize():
        return False
    try:
        generate(period=period)
    finally:
        _end_summarize()
    return True


def start_generate_bg(period: str = "manual") -> bool:
    """Claim the summarize mutex and start a background generation.
    Returns False (nothing started) if a summarization is already running."""
    if not _try_begin_summarize():
        return False

    def _worker():
        try:
            generate(period=period)
        except Exception:
            pass
        finally:
            _end_summarize()

    threading.Thread(target=_worker, daemon=True).start()
    return True


def is_summarizing():
    return crawler_runner.STATE["summarizing"]
