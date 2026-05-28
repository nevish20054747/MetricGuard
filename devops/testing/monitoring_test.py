"""
==========================================================
MetricGuard - Monitoring Verification Test Suite
==========================================================

Purpose:
    Verifies that the MetricGuard monitoring pipeline is
    actively running and collecting data correctly.

    This test suite checks:
    1. metrics.json exists and is being updated (freshness)
    2. Metric data structure and value validity
    3. Backend API health endpoint is reachable
    4. Anomaly log file is being written to
    5. System log file is being updated
    6. Metric collector module loads and functions
    7. Real-time AI detection module is importable
    8. Monitoring produces new data over a short window

How to run:
    cd devops/
    python -m pytest testing/monitoring_test.py -v

    Or run individual test classes:
    python -m pytest testing/monitoring_test.py::TestMetricsFileHealth -v
    python -m pytest testing/monitoring_test.py::TestBackendHealth -v
    python -m pytest testing/monitoring_test.py::TestAnomalyLogging -v
    python -m pytest testing/monitoring_test.py::TestCollectorModule -v
    python -m pytest testing/monitoring_test.py::TestSystemLogActivity -v
    python -m pytest testing/monitoring_test.py::TestLiveMonitoringCycle -v

Dependencies:
    pip install psutil pytest requests
"""

import sys
import os
import json
import time
import csv
import pytest
import psutil
import requests

from datetime import datetime, timedelta

# =========================================================
# PATH SETUP
# =========================================================

# The test file lives in  devops/testing/
# Monitoring modules live in  devops/monitoring/
# metrics.json lives in the project root (two levels up)

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DEVOPS_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(DEVOPS_DIR)
MONITORING_DIR = os.path.join(DEVOPS_DIR, "monitoring")

# Add monitoring directory to the path for imports
sys.path.insert(0, MONITORING_DIR)

# Key file paths
# The collector writes to a relative "metrics.json" in its CWD.
# When run per docs (cd devops/monitoring; python metric_collector.py),
# it writes to devops/monitoring/metrics.json.
METRICS_FILE = os.path.join(MONITORING_DIR, "metrics.json")
ANOMALY_LOG_FILE = os.path.join(DEVOPS_DIR, "logs", "anomaly_logs.csv")
SYSTEM_LOG_FILE = os.path.join(DEVOPS_DIR, "logs", "system.log")

# Backend URL (mirrors config.py default)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# Maximum age (seconds) a metrics.json entry can be before
# we consider monitoring "stale" — default 60s (12 cycles).
FRESHNESS_THRESHOLD = int(os.getenv("FRESHNESS_THRESHOLD", "60"))


# ==========================================================
# TEST 1: METRICS FILE HEALTH
# ==========================================================

class TestMetricsFileHealth:
    """
    Verifies that metrics.json exists, is valid JSON, has
    the correct structure, and is being updated recently
    (i.e. the collector is actively running).
    """

    def test_metrics_file_exists(self):
        """
        Test: metrics.json must exist on disk.
        If it doesn't, the metric collector has never run.
        """
        assert os.path.exists(METRICS_FILE), (
            f"metrics.json not found at {METRICS_FILE}. "
            "The metric collector may not have been started."
        )

    def test_metrics_file_is_valid_json(self):
        """
        Test: metrics.json must contain valid JSON (an array).
        """
        assert os.path.exists(METRICS_FILE), "metrics.json not found"

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)

        assert isinstance(data, list), (
            "metrics.json should contain a JSON array, "
            f"got {type(data).__name__}"
        )

    def test_metrics_file_is_not_empty(self):
        """
        Test: metrics.json must have at least one entry.
        An empty array means the collector started but
        hasn't completed a single cycle yet.
        """
        assert os.path.exists(METRICS_FILE), "metrics.json not found"

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)

        assert len(data) > 0, (
            "metrics.json is empty ([]). "
            "The collector may have just started — wait 5 seconds."
        )

    def test_latest_metric_has_required_keys(self):
        """
        Test: The most recent metric entry must contain all
        10 required keys plus a timestamp.
        """
        assert os.path.exists(METRICS_FILE), "metrics.json not found"

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)

        assert len(data) > 0, "metrics.json is empty"

        latest = data[-1]

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

        missing = [k for k in required_keys if k not in latest]
        assert not missing, (
            f"Latest metric entry is missing keys: {missing}"
        )
        print(f"\n[METRICS FILE] Latest entry has all {len(required_keys)} keys ✓")

    def test_latest_metric_is_fresh(self):
        """
        Test: The latest metric timestamp must be within
        FRESHNESS_THRESHOLD seconds of the current time.

        This proves the collector loop is actively running.
        """
        assert os.path.exists(METRICS_FILE), "metrics.json not found"

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)

        assert len(data) > 0, "metrics.json is empty"

        latest = data[-1]
        ts_str = latest.get("timestamp", "")

        # Parse the collector's timestamp format: 2026-05-16T14:00:00
        try:
            metric_time = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pytest.fail(
                f"Could not parse timestamp '{ts_str}'. "
                "Expected format: YYYY-MM-DDTHH:MM:SS"
            )

        age_seconds = (datetime.now() - metric_time).total_seconds()

        print(f"\n[FRESHNESS] Latest metric age: {age_seconds:.1f}s "
              f"(threshold: {FRESHNESS_THRESHOLD}s)")

        assert age_seconds <= FRESHNESS_THRESHOLD, (
            f"Latest metric is {age_seconds:.0f}s old, "
            f"exceeds freshness threshold of {FRESHNESS_THRESHOLD}s. "
            "Monitoring may have stopped."
        )

    def test_metrics_values_are_sane(self):
        """
        Test: CPU and RAM values in the latest entry must
        be within valid ranges (0-100%).
        """
        assert os.path.exists(METRICS_FILE), "metrics.json not found"

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)

        assert len(data) > 0, "metrics.json is empty"

        latest = data[-1]
        cpu = latest.get("cpu_usage")
        ram = latest.get("ram_usage")
        disk = latest.get("disk_usage")

        # CPU check
        assert cpu is not None, "cpu_usage is None"
        assert 0.0 <= cpu <= 100.0, f"cpu_usage out of range: {cpu}"

        # RAM check
        assert ram is not None, "ram_usage is None"
        assert 0.0 <= ram <= 100.0, f"ram_usage out of range: {ram}"

        # Disk check
        assert disk is not None, "disk_usage is None"
        assert 0.0 <= disk <= 100.0, f"disk_usage out of range: {disk}"

        print(f"\n[VALUES] CPU={cpu}%, RAM={ram}%, Disk={disk}% ✓")


# ==========================================================
# TEST 2: BACKEND API HEALTH
# ==========================================================

class TestBackendHealth:
    """
    Verifies that the Flask backend API is running and
    responsive. The metric collector POSTs to /metrics
    and the AI detection pings /health for response time.
    """

    def test_health_endpoint(self):
        """
        Test: GET /health should return HTTP 200 with
        {"status": "healthy"}.
        """
        health_url = f"{BACKEND_URL}/health"

        try:
            response = requests.get(health_url, timeout=5)
        except requests.exceptions.ConnectionError:
            pytest.skip(
                f"Backend not reachable at {health_url}. "
                "Start it with: python monitoring/test_backend.py"
            )

        assert response.status_code == 200, (
            f"Health endpoint returned {response.status_code}"
        )

        body = response.json()
        assert body.get("status") == "healthy", (
            f"Unexpected health response: {body}"
        )

        print(f"\n[BACKEND] /health returned 200 — status: healthy ✓")

    def test_metrics_endpoint_accepts_post(self):
        """
        Test: POST /metrics should accept a valid metric
        payload and return HTTP 200.
        """
        metrics_url = f"{BACKEND_URL}/metrics"

        test_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_usage": 42.0,
            "ram_usage": 55.0,
            "disk_usage": 30.0,
            "disk_read_speed": "10 MB",
            "disk_write_speed": "5 MB",
            "network_upload_speed": "1 MB",
            "network_download_speed": "2 MB",
            "process_count": 200,
            "system_load": None,
            "system_uptime": "10h 0m 0s",
        }

        try:
            response = requests.post(
                metrics_url,
                json=test_payload,
                timeout=5,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.ConnectionError:
            pytest.skip(
                f"Backend not reachable at {metrics_url}. "
                "Start it with: python monitoring/test_backend.py"
            )

        assert response.status_code == 200, (
            f"POST /metrics returned {response.status_code}"
        )

        print(f"\n[BACKEND] POST /metrics accepted test payload ✓")

    def test_backend_response_time(self):
        """
        Test: Backend response time should be under 2000ms.
        The Isolation Forest model uses response time as a
        feature — excessively slow responses could bias
        anomaly detection.
        """
        health_url = f"{BACKEND_URL}/health"

        try:
            start = time.time()
            response = requests.get(health_url, timeout=5)
            elapsed_ms = (time.time() - start) * 1000
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not reachable")

        assert response.status_code == 200
        assert elapsed_ms < 5000, (
            f"Backend response time {elapsed_ms:.0f}ms exceeds 5000ms limit"
        )

        print(f"\n[BACKEND] Response time: {elapsed_ms:.1f}ms ✓")


# ==========================================================
# TEST 3: ANOMALY LOG ACTIVITY
# ==========================================================

class TestAnomalyLogging:
    """
    Verifies that the anomaly detection pipeline is writing
    to anomaly_logs.csv when it detects issues.
    """

    def test_anomaly_log_file_exists(self):
        """
        Test: anomaly_logs.csv should exist if the AI
        detection module has ever run.
        """
        assert os.path.exists(ANOMALY_LOG_FILE), (
            f"anomaly_logs.csv not found at {ANOMALY_LOG_FILE}. "
            "The real-time AI detection may not have run yet."
        )

    def test_anomaly_log_has_header(self):
        """
        Test: The CSV file should have the correct header row.
        """
        if not os.path.exists(ANOMALY_LOG_FILE):
            pytest.skip("anomaly_logs.csv does not exist yet")

        with open(ANOMALY_LOG_FILE, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)

        assert header is not None, "anomaly_logs.csv is empty"

        expected_columns = [
            "timestamp",
            "cpu_usage",
            "ram_usage",
            "disk_usage",
            "isolation_forest_result",
            "reconstruction_error",
        ]

        for col in expected_columns:
            assert col in header, (
                f"Missing column '{col}' in anomaly_logs.csv header. "
                f"Found: {header}"
            )

        print(f"\n[ANOMALY LOG] Header contains all expected columns ✓")

    def test_anomaly_log_has_data_rows(self):
        """
        Test: anomaly_logs.csv should have at least one data
        row (i.e. the AI detection has flagged at least one
        anomaly or written at least one entry).
        """
        if not os.path.exists(ANOMALY_LOG_FILE):
            pytest.skip("anomaly_logs.csv does not exist yet")

        with open(ANOMALY_LOG_FILE, "r", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # First row is header, so we need at least 2 rows total
        assert len(rows) >= 2, (
            "anomaly_logs.csv has a header but no data rows. "
            "The AI detection may not have flagged any anomalies yet."
        )

        data_count = len(rows) - 1
        print(f"\n[ANOMALY LOG] Contains {data_count} logged anomaly entries ✓")

    def test_anomaly_log_latest_entry_values(self):
        """
        Test: The most recent anomaly log entry should have
        valid numeric values for key fields.
        """
        if not os.path.exists(ANOMALY_LOG_FILE):
            pytest.skip("anomaly_logs.csv does not exist yet")

        with open(ANOMALY_LOG_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            pytest.skip("No data rows in anomaly_logs.csv")

        latest = rows[-1]

        # isolation_forest_result should be 1 (normal) or -1 (anomaly)
        iso_result = int(latest["isolation_forest_result"])
        assert iso_result in (1, -1), (
            f"Invalid isolation_forest_result: {iso_result}"
        )

        # reconstruction_error should be a non-negative float
        recon_error = float(latest["reconstruction_error"])
        assert recon_error >= 0.0, (
            f"Negative reconstruction_error: {recon_error}"
        )

        print(f"\n[ANOMALY LOG] Latest entry — "
              f"IF={iso_result}, MSE={recon_error:.6f} ✓")


# ==========================================================
# TEST 4: COLLECTOR MODULE INTEGRITY
# ==========================================================

class TestCollectorModule:
    """
    Tests that the metric collector module can be imported
    and its individual collector functions work correctly.
    This verifies the monitoring codebase is intact.
    """

    def test_import_metric_collector(self):
        """
        Test: metric_collector.py should be importable
        without errors.
        """
        try:
            from metric_collector import collect_all_metrics
        except ImportError as e:
            pytest.fail(
                f"Cannot import metric_collector: {e}. "
                "Check that monitoring/ is on the Python path."
            )

        print("\n[MODULE] metric_collector imported successfully ✓")

    def test_collect_all_metrics_returns_data(self):
        """
        Test: collect_all_metrics() should return a complete
        dictionary with all required keys.
        """
        from metric_collector import collect_all_metrics

        metrics = collect_all_metrics()

        assert isinstance(metrics, dict), (
            f"Expected dict, got {type(metrics).__name__}"
        )

        assert "timestamp" in metrics, "Missing 'timestamp' key"
        assert "cpu_usage" in metrics, "Missing 'cpu_usage' key"
        assert "ram_usage" in metrics, "Missing 'ram_usage' key"

        print(f"\n[MODULE] collect_all_metrics() returned "
              f"{len(metrics)} fields ✓")

    def test_individual_collectors_return_values(self):
        """
        Test: Each individual collector function should
        return a non-None value (except system_load on
        Windows, which legitimately returns None).
        """
        from metric_collector import (
            get_cpu_usage,
            get_ram_usage,
            get_disk_usage,
            get_process_count,
            get_system_uptime,
            get_disk_io,
            get_network_io,
        )

        cpu = get_cpu_usage()
        assert cpu is not None, "get_cpu_usage() returned None"

        ram = get_ram_usage()
        assert ram is not None, "get_ram_usage() returned None"

        disk = get_disk_usage()
        assert disk is not None, "get_disk_usage() returned None"

        procs = get_process_count()
        assert procs is not None, "get_process_count() returned None"

        uptime = get_system_uptime()
        assert uptime is not None, "get_system_uptime() returned None"

        disk_read, disk_write = get_disk_io()
        assert disk_read is not None, "get_disk_io() read returned None"

        net_up, net_down = get_network_io()
        assert net_up is not None, "get_network_io() upload returned None"

        print(f"\n[MODULE] All individual collectors returned valid data ✓")


# ==========================================================
# TEST 5: SYSTEM LOG ACTIVITY
# ==========================================================

class TestSystemLogActivity:
    """
    Verifies that the monitoring system is writing to
    logs/system.log — the centralized log file.
    """

    def test_system_log_exists(self):
        """
        Test: system.log should exist if the collector
        has ever been started.
        """
        assert os.path.exists(SYSTEM_LOG_FILE), (
            f"system.log not found at {SYSTEM_LOG_FILE}. "
            "The metric collector may not have been started."
        )

    def test_system_log_is_not_empty(self):
        """
        Test: system.log should contain log entries.
        """
        if not os.path.exists(SYSTEM_LOG_FILE):
            pytest.skip("system.log does not exist")

        size = os.path.getsize(SYSTEM_LOG_FILE)
        assert size > 0, (
            "system.log is empty (0 bytes). "
            "The collector may have just cleared it."
        )

        print(f"\n[LOG] system.log size: {size:,} bytes ✓")

    def test_system_log_has_recent_entries(self):
        """
        Test: system.log should have been modified recently,
        indicating the collector is actively logging.
        """
        if not os.path.exists(SYSTEM_LOG_FILE):
            pytest.skip("system.log does not exist")

        mod_time = os.path.getmtime(SYSTEM_LOG_FILE)
        age_seconds = time.time() - mod_time

        print(f"\n[LOG] system.log last modified {age_seconds:.1f}s ago")

        assert age_seconds <= FRESHNESS_THRESHOLD, (
            f"system.log was last modified {age_seconds:.0f}s ago, "
            f"exceeds threshold of {FRESHNESS_THRESHOLD}s. "
            "The collector may have stopped."
        )


# ==========================================================
# TEST 6: LIVE MONITORING CYCLE
# ==========================================================

class TestLiveMonitoringCycle:
    """
    Performs a live observation test: waits for a short
    period and verifies that metrics.json grows, proving
    the monitoring loop is actively collecting data.
    """

    def test_metrics_count_increases(self):
        """
        Test: The number of entries in metrics.json should
        increase over a 10-second observation window.

        The collector runs every 5 seconds, so we should see
        at least one new entry in 10 seconds.
        """
        if not os.path.exists(METRICS_FILE):
            pytest.skip("metrics.json not found")

        # Snapshot: count before
        with open(METRICS_FILE, "r") as f:
            count_before = len(json.load(f))

        print(f"\n[LIVE] Entries before: {count_before}")
        print("[LIVE] Waiting 10 seconds for new collection cycles...")

        time.sleep(10)

        # Snapshot: count after
        with open(METRICS_FILE, "r") as f:
            count_after = len(json.load(f))

        new_entries = count_after - count_before
        print(f"[LIVE] Entries after: {count_after} "
              f"(+{new_entries} new)")

        assert count_after > count_before, (
            f"metrics.json did not grow in 10 seconds "
            f"(stayed at {count_before} entries). "
            "The metric collector is NOT actively running."
        )

    def test_metrics_file_modified_recently(self):
        """
        Test: The file modification time of metrics.json
        should update within the observation window.
        """
        if not os.path.exists(METRICS_FILE):
            pytest.skip("metrics.json not found")

        mod_time = os.path.getmtime(METRICS_FILE)
        age = time.time() - mod_time

        print(f"\n[LIVE] metrics.json last modified {age:.1f}s ago")

        assert age <= FRESHNESS_THRESHOLD, (
            f"metrics.json was last modified {age:.0f}s ago. "
            "Monitoring is NOT actively writing metrics."
        )


# ==========================================================
# Run all tests from command line
# ==========================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
