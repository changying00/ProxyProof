# ProxyProof Docker 部署

> 前提：服务器上有 Docker 和 docker compose v2。本机有 Docker Desktop 时同样适用。

## 一、准备

```bash
git clone https://github.com/changying00/ProxyProof.git
cd ProxyProof
cp .env.example .env      # 默认配置即可直接跑，想改目标站/换端口再编辑
```

不编辑 `.env` 也完全能跑，全部按默认来。挂公网想给 API 加把锁，再在 `.env` 里设 `API_KEY`（可选，设了之后客户端要带 `API-KEY` 头）。

## 二、启动

两种方式二选一：

```bash
# A. 直接用预构建镜像（推荐，快，不用在服务器上编译）
docker compose pull
docker compose up -d

# B. 从源码构建
docker compose up -d --build
```

两个容器：

| 容器 | 内容 | 说明 |
|---|---|---|
| `redis` | Redis 7 + AOF 持久化 | 池子不随重启清零 |
| `app` | getter / tester / server | 起在容器里的三个进程 |

- `docker compose logs -f` 看实时日志（日志直接打 stdout，不写文件）
- `docker compose ps` 确认两个容器都在运行

## 三、验证

```bash
curl "http://127.0.0.1:5555/random"
curl "http://127.0.0.1:5555/stats"
```

- 返回一个 `ip:port` 字符串 = 正常
- 返回 `503` = 池子刚起、还在攒（getter 先抓一轮 1 分钟，tester 再探测，fresh 要 2~4 分钟才涨上来）

> 确认 503 是不是"池子冷启动"：不带 key 参数看 `/stats`，`total` 在涨就是正常。

## 四、公网访问

1. 云安全组放行 `API_PORT`（默认 5555，compose 里改成冷门端口更安静）
2. 服务器防火墙：`ufw allow 5555/tcp`
3. 想给 API 加把锁：`.env` 里设 `API_KEY`，客户端请求带 `API-KEY` 头（可选，不设任何人都能访问）

## 五、更新

```bash
git pull
docker compose pull
docker compose up -d     # 旧容器替换成新镜像
```

Redis 有 AOF 持久化，池子数据会保留（重新探测会自然淘汰旧记录）。

## 常见问题

- **`/random` 返回 403** → 客户端没带 `API-KEY` 头，或头里值不对
- **`curl 127.0.0.1:5555` 连不上** → `docker compose ps` 看 app 是否重启循环；`docker compose logs app | tail -50` 看报错
- **公网连不上** → 先检查云安全组，再看 `ss -lntp | grep 5555`（应显示监听在 0.0.0.0）
- **fresh 一直是 0 但 total 在涨** → 等 2~4 分钟；超过 10 分钟还是 0 再查 `docker compose logs app` 里的探测报错
