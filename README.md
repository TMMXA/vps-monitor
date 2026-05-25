# VPS Monitor

本地 Docker 版 Akile VPS 流量监测系统。一个容器内运行 FastAPI、SQLite、定时采集、Telegram 告警和日报截图。

## 功能

- 每 30 分钟采集 `SERVER_IDS` 配置的 Akile VPS
- SQLite 保存 90 天历史数据
- 当前报表页面：`GET /`
- 前端 API：`GET /api/latest`、`GET /api/history?hours=24`
- 手动采集：`POST /api/collect`
- 手动发送日报截图：`POST /api/report`
- Telegram 小时流量告警、剩余流量告警和命令查询
- 每天 `09:00 Asia/Hong_Kong` 自动发送截图日报

## 配置

复制 `docker-compose.example.yml`，填入环境变量：

```yaml
AKILE_CLIENT_ID: "..."
AKILE_SECRET: "..."
TELEGRAM_BOT_TOKEN: "..."
TELEGRAM_CHAT_IDS: "123456789"
# 也兼容 TG_TOKEN / CHAT_ID
ADMIN_TOKEN: "change-me"
```

可选项：

```yaml
SERVER_IDS: "12345,67890"
COLLECT_INTERVAL_MINUTES: "30"
REPORT_TIME: "09:00"
RETENTION_DAYS: "90"
THRESHOLD_12345_GIB_PER_HOUR: "15"
THRESHOLD_67890_GIB_PER_HOUR: "1"
```

如果服务器不能直连 Telegram，可以配置 `TELEGRAM_PROXY`，例如 `http://proxy-host:proxy-port`。这个代理只用于 Telegram，Akile 采集仍然直连。

## 运行

```bash
docker compose up -d --build
```

打开：

```text
http://localhost:8000/
```

手动触发采集：

```bash
curl -X POST http://localhost:8000/api/collect \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

手动发送日报：

```bash
curl -X POST http://localhost:8000/api/report \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Telegram 命令

机器人通过 long polling 接收命令，不需要公网 webhook。

```text
/status  查看两台 VPS 当前状态
/report  生成并发送日报截图
/collect 立刻采集一次 Akile 数据
/history 查看最近 24 小时流量汇总
/health  查看服务健康状态
/help    显示帮助
```

## 数据口径

Akile `GetServerStatistics` 的 `netin/netout` 按 bits/s 处理。小时流量按相邻采样点真实时间差计算：

```text
bytes = bps * interval_seconds / 8
```

不能固定写死采样间隔，因为不同 VPS 可能返回不同粒度的统计点。
