#!/usr/bin/env bash
# ProxyProof 一键部署脚本（Ubuntu / Debian）
# 用法：bash deploy.sh [端口]
set -e

PORT="${1:-5555}"
DIR="/opt/ProxyProof"

echo "=== 1/5 检查 Docker ==="
if ! command -v docker &>/dev/null; then
  echo "Docker 未安装，正在安装..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
if ! docker compose version &>/dev/null; then
  echo "docker compose 插件缺失，请运行: sudo apt install docker-compose-plugin"
  exit 1
fi
echo "Docker OK: $(docker version --format '{{.Server.Version}}')"

echo "=== 2/5 拉取代码 ==="
if [ -d "$DIR" ]; then
  cd "$DIR" && git pull
else
  sudo git clone https://github.com/changying00/ProxyProof.git "$DIR"
  cd "$DIR"
fi

echo "=== 3/5 配置 ==="
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^CN_ONLY=false/CN_ONLY=true/" .env
  sed -i "s/^API_PORT=5555/API_PORT=$PORT/" .env
  echo "已生成 .env（CN_ONLY=true, API_PORT=$PORT）"
else
  echo ".env 已存在，跳过"
fi

echo "=== 4/5 启动 ==="
docker compose pull
docker compose up -d

echo "=== 5/5 等待启动（2~4 分钟）==="
sleep 5
docker compose ps

echo ""
echo "=== 部署完成 ==="
echo "API: http://$(curl -s ifconfig.me):$PORT/random"
echo "监控: http://$(curl -s ifconfig.me):$PORT/health"
echo "看日志: cd $DIR && docker compose logs -f"
echo ""
echo "提醒：请在云安全组放行 TCP $PORT 端口"
