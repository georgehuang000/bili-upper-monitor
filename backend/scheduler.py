"""
APScheduler 定时调度
- 每小时整点：爬取所有UP主最新视频和动态
- 每天 9:00：生成上午总结 (period=morning)
- 每天 17:00：生成下午总结 (period=afternoon)
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

scheduler = AsyncIOScheduler()


async def scheduled_crawl():
    """定时爬取任务"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 开始定时爬取 ===")
    try:
        from crawler.bilibili import crawl_all_uppers
        results = await crawl_all_uppers()
        for r in results:
            print(f"  {r['upper_name']}: {r['status']} - {r['message']}")
    except Exception as e:
        print(f"[定时爬取错误] {e}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 定时爬取完成 ===\n")


async def scheduled_summary_morning():
    """上午总结任务 (9:00)"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 开始生成上午总结 ===")
    try:
        from summarizer.llm import generate_summary
        result = await generate_summary(period="morning")
        print(f"  状态: {result['status']}")
        if "message" in result:
            print(f"  消息: {result['message']}")
    except Exception as e:
        print(f"[总结生成错误] {e}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 上午总结完成 ===\n")


async def scheduled_summary_afternoon():
    """下午总结任务 (17:00)"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 开始生成下午总结 ===")
    try:
        from summarizer.llm import generate_summary
        result = await generate_summary(period="afternoon")
        print(f"  状态: {result['status']}")
        if "message" in result:
            print(f"  消息: {result['message']}")
    except Exception as e:
        print(f"[总结生成错误] {e}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === 下午总结完成 ===\n")


def setup_scheduler():
    """配置定时任务"""
    # 每小时整点爬取
    scheduler.add_job(
        scheduled_crawl,
        trigger=CronTrigger(minute=0),  # 每小时第0分钟
        id="crawl_hourly",
        name="每小时爬取",
        replace_existing=True,
    )

    # 每天 9:00 生成上午总结
    scheduler.add_job(
        scheduled_summary_morning,
        trigger=CronTrigger(hour=9, minute=0),
        id="summary_morning",
        name="上午总结(9:00)",
        replace_existing=True,
    )

    # 每天 17:00 生成下午总结
    scheduler.add_job(
        scheduled_summary_afternoon,
        trigger=CronTrigger(hour=17, minute=0),
        id="summary_afternoon",
        name="下午总结(17:00)",
        replace_existing=True,
    )

    return scheduler
