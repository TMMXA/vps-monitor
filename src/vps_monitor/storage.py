from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from .aggregation import aggregate_samples
from .formatting import (
    GIB,
    flag_for_area,
    format_datetime,
    format_gib,
    format_percent,
    format_uptime,
    hour_label,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS servers (
  akile_id INTEGER PRIMARY KEY,
  server_id TEXT,
  display_name TEXT NOT NULL,
  area_name TEXT,
  node_name TEXT,
  plan_name TEXT,
  system_name TEXT,
  status_text TEXT,
  state TEXT,
  cpu_cores INTEGER,
  memory_bytes INTEGER,
  disk_bytes INTEGER,
  rate_mbps INTEGER,
  traffic_limit_bytes INTEGER,
  used_traffic_bytes INTEGER,
  remaining_traffic_bytes INTEGER,
  due_at INTEGER,
  next_reset_at INTEGER,
  uptime_seconds INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS server_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  akile_id INTEGER NOT NULL,
  collected_at INTEGER NOT NULL,
  state TEXT,
  cpu_used REAL,
  memory_total_bytes INTEGER,
  memory_used_bytes INTEGER,
  netin_total_bytes INTEGER,
  netout_total_bytes INTEGER,
  disk_read_total_bytes INTEGER,
  disk_write_total_bytes INTEGER,
  used_traffic_bytes INTEGER,
  remaining_traffic_bytes INTEGER
);

CREATE INDEX IF NOT EXISTS idx_server_snapshots_server_time
  ON server_snapshots (akile_id, collected_at);

CREATE TABLE IF NOT EXISTS traffic_samples (
  akile_id INTEGER NOT NULL,
  sample_at INTEGER NOT NULL,
  netin_bps REAL NOT NULL DEFAULT 0,
  netout_bps REAL NOT NULL DEFAULT 0,
  cpu REAL,
  memory_used_bytes REAL,
  disk_read REAL,
  disk_write REAL,
  PRIMARY KEY (akile_id, sample_at)
);

CREATE TABLE IF NOT EXISTS hourly_traffic (
  akile_id INTEGER NOT NULL,
  hour_start INTEGER NOT NULL,
  in_bytes INTEGER NOT NULL DEFAULT 0,
  out_bytes INTEGER NOT NULL DEFAULT 0,
  total_bytes INTEGER NOT NULL DEFAULT 0,
  sample_count INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (akile_id, hour_start)
);

CREATE TABLE IF NOT EXISTS alerts (
  akile_id INTEGER NOT NULL,
  alert_type TEXT NOT NULL,
  bucket_start INTEGER NOT NULL,
  level TEXT NOT NULL,
  threshold_value REAL,
  observed_value REAL,
  sent_at INTEGER NOT NULL,
  PRIMARY KEY (akile_id, alert_type, bucket_start, level)
);

CREATE TABLE IF NOT EXISTS server_alert_config (
  akile_id INTEGER PRIMARY KEY,
  hourly_threshold_bytes INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1
);
"""


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self, thresholds: dict[int, int]) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for akile_id, threshold in thresholds.items():
                conn.execute(
                    """
                    INSERT INTO server_alert_config (akile_id, hourly_threshold_bytes, enabled)
                    VALUES (?, ?, 1)
                    ON CONFLICT(akile_id) DO UPDATE SET
                      hourly_threshold_bytes = excluded.hourly_threshold_bytes
                    """,
                    (akile_id, threshold),
                )

    def store_server(self, conn: sqlite3.Connection, server: dict) -> None:
        conn.execute(
            """
            INSERT INTO servers (
              akile_id, server_id, display_name, area_name, node_name, plan_name,
              system_name, status_text, state, cpu_cores, memory_bytes, disk_bytes,
              rate_mbps, traffic_limit_bytes, used_traffic_bytes,
              remaining_traffic_bytes, due_at, next_reset_at, uptime_seconds, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(akile_id) DO UPDATE SET
              server_id = excluded.server_id,
              display_name = excluded.display_name,
              area_name = excluded.area_name,
              node_name = excluded.node_name,
              plan_name = excluded.plan_name,
              system_name = excluded.system_name,
              status_text = excluded.status_text,
              state = excluded.state,
              cpu_cores = excluded.cpu_cores,
              memory_bytes = excluded.memory_bytes,
              disk_bytes = excluded.disk_bytes,
              rate_mbps = excluded.rate_mbps,
              traffic_limit_bytes = excluded.traffic_limit_bytes,
              used_traffic_bytes = excluded.used_traffic_bytes,
              remaining_traffic_bytes = excluded.remaining_traffic_bytes,
              due_at = excluded.due_at,
              next_reset_at = excluded.next_reset_at,
              uptime_seconds = excluded.uptime_seconds,
              updated_at = excluded.updated_at
            """,
            (
                server["id"],
                server.get("server_id"),
                server["display_name"],
                server.get("area_name"),
                server.get("node_name"),
                server.get("plan_name"),
                server.get("system_name"),
                server.get("status_text"),
                server.get("state"),
                server.get("cpu_cores"),
                server.get("memory_bytes"),
                server.get("disk_bytes"),
                server.get("rate_mbps"),
                server.get("traffic_limit_bytes"),
                server.get("used_traffic_bytes"),
                server.get("remaining_traffic_bytes"),
                server.get("due_at"),
                server.get("next_reset_at"),
                server.get("uptime_seconds"),
                server["updated_at"],
            ),
        )

    def store_snapshot(self, conn: sqlite3.Connection, server: dict) -> None:
        realtime = server.get("realtime", {})
        conn.execute(
            """
            INSERT INTO server_snapshots (
              akile_id, collected_at, state, cpu_used, memory_total_bytes,
              memory_used_bytes, netin_total_bytes, netout_total_bytes,
              disk_read_total_bytes, disk_write_total_bytes,
              used_traffic_bytes, remaining_traffic_bytes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                server["id"],
                server["updated_at"],
                server.get("state"),
                realtime.get("cpu_used"),
                realtime.get("memory_total_bytes"),
                realtime.get("memory_used_bytes"),
                realtime.get("netin_total_bytes"),
                realtime.get("netout_total_bytes"),
                realtime.get("disk_read_total_bytes"),
                realtime.get("disk_write_total_bytes"),
                server.get("used_traffic_bytes"),
                server.get("remaining_traffic_bytes"),
            ),
        )

    def upsert_samples(self, conn: sqlite3.Connection, server: dict) -> None:
        rows = []
        for sample in server.get("samples", []):
            rows.append(
                (
                    server["id"],
                    int(sample["sample_at"]),
                    float(sample.get("netin_bps") or 0),
                    float(sample.get("netout_bps") or 0),
                    sample.get("cpu"),
                    sample.get("memory_used_bytes"),
                    sample.get("disk_read"),
                    sample.get("disk_write"),
                )
            )
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO traffic_samples (
              akile_id, sample_at, netin_bps, netout_bps, cpu,
              memory_used_bytes, disk_read, disk_write
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(akile_id, sample_at) DO UPDATE SET
              netin_bps = excluded.netin_bps,
              netout_bps = excluded.netout_bps,
              cpu = excluded.cpu,
              memory_used_bytes = excluded.memory_used_bytes,
              disk_read = excluded.disk_read,
              disk_write = excluded.disk_write
            """,
            rows,
        )

    def recompute_hourly(self, conn: sqlite3.Connection, akile_id: int) -> None:
        samples = [
            dict(row)
            for row in conn.execute(
                """
                SELECT sample_at, netin_bps, netout_bps, cpu, memory_used_bytes, disk_read, disk_write
                FROM traffic_samples
                WHERE akile_id = ?
                ORDER BY sample_at
                """,
                (akile_id,),
            )
        ]
        buckets = aggregate_samples(samples)
        now = int(time.time())
        conn.execute("DELETE FROM hourly_traffic WHERE akile_id = ?", (akile_id,))
        conn.executemany(
            """
            INSERT INTO hourly_traffic (
              akile_id, hour_start, in_bytes, out_bytes, total_bytes, sample_count, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    akile_id,
                    bucket.hour_start,
                    int(bucket.in_bytes),
                    int(bucket.out_bytes),
                    int(bucket.total_bytes),
                    bucket.sample_count,
                    now,
                )
                for bucket in buckets.values()
            ],
        )

    def store_collection(self, servers: list[dict]) -> None:
        with self.connect() as conn:
            for server in servers:
                self.store_server(conn, server)
                self.store_snapshot(conn, server)
                self.upsert_samples(conn, server)
                self.recompute_hourly(conn, server["id"])

    def latest_servers(self, server_ids: list[int], tz: ZoneInfo) -> list[dict]:
        with self.connect() as conn:
            placeholders = ",".join("?" for _ in server_ids)
            rows = conn.execute(
                f"SELECT * FROM servers WHERE akile_id IN ({placeholders})",
                server_ids,
            ).fetchall()
        by_id = {int(row["akile_id"]): row for row in rows}
        response: list[dict] = []
        for index, akile_id in enumerate(server_ids, start=1):
            row = by_id.get(akile_id)
            if row is None:
                continue
            limit = row["traffic_limit_bytes"] or 0
            used = row["used_traffic_bytes"] or 0
            remaining = row["remaining_traffic_bytes"] or max(0, limit - used)
            used_ratio = (used / limit * 100) if limit else 0
            flag = flag_for_area(row["area_name"], row["node_name"])
            response.append(
                {
                    "akileId": akile_id,
                    "index": index,
                    "flag": flag["flag"],
                    "flagLabel": flag["flagLabel"],
                    "flagSrc": flag["flagSrc"],
                    "name": row["display_name"],
                    "node": f"{row['area_name'] or '-'} / {row['node_name'] or '-'}",
                    "status": "Running" if row["state"] == "running" else (row["status_text"] or row["state"] or "-"),
                    "remaining": format_gib(remaining),
                    "used": format_gib(used),
                    "total": format_gib(limit),
                    "usedRatio": round(used_ratio, 2),
                    "usedPercent": format_percent(used_ratio),
                    "forecast": self.forecast_text(akile_id, remaining, tz),
                    "resetAt": format_datetime(row["next_reset_at"], tz),
                    "expiresAt": format_datetime(row["due_at"], tz),
                    "uptime": format_uptime(row["uptime_seconds"]),
                    "updatedAt": format_datetime(row["updated_at"], tz),
                }
            )
        return response

    def forecast_text(self, akile_id: int, remaining_bytes: int, tz: ZoneInfo) -> str:
        hourly = self.history(akile_id, 24, tz)
        daily_gib = sum(item["in"] + item["out"] for item in hourly)
        if daily_gib < 0.1:
            return "消耗过低"
        days = (remaining_bytes / GIB) / daily_gib
        return f"约 {days:.1f} 天"

    def history(self, akile_id: int, hours: int, tz: ZoneInfo) -> list[dict]:
        now = int(time.time())
        current_hour = now - (now % 3600)
        start = current_hour - (hours - 1) * 3600
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT hour_start, in_bytes, out_bytes
                FROM hourly_traffic
                WHERE akile_id = ? AND hour_start >= ? AND hour_start <= ?
                ORDER BY hour_start
                """,
                (akile_id, start, current_hour),
            ).fetchall()
        by_hour = {int(row["hour_start"]): row for row in rows}
        result = []
        for hour_start in range(start, current_hour + 1, 3600):
            row = by_hour.get(hour_start)
            result.append(
                {
                    "h": hour_label(hour_start, tz),
                    "in": round((row["in_bytes"] if row else 0) / GIB, 3),
                    "out": round((row["out_bytes"] if row else 0) / GIB, 3),
                }
            )
        return result

    def latest_snapshot_time(self) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(collected_at) AS value FROM server_snapshots").fetchone()
        return int(row["value"]) if row and row["value"] is not None else None

    def alert_exists(self, conn: sqlite3.Connection, akile_id: int, alert_type: str, bucket_start: int, level: str) -> bool:
        row = conn.execute(
            """
            SELECT 1 FROM alerts
            WHERE akile_id = ? AND alert_type = ? AND bucket_start = ? AND level = ?
            """,
            (akile_id, alert_type, bucket_start, level),
        ).fetchone()
        return row is not None

    def record_alert(
        self,
        conn: sqlite3.Connection,
        akile_id: int,
        alert_type: str,
        bucket_start: int,
        level: str,
        threshold_value: float,
        observed_value: float,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO alerts (
              akile_id, alert_type, bucket_start, level, threshold_value, observed_value, sent_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (akile_id, alert_type, bucket_start, level, threshold_value, observed_value, int(time.time())),
        )

    def hourly_thresholds(self) -> dict[int, int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT akile_id, hourly_threshold_bytes FROM server_alert_config WHERE enabled = 1"
            ).fetchall()
        return {int(row["akile_id"]): int(row["hourly_threshold_bytes"]) for row in rows}

    def cleanup(self, retention_days: int) -> None:
        cutoff = int(time.time()) - retention_days * 86400
        with self.connect() as conn:
            conn.execute("DELETE FROM server_snapshots WHERE collected_at < ?", (cutoff,))
            conn.execute("DELETE FROM traffic_samples WHERE sample_at < ?", (cutoff,))
            conn.execute("DELETE FROM hourly_traffic WHERE hour_start < ?", (cutoff - (cutoff % 3600),))
            conn.execute("DELETE FROM alerts WHERE sent_at < ?", (cutoff,))
