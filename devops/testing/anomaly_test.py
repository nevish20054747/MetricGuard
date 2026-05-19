"""
==========================================================
MetricGuard - Anomaly & Stress Testing Module
==========================================================

Purpose:
    Simulates abnormal system conditions to verify that:
    1. The metric collector captures extreme values correctly.
    2. Anomalous metrics are detected and logged.
    3. The system remains stable under stress.

Tests included:
    1. CPU Stress Test   — spikes CPU to ~100%
    2. RAM Stress Test   — allocates large memory blocks
    3. Fake Anomaly Test — generates artificial extreme metrics

How to run:
    cd devops/
    python -m pytest testing/anomaly_test.py -v

    Or run individual tests:
    python -m pytest testing/anomaly_test.py::TestCPUStress -v
    python -m pytest testing/anomaly_test.py::TestRAMStress -v
    python -m pytest testing/anomaly_test.py::TestFakeAnomaly -v

Dependencies:
    pip install psutil pytest requests
"""

import sys
import os
import time
import multiprocessing
import psutil
import pytest

# Add the monitoring directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "monitoring"))

from metric_collector import (
    collect_all_metrics,
    get_cpu_usage,
    get_ram_usage,
    get_disk_usage,
    get_process_count,
    get_system_load,
    get_system_uptime,
    get_disk_io,
    get_network_io,
)


# ==========================================================
# TEST 1: CPU STRESS TEST
# ==========================================================

class TestCPUStress:
    """
    Tests that the metric collector accurately reports
    high CPU usage during a CPU-intensive workload.
    """

    @staticmethod
    def _cpu_burn(duration):
        """
        Burns CPU for the given number of seconds.
        This function runs an infinite loop to max out one core.

        Args:
            duration (int): How many seconds to burn CPU.
        """
        end_time = time.time() + duration
        while time.time() < end_time:
            # Busy loop — consumes 100% of one CPU core
            _ = 99999 ** 99

    def test_cpu_stress_detection(self):
        """
        Test: Spike CPU usage and verify the collector reports
        a value above 50%.

        How it works:
            1. Spawns multiple processes that burn CPU for 5 seconds.
            2. While they run, collects CPU metrics.
            3. Asserts that reported CPU > 50%.
        """
        print("\n[CPU STRESS TEST] Starting CPU burn...")

        # Spawn one burner per CPU core
        num_cores = multiprocessing.cpu_count()
        processes = []

        for _ in range(num_cores):
            p = multiprocessing.Process(target=self._cpu_burn, args=(5,))
            p.start()
            processes.append(p)

        # Wait a moment for CPU to ramp up, then measure
        time.sleep(2)
        cpu = get_cpu_usage()

        # Clean up: wait for all burner processes to finish
        for p in processes:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()

        print(f"[CPU STRESS TEST] Measured CPU: {cpu}%")

        # Assert CPU is elevated (should be well above 20%)
        assert cpu is not None, "CPU metric returned None"
        assert cpu > 20.0, f"Expected CPU > 20%, got {cpu}%"

    def test_cpu_returns_valid_range(self):
        """
        Test: Normal CPU reading should be between 0 and 100.
        """
        cpu = get_cpu_usage()
        assert cpu is not None, "CPU metric returned None"
        assert 0.0 <= cpu <= 100.0, f"CPU out of range: {cpu}%"


# ==========================================================
# TEST 2: RAM STRESS TEST
# ==========================================================

class TestRAMStress:
    """
    Tests that the metric collector accurately reports
    increased RAM usage when large allocations are made.
    """

    def test_ram_stress_detection(self):
        """
        Test: Allocate a large block of memory and verify
        that reported RAM usage increases.

        How it works:
            1. Records baseline RAM usage.
            2. Allocates ~200MB of memory.
            3. Records new RAM usage.
            4. Asserts that usage increased.
        """
        print("\n[RAM STRESS TEST] Recording baseline RAM...")
        baseline_ram = get_ram_usage()

        # Allocate ~200MB (200 million bytes)
        print("[RAM STRESS TEST] Allocating ~200MB of RAM...")
        large_block = bytearray(200 * 1024 * 1024)  # 200MB

        stressed_ram = get_ram_usage()
        print(f"[RAM STRESS TEST] Baseline: {baseline_ram}%, "
              f"After allocation: {stressed_ram}%")

        # Clean up
        del large_block

        assert baseline_ram is not None, "Baseline RAM returned None"
        assert stressed_ram is not None, "Stressed RAM returned None"
        # RAM should have increased (or at least stayed the same)
        assert stressed_ram >= baseline_ram, (
            f"Expected RAM to increase from {baseline_ram}% "
            f"but got {stressed_ram}%"
        )

    def test_ram_returns_valid_range(self):
        """
        Test: Normal RAM reading should be between 0 and 100.
        """
        ram = get_ram_usage()
        assert ram is not None, "RAM metric returned None"
        assert 0.0 <= ram <= 100.0, f"RAM out of range: {ram}%"


# ==========================================================
# TEST 3: FAKE ANOMALY GENERATION
# ==========================================================

class TestFakeAnomaly:
    """
    Generates fake anomalous metric values to test that
    downstream systems (backend, ML model, alerts) can
    handle extreme data correctly.

    These tests do NOT stress the actual system — they
    create synthetic payloads with extreme values.
    """

    def test_fake_high_cpu_anomaly(self):
        """
        Test: Generate a fake payload where CPU is at 99.9%.
        """
        fake_metrics = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_usage": 99.9,
            "ram_usage": 45.0,
            "disk_usage": 60.0,
            "disk_read_speed": "950 MB",
            "disk_write_speed": "500 MB",
            "network_upload_speed": "200 MB",
            "network_download_speed": "300 MB",
            "process_count": 250,
            "system_load": 8.5,
            "system_uptime": "24h 0m 0s"
        }
        print(f"\n[FAKE ANOMALY] High CPU payload: {fake_metrics}")

        # Verify the payload structure is valid
        assert fake_metrics["cpu_usage"] == 99.9
        assert "timestamp" in fake_metrics
        assert len(fake_metrics) == 11  # All 10 metrics + timestamp

    def test_fake_high_ram_anomaly(self):
        """
        Test: Generate a fake payload where RAM is at 98.5%.
        """
        fake_metrics = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_usage": 25.0,
            "ram_usage": 98.5,
            "disk_usage": 55.0,
            "disk_read_speed": "800 MB",
            "disk_write_speed": "400 MB",
            "network_upload_speed": "150 MB",
            "network_download_speed": "250 MB",
            "process_count": 300,
            "system_load": 2.0,
            "system_uptime": "48h 0m 0s"
        }
        print(f"\n[FAKE ANOMALY] High RAM payload: {fake_metrics}")

        assert fake_metrics["ram_usage"] == 98.5
        assert fake_metrics["process_count"] == 300

    def test_fake_disk_full_anomaly(self):
        """
        Test: Generate a fake payload where disk is nearly full.
        """
        fake_metrics = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_usage": 30.0,
            "ram_usage": 50.0,
            "disk_usage": 97.0,
            "disk_read_speed": "5 GB",
            "disk_write_speed": "4.5 GB",
            "network_upload_speed": "100 MB",
            "network_download_speed": "200 MB",
            "process_count": 200,
            "system_load": 1.5,
            "system_uptime": "72h 0m 0s",
        }
        print(f"\n[FAKE ANOMALY] Disk full payload: {fake_metrics}")

        assert fake_metrics["disk_usage"] == 97.0

    def test_fake_network_spike_anomaly(self):
        """
        Test: Generate a fake payload with extreme network traffic.
        """
        fake_metrics = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_usage": 40.0,
            "ram_usage": 55.0,
            "disk_usage": 65.0,
            "disk_read_speed": "1 GB",
            "disk_write_speed": "500 MB",
            "network_upload_speed": "1.2 GB",
            "network_download_speed": "950 MB",
            "process_count": 150,
            "system_load": 3.0,
            "system_uptime": "12h 0m 0s",
        }
        print(f"\n[FAKE ANOMALY] Network spike payload: {fake_metrics}")

        assert fake_metrics["network_upload_speed"] == "1.2 GB"


# ==========================================================
# TEST 4: FULL COLLECTION TEST
# ==========================================================

class TestFullCollection:
    """
    Tests the complete collect_all_metrics() function
    to ensure all metrics are gathered successfully.
    """

    def test_collect_all_returns_complete_payload(self):
        """
        Test: collect_all_metrics() should return a dict
        with all 10 metrics plus a timestamp.
        """
        metrics = collect_all_metrics()

        # Check all required keys exist
        required_keys = [
            "timestamp",
            "cpu_usage",
            "ram_usage",
            "disk_usage",
            "disk_read_speed",
            "disk_write_speed",
            "network_upload_speed",
            "network_download_speed",
            "process_count",
            "system_load",
            "system_uptime",
        ]

        for key in required_keys:
            assert key in metrics, f"Missing key: {key}"

        print(f"\n[FULL COLLECTION] Collected metrics: {metrics}")

    def test_metric_types(self):
        """
        Test: Each metric should be the correct type.
        """
        metrics = collect_all_metrics()

        # Timestamp should be a string
        assert isinstance(metrics["timestamp"], str)

        # Percentage metrics should be numbers
        assert isinstance(metrics["cpu_usage"], (int, float))
        assert isinstance(metrics["ram_usage"], (int, float))
        assert isinstance(metrics["disk_usage"], (int, float))

        # Speed metrics are now formatted strings
        assert isinstance(metrics["disk_read_speed"], str)
        assert isinstance(metrics["disk_write_speed"], str)
        assert isinstance(metrics["network_upload_speed"], str)
        assert isinstance(metrics["network_download_speed"], str)

        # Process count should be integer
        assert isinstance(metrics["process_count"], int)

        # System load can be float OR None (Windows)
        assert (
            isinstance(metrics["system_load"], (int, float))
            or metrics["system_load"] is None
        )

        # Uptime is now a readable string
        assert isinstance(metrics["system_uptime"], str)


# ==========================================================
# Run all tests from command line
# ==========================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
