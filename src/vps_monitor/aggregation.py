from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class HourBucket:
    hour_start: int
    in_bytes: float = 0.0
    out_bytes: float = 0.0
    sample_count: int = 0

    @property
    def total_bytes(self) -> float:
        return self.in_bytes + self.out_bytes


def floor_hour(timestamp: int) -> int:
    return int(timestamp) - (int(timestamp) % 3600)


def _sample_time(sample: dict) -> int:
    return int(sample.get("sample_at", sample.get("time", 0)))


def _median_interval(samples: list[dict]) -> int:
    intervals: list[int] = []
    for previous, current in zip(samples, samples[1:]):
        delta = _sample_time(current) - _sample_time(previous)
        if 0 < delta <= 7200:
            intervals.append(delta)
    if not intervals:
        return 1800
    intervals.sort()
    return intervals[len(intervals) // 2]


def aggregate_samples(samples: Iterable[dict]) -> dict[int, HourBucket]:
    """Aggregate bps samples into hourly byte buckets.

    Akile currently returns mixed sampling windows: some servers expose 1800s
    samples and some expose 60s samples. The only safe way to compute traffic is
    to use the actual delta between adjacent sample timestamps.
    """
    unique: dict[int, dict] = {}
    for sample in samples:
        timestamp = _sample_time(sample)
        if timestamp > 0:
            unique[timestamp] = sample

    ordered = [unique[key] for key in sorted(unique)]
    if not ordered:
        return {}

    fallback_interval = _median_interval(ordered)
    buckets: dict[int, HourBucket] = {}

    for index, sample in enumerate(ordered):
        start = _sample_time(sample)
        if index < len(ordered) - 1:
            end = _sample_time(ordered[index + 1])
        else:
            end = start + fallback_interval

        if end <= start or end - start > 7200:
            end = start + fallback_interval

        netin_bps = float(sample.get("netin_bps", sample.get("netin", 0)) or 0)
        netout_bps = float(sample.get("netout_bps", sample.get("netout", 0)) or 0)
        cursor = start

        while cursor < end:
            bucket_start = floor_hour(cursor)
            segment_end = min(end, bucket_start + 3600)
            seconds = segment_end - cursor
            bucket = buckets.setdefault(bucket_start, HourBucket(hour_start=bucket_start))
            bucket.in_bytes += netin_bps * seconds / 8
            bucket.out_bytes += netout_bps * seconds / 8
            bucket.sample_count += 1
            cursor = segment_end

    return buckets
