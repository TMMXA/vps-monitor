from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from datetime import datetime

from .akile import AkileClient
from .config import GIB, AppConfig
from .formatting import format_datetime, format_gib
from .screenshot import capture_report
from .storage import Storage
from .telegram import TelegramNotifier


class MonitorService:
    def __init__(self, config: AppConfig, storage: Storage):
        self.config = config
        self.storage = storage
        self.akile = AkileClient(config)
        self.telegram = TelegramNotifier(config)
        self._collect_lock = asyncio.Lock()
        self._report_lock = asyncio.Lock()

    async def collect(self) -> dict:
        async with self._collect_lock:
            servers = await self.akile.fetch()
            self.storage.store_collection(servers)
            await self.check_alerts()
            return {"ok": True, "servers": len(servers), "collected_at": int(time.time())}

    async def check_alerts(self) -> None:
        thresholds = self.storage.hourly_thresholds()
        now = int(time.time())
        current_hour = now - (now % 3600)
        remaining_levels = [20, 10, 5]

        with self.storage.connect() as conn:
            for server in conn.execute("SELECT * FROM servers").fetchall():
                akile_id = int(server["akile_id"])
                name = server["display_name"]

                threshold = thresholds.get(akile_id)
                if threshold:
                    rows = conn.execute(
                        """
                        SELECT hour_start, total_bytes
                        FROM hourly_traffic
                        WHERE akile_id = ? AND hour_start >= ?
                        ORDER BY hour_start DESC
                        """,
                        (akile_id, current_hour - 3600),
                    ).fetchall()
                    for row in rows:
                        observed = int(row["total_bytes"] or 0)
                        if observed <= threshold:
                            continue
                        bucket = int(row["hour_start"])
                        if self.storage.alert_exists(conn, akile_id, "hourly_traffic", bucket, "threshold"):
                            continue
                        text = (
                            f"VPS 流量告警\n"
                            f"{name} 当前小时流量 {format_gib(observed)}，"
                            f"超过阈值 {format_gib(threshold)}。\n"
                            f"时间：{format_datetime(bucket, self.config.timezone)}"
                        )
                        if await self.telegram.send_message(text):
                            self.storage.record_alert(conn, akile_id, "hourly_traffic", bucket, "threshold", threshold, observed)

                limit = int(server["traffic_limit_bytes"] or 0)
                remaining = int(server["remaining_traffic_bytes"] or 0)
                reset_bucket = int(server["next_reset_at"] or 0)
                if limit <= 0 or reset_bucket <= 0:
                    continue
                remaining_percent = remaining / limit * 100
                for level in remaining_levels:
                    if remaining_percent > level:
                        continue
                    level_key = str(level)
                    if self.storage.alert_exists(conn, akile_id, "remaining_percent", reset_bucket, level_key):
                        continue
                    text = (
                        f"VPS 剩余流量告警\n"
                        f"{name} 剩余 {format_gib(remaining)}，低于 {level}% 阈值。\n"
                        f"重置时间：{format_datetime(reset_bucket, self.config.timezone)}"
                    )
                    if await self.telegram.send_message(text):
                        self.storage.record_alert(
                            conn,
                            akile_id,
                            "remaining_percent",
                            reset_bucket,
                            level_key,
                            level,
                            remaining_percent,
                        )

    async def send_report(self, chat_ids: Sequence[str] | None = None) -> dict:
        async with self._report_lock:
            image = await capture_report(self.config)
            caption = f"VPS Daily Report {datetime.now(self.config.timezone).strftime('%Y-%m-%d %H:%M')}"
            sent = await self.telegram.send_photo(image, caption, chat_ids=chat_ids)
            return {"ok": sent, "path": str(image)}

    def cleanup(self) -> None:
        self.storage.cleanup(self.config.retention_days)
