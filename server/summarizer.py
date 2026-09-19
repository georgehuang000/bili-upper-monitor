# -*- coding: utf-8 -*-
"""Daily investment-content report generation via the DeepSeek LLM gateway.

- Collects the last 24h of new videos (title + desc) and dynamics text per UP.
- Builds a grouped Chinese prompt, truncated to ~8000 chars.
- Calls LLM_MODEL (fallback LLM_MODEL_FALLBACK) through the OpenAI SDK, whose
  key/base_url/model can be changed at runtime from the web UI (see llm_settings).
- Persists the markdown result into the summaries table.
"""
import threading
import time
from datetime import datetime

import config
import db
import crawler_runner
import llm_client

# independent mutex for summarization (separate from the crawl lock)
_summarize_lock = threading.Lock()

# 认证/权限/地址类错误重试没有意义（换个模型也一样失败），直接放弃
_FATAL_STATUS = (400, 401, 402, 403, 404)


def _client_instance():
    """共享 LLM 客户端。委托给 llm_client，使网页改完密钥后立刻生效。"""
    return llm_client.get_client()


def _image_line(raw, label: str) -> str:
    """把图片识别结果整理成一行素材。

    空值和失败占位（"[识别失败]…"）都不写进 prompt——失败原因是运维信息，
    不是内容，喂给模型只会污染日报。
    """
    t = (raw or "").strip()
    if not t or t.startswith(db.IMAGE_FAIL_PREFIX):
        return ""
    return f"\n  {label}（图片识别）：{t}"


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
                cov = _image_line(v.get("image_desc"), "封面画面")
                buf.append(f"- 标题：{v['title']}{d}{s}{cov} 链接：{v['url']}")
        if dynamics:
            buf.append("### 近24小时新动态")
            for dy in dynamics:
                txt = (dy.get("text") or "").strip().replace("\n", " ")
                pic = _image_line(dy.get("image_desc"), "配图内容")
                buf.append(f"- [{dy.get('type')}] {txt}{pic} 链接：{dy['url']}")
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
        "4. 素材里的「封面画面」「配图内容」是模型读图得到的画面信息，"
        "把它当作该条内容的组成部分一起分析（封面上的大字/研报标题常是核心观点）；\n"
        "5. 语言精炼、客观，不臆造未提供的信息；\n"
        "6. 结尾附一句风险免责声明。"
    )
    return system, user, has_any


def _call_llm(system: str, user: str):
    """Try primary model, then fallback; each with retries. Returns (content, model).

    认证/权限/地址类错误（401/403/404/400/402）不做重试：换模型也一样失败，
    重试只会白等 6 次。真正的临时故障（超时/限流/5xx）才退避重试。
    """
    client = _client_instance()

    models = []
    for m in (config.LLM_MODEL, config.LLM_MODEL_FALLBACK):
        m = (m or "").strip()
        if m and m not in models:
            models.append(m)
    if not models:
        raise RuntimeError("未配置 LLM 模型：请在网页顶栏「模型设置」里填写")

    kwargs = {}
    if not llm_client.thinking_enabled():
        kwargs["temperature"] = 0.4  # 思考模式不接受 temperature，故仅在非思考模式下传
    kwargs.update(llm_client.thinking_kwargs())

    last_err = "未知错误"
    last_status = None
    for model in models:
        for attempt in range(3):  # 1 try + 2 retries
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    timeout=120,
                    **kwargs,
                )
                content = resp.choices[0].message.content
                if content and content.strip():
                    return content, model
                last_err = "模型返回了空内容"
            except Exception as ex:
                hint, status = llm_client.describe_error(ex)
                last_err = f"{hint}（模型={model}，{type(ex).__name__}）"
                last_status = status
                if status in _FATAL_STATUS:
                    break
                time.sleep(1.5 * (attempt + 1))
        if last_status in _FATAL_STATUS:
            break  # 换个模型也是同样的错，别浪费时间
    raise RuntimeError(f"LLM 调用失败：{last_err}")


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
