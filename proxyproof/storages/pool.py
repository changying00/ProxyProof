"""代理池存储层（新）

ZSET 只用来排序，属性全部放 hash。分数按 key（目标）独立。

    pool:keys            SET   key 名
    pool:meta            HASH  proxy -> {exit_ip, anonymous, plain, risk, asn, cc, src, first_seen}
    pool:due:<key>       ZSET  proxy -> next_check_ts        （到期队列，不是全量扫描）
    pool:score:<key>     ZSET  proxy -> score
    pool:fresh:<key>     ZSET  proxy -> last_ok_ts           （新鲜度索引，分发只从这里取）
    pool:stat:<key>      HASH  proxy -> {ok, fail, streak, ewma, lat_ms, last_ok, served}
"""
import json
import random
import time

import redis

from proxyproof.probe import verdict as V
from proxyproof.setting import (
    INTRODUCE_WINDOW,
    PROXY_SCORE_INIT,
    REDIS_CONNECTION_STRING,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    SOURCE_WEIGHTS,
)

POP_LUA = """
local items = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, tonumber(ARGV[2]))
for i = 1, #items do redis.call('ZREM', KEYS[1], items[i]) end
return items
"""


def _dumps(d):
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def _loads(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


class Pool:
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                 db=REDIS_DB, connection_string=REDIS_CONNECTION_STRING, prefix="pool"):
        if connection_string:
            self.db = redis.StrictRedis.from_url(connection_string, decode_responses=True)
        else:
            self.db = redis.StrictRedis(host=host, port=port, password=password, db=db,
                                        decode_responses=True)
        self.p = prefix
        self._pop = self.db.register_script(POP_LUA)
        self._live_at = {}
        self.has_zrandmember = False

    # ---------- keys ----------
    def k_due(self, key): return f"{self.p}:due:{key}"
    def k_score(self, key): return f"{self.p}:score:{key}"
    def k_fresh(self, key): return f"{self.p}:fresh:{key}"
    def k_live(self, key): return f"{self.p}:live:{key}"
    def k_stat(self, key): return f"{self.p}:stat:{key}"
    def k_meta(self): return f"{self.p}:meta"

    def ensure_key(self, key):
        self.db.sadd(f"{self.p}:keys", key)

    def keys(self):
        return sorted(self.db.smembers(f"{self.p}:keys"))

    # ---------- meta ----------
    def meta(self, proxy):
        return _loads(self.db.hget(self.k_meta(), proxy))

    def meta_set(self, proxy, **fields):
        if not fields:
            return
        cur = self.meta(proxy)
        cur.update({k: v for k, v in fields.items() if v is not None})
        self.db.hset(self.k_meta(), proxy, _dumps(cur))

    # ---------- 入池 ----------
    def add(self, proxy, key, src=None, score=None):
        """新代理入池：写 meta + 排到期。

        关键：到期时间要**打散**。若整批都写 now，一次抓 3 万个就会把到期队列
        淹掉，检测器一轮要几十分钟，期间已确认可用的代理排不上队、全部过期。
        按抓取批量摊到一个窗口里，可用代理的 120s 复检才能插到前面。
        """
        self.ensure_key(key)
        if not self.db.hexists(self.k_meta(), proxy):
            self.meta_set(proxy, first_seen=int(time.time()), src=src)
        # 来源加权：好源初始分高（排更前面），坏源首检排得更远
        w = SOURCE_WEIGHTS.get(src, 1.0) if src else 1.0
        init = (PROXY_SCORE_INIT if score is None else score) * w
        self.db.zadd(self.k_score(key), {proxy: round(init, 3)}, nx=True)
        if self.db.zscore(self.k_due(key), proxy) is None:
            window = max(60, int(INTRODUCE_WINDOW / max(w, 0.3)))
            self.db.zadd(self.k_due(key), {proxy: int(time.time()) + random.randint(0, window)})
        return True

    def add_many(self, proxies, key, src=None):
        n = 0
        for p in proxies:
            if self.add(p, key, src):
                n += 1
        return n

    # ---------- 到期队列 ----------
    def k_hot(self, key): return f"{self.p}:hot:{key}"

    def due_pop(self, key, limit=200, now=None):
        """先取"上一轮判定为 OK"的（hot），没有再取普通到期。

        没有这一层，3000 个新代理一入池就把队列堵死，已确认可用的代理
        排在他们后面，还没轮到复检就过了新鲜期，池子直接归零。
        """
        now = int(time.time()) if now is None else now
        hot = self._pop(keys=[self.k_hot(key)], args=[now, limit]) or []
        if hot:
            return hot
        return self._pop(keys=[self.k_due(key)], args=[now, limit]) or []

    def due_size(self, key, now=None):
        now = int(time.time()) if now is None else now
        return (self.db.zcount(self.k_hot(key), "-inf", now)
                + self.db.zcount(self.k_due(key), "-inf", now))

    def reseed(self, key):
        """崩溃恢复：score 集合里有、due 队列里没有的代理，重新排到期"""
        missing = []
        cursor = 0
        while True:
            cursor, members = self.db.zscan(self.k_score(key), cursor, count=1000)
            pairs = members.items() if isinstance(members, dict) else members
            for m, _ in pairs:
                if self.db.zscore(self.k_due(key), m) is None:
                    missing.append(m)
            if cursor == 0:
                break
        if missing:
            now = int(time.time())
            self.db.zadd(self.k_due(key), {m: now for m in missing})
        return len(missing)

    # ---------- 记录观测 ----------
    def record(self, obs, score_weights=None):
        """按四态更新分数/新鲜度/下次检测时间"""
        key, proxy = obs.key, obs.proxy
        self.ensure_key(key)
        stat = _loads(self.db.hget(self.k_stat(key), proxy))

        if obs.verdict == V.OK:
            ok, fail, streak = stat.get("ok", 0) + 1, stat.get("fail", 0), 0
        elif obs.verdict in (V.BLOCKED, V.DEAD):
            ok, fail, streak = stat.get("ok", 0), stat.get("fail", 0) + 1, stat.get("streak", 0) + 1
        else:  # UNKNOWN 不改变分数
            ok, fail, streak = stat.get("ok", 0), stat.get("fail", 0), stat.get("streak", 0)

        ewma = stat.get("ewma", 0.5)
        if obs.verdict in V.SCORING_VERDICTS:
            ewma = 0.7 * ewma + 0.3 * (1.0 if obs.verdict == V.OK else 0.0)

        lat = obs.lat_ms if obs.lat_ms and obs.lat_ms > 0 else stat.get("lat_ms", 3000)
        stat.update({
            "ok": ok, "fail": fail, "streak": streak, "ewma": round(ewma, 4),
            "lat_ms": lat, "last_verdict": obs.verdict, "last_check": obs.ts,
            "served": stat.get("served", 0),
        })
        if obs.verdict == V.OK:
            stat["last_ok"] = obs.ts
        self.db.hset(self.k_stat(key), proxy, _dumps(stat))

        if obs.exit_ip:
            self.meta_set(proxy, exit_ip=obs.exit_ip, anonymous=obs.anonymous,
                          plain=obs.plain_ok)

        meta = self.meta(proxy)
        risk = meta.get("risk")
        lat_factor = max(0.2, 500.0 / (500.0 + float(lat)))
        purity = (1.0 - min(risk, 150) / 150.0) if isinstance(risk, (int, float)) else 0.85
        score = 0.0 if obs.verdict == V.DEAD else 100.0 * ewma * lat_factor * purity
        self.db.zadd(self.k_score(key), {proxy: round(score, 3)})

        if obs.verdict == V.OK and obs.anonymous is not False:
            self.db.zadd(self.k_fresh(key), {proxy: obs.ts})

        if V.should_drop(obs.verdict, streak):
            self.drop(proxy, key)
            return {"dropped": True, "score": 0}

        nxt = int(time.time()) + V.next_check_delay(obs.verdict, streak)
        if obs.verdict == V.OK:
            self.db.zrem(self.k_due(key), proxy)
            self.db.zadd(self.k_hot(key), {proxy: nxt})
        else:
            self.db.zrem(self.k_hot(key), proxy)
            self.db.zadd(self.k_due(key), {proxy: nxt})
        return {"dropped": False, "score": round(score, 2), "next": nxt}

    def drop(self, proxy, key=None):
        keys = [key] if key else self.keys()
        for k in keys:
            self.db.zrem(self.k_score(k), proxy)
            self.db.zrem(self.k_fresh(k), proxy)
            self.db.zrem(self.k_due(k), proxy)
            self.db.zrem(self.k_hot(k), proxy)
            self.db.srem(self.k_live(k), proxy)
            self.db.hdel(self.k_stat(k), proxy)
        self.db.hdel(self.k_meta(), proxy)

    # ---------- 分发 ----------
    def prune_fresh(self, key, max_age, force=False):
        """清理过期新鲜度，并把 fresh 集合同步成 SET（本机 Redis 5.0 没有 ZRANDMEMBER，
        用 SET + SRANDMEMBER 拿到 O(1) 均匀随机）。最多每 5 秒重建一次。"""
        now = int(time.time())
        if not force and now - self._live_at.get(key, 0) < 5:
            return 0
        removed = self.db.zremrangebyscore(self.k_fresh(key), "-inf", now - int(max_age))
        members = self.db.zrange(self.k_fresh(key), 0, -1)
        live = self.k_live(key)
        pipe = self.db.pipeline()
        pipe.delete(live)
        for i in range(0, len(members), 1000):
            pipe.sadd(live, *members[i:i + 1000])
        pipe.execute()
        self._live_at[key] = now
        return removed

    def pick(self, key, count=1, max_age=180, max_risk=None):
        """O(1) 分发：SRANDMEMBER 取候选 → power-of-two-choices 挑分高的 → 校验新鲜度"""
        self.prune_fresh(key, max_age)
        live = self.db.srandmember(self.k_live(key), max(3, count * 2))
        if not live:
            self.prune_fresh(key, max_age, force=True)
            live = self.db.srandmember(self.k_live(key), max(3, count * 2))
        if not live:
            return []
        if isinstance(live, str):
            live = [live]

        cutoff = time.time() - int(max_age)
        pipe = self.db.pipeline()
        for p in live:
            pipe.zscore(self.k_fresh(key), p)
            pipe.zscore(self.k_score(key), p)
        res = pipe.execute()

        scored, stale = [], []
        for i, p in enumerate(live):
            ts, score = res[2 * i], res[2 * i + 1]
            if ts is None or ts < cutoff:
                stale.append(p)
                continue
            if max_risk is not None:
                m = self.meta(p)
                if isinstance(m.get("risk"), (int, float)) and m["risk"] > max_risk:
                    continue
            scored.append((score or 0, p))
        if stale:
            self.db.srem(self.k_live(key), *stale)
        if not scored:
            return []
        scored.sort(reverse=True)
        return [p for _, p in scored[:count]]

    def serve_inc(self, key, proxy):
        stat = _loads(self.db.hget(self.k_stat(key), proxy))
        stat["served"] = stat.get("served", 0) + 1
        stat["last_served"] = int(time.time())
        self.db.hset(self.k_stat(key), proxy, _dumps(stat))

    def report(self, key, proxy, ok):
        """调用方反馈：真实请求失败立即摘出新鲜集合（不等下一轮检测）"""
        stat = _loads(self.db.hget(self.k_stat(key), proxy))
        if ok:
            stat["ok"] = stat.get("ok", 0) + 1
            stat["ewma"] = round(0.7 * stat.get("ewma", 0.5) + 0.3, 4)
            self.db.zadd(self.k_fresh(key), {proxy: int(time.time())})
            # 成功反馈 = 一次免费的真实验证，刷新新鲜度并排进热队列优先复检，
            # 这样高频使用的代理在池子里保持有效（之前这里只改 fresh 不排复检）
            self.db.zadd(self.k_hot(key), {proxy: int(time.time())})
        else:
            stat["fail"] = stat.get("fail", 0) + 1
            stat["ewma"] = round(0.7 * stat.get("ewma", 0.5), 4)
            self.db.zrem(self.k_fresh(key), proxy)
            self.db.srem(self.k_live(key), proxy)
            self.db.zincrby(self.k_score(key), -20, proxy)
            self.db.zadd(self.k_due(key), {proxy: int(time.time())})
        stat["last_check"] = int(time.time())
        self.db.hset(self.k_stat(key), proxy, _dumps(stat))
        return stat

    # ---------- 统计 ----------
    def count(self, key, max_age=None):
        if max_age is None:
            return self.db.zcard(self.k_score(key))
        self.prune_fresh(key, max_age)
        return self.db.zcard(self.k_fresh(key))

    def all(self, key, max_age=None):
        if max_age is None:
            return self.db.zrange(self.k_score(key), 0, -1)
        self.prune_fresh(key, max_age)
        return self.db.zrange(self.k_fresh(key), 0, -1)

    def stats(self, key):
        fresh = self.db.zcard(self.k_fresh(key))
        total = self.db.zcard(self.k_score(key))
        due = self.due_size(key)
        verdicts = {}
        cursor = 0
        while True:
            cursor, items = self.db.hscan(self.k_stat(key), cursor, count=1000)
            pairs = items.items() if isinstance(items, dict) else items
            for _, v in pairs:
                lv = _loads(v).get("last_verdict", "?")
                verdicts[lv] = verdicts.get(lv, 0) + 1
            if cursor == 0:
                break
        return {"key": key, "total": total, "fresh": fresh, "due": due,
                "verdicts": verdicts, "zetrand": self.has_zrandmember}
