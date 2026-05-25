import unittest

from vps_monitor.aggregation import aggregate_samples


class AggregationTests(unittest.TestCase):
    def test_uses_1800_second_intervals(self):
        samples = [
            {"sample_at": 3600, "netin_bps": 8 * 1024, "netout_bps": 8 * 1024},
            {"sample_at": 5400, "netin_bps": 8 * 1024, "netout_bps": 8 * 1024},
        ]

        buckets = aggregate_samples(samples)

        self.assertEqual(len(buckets), 1)
        bucket = buckets[3600]
        self.assertEqual(bucket.in_bytes, 1024 * 3600)
        self.assertEqual(bucket.out_bytes, 1024 * 3600)

    def test_uses_60_second_intervals(self):
        samples = [
            {"sample_at": 3600, "netin_bps": 8 * 1024, "netout_bps": 0},
            {"sample_at": 3660, "netin_bps": 8 * 1024, "netout_bps": 0},
            {"sample_at": 3720, "netin_bps": 8 * 1024, "netout_bps": 0},
        ]

        buckets = aggregate_samples(samples)

        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[3600].in_bytes, 1024 * 180)

    def test_splits_intervals_across_hours(self):
        samples = [
            {"sample_at": 3500, "netin_bps": 8 * 100, "netout_bps": 0},
            {"sample_at": 3700, "netin_bps": 8 * 100, "netout_bps": 0},
        ]

        buckets = aggregate_samples(samples)

        self.assertEqual(buckets[0].in_bytes, 100 * 100)
        self.assertEqual(buckets[3600].in_bytes, 100 * 300)

    def test_deduplicates_same_sample_timestamp(self):
        samples = [
            {"sample_at": 3600, "netin_bps": 8 * 100, "netout_bps": 0},
            {"sample_at": 3600, "netin_bps": 8 * 200, "netout_bps": 0},
            {"sample_at": 3660, "netin_bps": 8 * 100, "netout_bps": 0},
        ]

        buckets = aggregate_samples(samples)

        self.assertEqual(buckets[3600].in_bytes, 200 * 60 + 100 * 60)


if __name__ == "__main__":
    unittest.main()
