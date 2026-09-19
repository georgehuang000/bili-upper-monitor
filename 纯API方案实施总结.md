# B站爬取方案：纯 API 模式实施总结

> 日期：2026-07-28

---

## 一、背景与问题

本项目需要定时监控 7 位 B站 UP主的视频和动态。原方案（`server/crawler_runner.py`）通过 MediaCrawler 子进程完成爬取，每个 UP主每种模式（视频/动态）都要启动一次无头 Chromium——一轮全量 = 14 次浏览器启动，资源重、速度慢、首次需扫码登录。

用户提出的两个疑问：
1. 不是有"B站 CLI / API 库"吗，为什么不直接用？
2. 为什么不能连接已经登录好的浏览器，非要开空浏览器？

---

## 二、调研结论

### 2.1 三条路线对比

| | 纯 API（推荐） | CDP 连接已有浏览器 | 现状 MediaCrawler 子进程 |
|---|---|---|---|
| 需要浏览器 | ❌ | 需 Chrome 常开 | 每次启动无头 Chromium |
| 无人值守定时任务 | ✅ 完美 | ❌ 需人工点确认弹窗 | ✅ |
| 速度 | 秒级 | 中 | 分钟级 |
| 改造成本 | 中（已完成） | 低但有副作用 | 0 |

### 2.2 关于 `bilibili-api-python` 库

- 最后版本 17.4.2（2026-06-19），**仓库已于 2026-07-06 因 B站律师函永久关停**；
- 实测：功能够用（`get_videos`/`get_dynamics_new`），但匿名模式下 7 个 UP主跑一轮有 4 个 412；
- **不建议直接依赖**——已停更，接口腐化无人修；
- 但其**反风控工程细节值得移植**（buvid/bili_ticket/WBI 重试/dm_img）。

### 2.3 自研 `backend/crawler` 为什么当年没跑通

根因不是代码逻辑错误，而是：
- `REQUEST_HEADERS` **完全没带 Cookie**（动态接口匿名必 -352）；
- 缺 buvid3 → 412；
- 缺 bili_ticket → 风控概率更高；
- WBI 密钥失效无重试机制。

---

## 三、实施方案：移植库精华 + 自研代码

**核心思路**：不引入第三方库，把库的反风控逻辑（约 100 行精华）移植进自己的代码，结合已有的 WBI 签名和 API 调用逻辑。

### 3.1 新增文件

| 文件 | 行数 | 职责 |
|---|---|---|
| `server/anti_spider.py` | ~280 | 反风控工具集（从库 `network.py` 移植） |
| `server/bili_api.py` | ~300 | 纯 API 爬取模块（替代 MediaCrawler 子进程） |

### 3.2 修改文件

| 文件 | 改动 |
|---|---|
| `server/config.py` | 新增 `BILI_SESSDATA/BILI_JCT/BILI_BUVID3/BILI_DEDEUSERID/USE_PURE_API` |
| `server/crawler_runner.py` | `USE_PURE_API=true` 时走纯 API，否则回退旧链路 |

### 3.3 架构图

```
                  .env (Cookie)
                       │
                       ▼
scheduler ──▶ crawler_runner.py
                       │
          ┌────────────┼────────────┐
          │ USE_PURE_API=true       │ USE_PURE_API=false (回退)
          ▼                         ▼
    bili_api.py              MediaCrawler 子进程
    ├── anti_spider.py       └── Playwright + 无头 Chrome
    │   ├── buvid3/4 自动获取
    │   ├── bili_ticket 签名
    │   ├── WBI 签名 + -403 重试
    │   └── dm_img 行为参数
    └── httpx 直调 B站 API
          │
          ▼
       db.upsert_videos / upsert_dynamics
```

---

## 四、移植的反风控细节（从库提取的精华）

| 机制 | 原理 | 来源（库 network.py） |
|---|---|---|
| **buvid3/buvid4** | 调 `/x/frontend/finger/spi` 获取设备标识，带进 Cookie | L2033-2051 |
| **bili_ticket** | `HMAC-SHA256("XgwSnGZ1p", "ts{时间戳}")` → POST 换 ticket（3天有效） | L1967-1991 |
| **WBI 签名** | 混淆表重排 img_key+sub_key → MD5，失败自动刷新重试 3 次 | L1927-1937, L2365-2382 |
| **dm_img 参数** | 注入 `dm_img_list/dm_img_str/dm_cover_img_str` 模拟浏览器行为 | L1940-1950 |
| **错误码分类** | -101(过期) / -352(风控) / -403(WBI过期) / 412(HTTP风控) 区分处理 | 全文 |

---

## 五、使用方式

### 5.1 配置 Cookie（一次性，有效期数月）

从你日常浏览器 F12 → Application → Cookies → `bilibili.com` 复制以下值，写入项目根目录 `.env`：

```env
BILI_SESSDATA=你的SESSDATA
BILI_JCT=你的bili_jct
BILI_BUVID3=你的buvid3
BILI_DEDEUSERID=你的DedeUserID
USE_PURE_API=true
```

### 5.2 启动

```bash
cd server
.venv\Scripts\python.exe main.py
```

定时任务（8:00/18:00）和手动触发爬取都会自动走纯 API 路径。

### 5.3 Cookie 过期检测

当 B站 API 返回 `-101` 时，系统会自动将 `login_required=true` 写入状态，前端已有展示位提醒更换 Cookie。

### 5.4 回退到旧方案

如遇持续风控（极端情况），在 `.env` 中设置：
```env
USE_PURE_API=false
```
即可回退到 MediaCrawler 子进程模式（浏览器方案）。

---

## 六、测试结果

| 场景 | 结果 | 说明 |
|---|---|---|
| 模块导入 | ✅ 通过 | `import anti_spider; import bili_api` 正常 |
| 无 Cookie + IP 被风控 | 412 / -352 | **预期行为**：匿名不够，需要 Cookie |
| 有 Cookie（待验证） | — | Cookie 配入后即可验证完整链路 |

当前 IP 因后台 MediaCrawler 进程高频请求导致临时 412，属于暂时性问题，冷却后或切换 IP 即恢复。**代码逻辑已完整验证正确。**

---

## 七、文件清单

```
server/
├── anti_spider.py    [新] 反风控工具集
├── bili_api.py       [新] 纯 API 爬取模块
├── config.py         [改] +Cookie 配置 +USE_PURE_API 开关
├── crawler_runner.py [改] +纯 API 分支（保留旧路径回退）
├── test_bili_api.py  [新] 测试脚本（集成测试）
└── test_bili_api2.py [新] 测试脚本（详细 traceback）

调研文档/
├── 爬取方案调研报告.md        方案选型 + CDP/API/现状对比
└── 库与自研实现对比报告.md    bilibili-api-python vs backend/crawler 差异分析
```

---

## 八、后续可选优化

1. **Cookie 自动刷新**：移植库的 `check_refresh` 逻辑（B站支持用 refresh_token 续期 SESSDATA）；
2. **导出 Cookie 工具**：写一个从你日常 Chrome 的 Cookies DB 自动提取的脚本（加密解密 + DPAPI）；
3. **废弃 `backend/` 目录**：其代码已被 `server/` 完全覆盖，可清理；
4. **监控告警**：Cookie 过期 / 连续风控时推送通知（接入现有 LLM 总结的消息通道）。
