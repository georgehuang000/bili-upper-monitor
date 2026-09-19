#!/usr/bin/env bash
# 服务器一次性初始化：创建 venv 并安装后端依赖（需要 Python 3.10+，建议 3.11/3.12）。
# 用法：把项目上传到服务器后，在项目根目录执行  bash deploy/setup_server.sh
set -e
cd "$(dirname "$0")/../server"

if ! command -v python3 >/dev/null; then
    echo "错误：未找到 python3，请先安装 Python 3.10+" >&2
    exit 1
fi

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cat <<'EOF'

依赖安装完成。接下来的步骤：
  1. 配置根目录 .env（至少填好 LLM key）。B站登录态有两种方式：
     a) 启动服务后打开网页点「扫码登录」用 B站 App 扫码（自动写入 .env 并热生效，无需重启）
     b) 或提前把浏览器 F12 里的 Cookie 填进 .env
     未登录时匿名爬取会被 B站风控（表现为 -352），系统会自动跳过该轮并在网页提示。
     注意：用扫码登录时，运行本服务的用户需要对项目根目录 .env 有写权限。
  2. 按实际部署路径修改 deploy/bili-monitor.service 里的 WorkingDirectory / ExecStart
  3. sudo cp deploy/bili-monitor.service /etc/systemd/system/
     sudo systemctl daemon-reload
     sudo systemctl enable --now bili-monitor
  4. 云服务器控制台/防火墙放行 9000 端口（TCP）
     ⚠️ 本项目无鉴权（含扫码登录接口），公网部署请用安全组限制来源 IP 或加反向代理鉴权
  5. 浏览器访问 http://服务器IP:9000

常用命令：
  journalctl -u bili-monitor -f      # 看实时日志
  sudo systemctl restart bili-monitor
  curl -s http://127.0.0.1:9000/api/status   # 本机健康检查
EOF
