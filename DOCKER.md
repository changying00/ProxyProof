# ProxyProof Docker 部署

> 前提：服务器上有 Docker 和 docker compose v2。本机有 Docker Desktop 时同样适用。

## 一、准备

```bash
git clone https://github.com/changying00/ProxyProof.git
cd ProxyProof
cp .env.example .env
vim .env
```

`.env` 必改两项：

```ini
# 不设等于任何人都能读你的池子、摘你的代理
API_KEY=随机字符串

# 部署机与探测目标站最好同区域，韩国机器一般保持默认即可
# PROBE_TARGETS={"default":[{"url":"http://cp.cloudflare.com/","min_len":0}]}
```

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
curl "http://127.0.0.1:5555/random" -H "API-KEY: 你的KEY"
curl "http://127.0.0.1:5555/stats"  -H "API-KEY: 你的KEY"
```

- 返回一个 `ip:port` 字符串 = 正常
- 返回 `503` = 池子刚起、还在攒（getter 先抓一轮 1 分钟，tester 再探测，fresh 要 2~4 分钟才涨上来）

> 确认 503 是不是"池子冷启动"：不带 key 参数看 `/stats`，`total` 在涨就是正常。

## 四、公网访问

1. 云安全组放行 `API_PORT`（默认 5555，compose 里改成冷门端口更安静）
2. 服务器防火墙：`ufw allow 5555/tcp`
3. 客户端请求必须带 `API-KEY` 头，否则 403

## 五、更新

```bash
git pull
docker compose up -d --build   # 旧容器替换成新镜像
```

Redis 有 AOF 持久化，池子数据会保留（重新探测会自然淘汰旧记录）。

## 常见问题

- **`/random` 返回 403** → 客户端没带 `API-KEY` 头，或头里值不对
- **`curl 127.0.0.1:5555` 连不上** → `docker compose ps` 看 app 是否重启循环；`docker compose logs app | tail -50` 看报错
- **公网连不上** → 先检查云安全组，再看 `ss -lntp | grep 5555`（应显示监听在 0.0.0.0）
- **fresh 一直是 0 但 total 在涨** → 等 2~4 分钟；超过 10 分钟还是 0 再查 `docker compose logs app` 里的探测报错
