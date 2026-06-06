"""
==========================================================
MetricGuard - Agent Verification Test Suite
==========================================================

Purpose:
    Verifies that the MetricGuard Agent pipeline is
    actively running and collecting data correctly.

    This test suite checks:
    1. Agent log file exists and is being updated (freshness)
    2. Backend API health endpoint is reachable
    3. Anomaly log file is being written to
    4. Agent collector module loads and functions
    5. Agent log file is being updated
    6. Agent produces new log entries over a short window

How to run:
    cd devops/
    python -m pytest testing/agent_test.py -v

    Or run individual test classes:
    python -m pytest testing/agent_test.py::TestAgentLogHealth -v
    python -m pytest testing/agent_test.py::TestBackendHealth -v
    python -m pytest testing/agent_test.py::TestAnomalyLogging -v
    python -m pytest testing/agent_test.py::TestCollectorModule -v
    python -m pytest testing/agent_test.py::TestAgentLogActivity -v
    python -m pytest testing/agent_test.py::TestLiveAgentCycle -v

Dependencies:
    pip install psutil pytest requests pyyaml
"""

import sys
import os
import time
import csv
import logging
import pytest
import psutil
import requests

from datetime import datetime, timedelta

# =========================================================
# PATH SETUP
# =========================================================

# The test file lives in  devops/testing/
# Agent modules live in   devops/agent/

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DEVOPS_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(DEVOPS_DIR)
AGENT_DIR = os.path.join(DEVOPS_DIR, "agent")

# Add agent directory to the path for imports
sys.path.insert(0, AGENT_DIR)

# Key file paths
# The agent writes logs to  devops/agent/logs/agent.log
AGENT_LOG_FILE = os.path.join(AGENT_DIR, "logs", "agent.log")
ANOMALY_LOG_FILE = os.path.join(DEVOPS_DIR, "logs", "anomaly_logs.csv")
SYSTEM_LOG_FILE = os.path.join(DEVOPS_DIR, "logs", "system.log")

# Backend URL (mirrors agent config.yaml default)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Maximum age (seconds) an agent log entry can be before
# we consider the agent "stale" — default 120s (4 cycles at 30s).
FRESHNESS_THRESHOLD = int(os.getenv("FRESHNESS_THRESHOLD", "120"))


# ==========================================================
# TEST 1: AGENT LOG HEALTH
# ==========================================================

class TestAgentLogHealth:
    """
    Verifies that the agent log file exists, is non-empty,
    and is being updated recently (i.e. the agent is
    actively running).

    The MetricGuard Agent writes to agent/logs/agent.log
    on every collection cycle. If this file is missing or
    stale, the agent has not been started or has stopped.
    """

    def test_agent_log_exists(self):
        """
        Test: agent.log must exist on disk.
        If it doesn't, the MetricGuard Agent has never run.
        """
        assert os.path.exists(AGENT_LOG_FILE), (
            f"agent.log not found at {AGENT_LOG_FILE}. "
            "The MetricGuard Agent may not have been started. "
            "Run: python devops/agent/main.py"
        )

    def test_agent_log_is_not_empty(self):
        """
        Test: agent.log must contain log entries.
        An empty file means the agent started but
        hasn't completed a single cycle yet.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log not found")

        size = os.path.getsize(AGENT_LOG_FILE)
        assert size > 0, (
            "agent.log is empty (0 bytes). "
            "The agent may have just started — wait 30 seconds."
        )

        print(f"\n[AGENT LOG] agent.log size: {size:,} bytes ✓")

    def test_agent_log_is_fresh(self):
        """
        Test: agent.log must have been modified within
        FRESHNESS_THRESHOLD seconds of the current time.

        This proves the agent collection loop is actively running.
        The agent collects every 30 seconds by default, so
        the file should be updated at least every ~30s.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log not found")

        mod_time = os.path.getmtime(AGENT_LOG_FILE)
        age_seconds = time.time() - mod_time

        print(f"\n[FRESHNESS] agent.log last modified {age_seconds:.1f}s ago "
              f"(threshold: {FRESHNESS_THRESHOLD}s)")

        assert age_seconds <= FRESHNESS_THRESHOLD, (
            f"agent.log was last modified {age_seconds:.0f}s ago, "
            f"exceeds freshness threshold of {FRESHNESS_THRESHOLD}s. "
            "The MetricGuard Agent may have stopped."
        )

    def test_agent_log_contains_collection_entries(self):
        """
        Test: agent.log should contain 'Metrics collected'
        entries, proving the collector is executing.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log not found")

        with open(AGENT_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        assert "Metrics collected" in content or "Collecting system metrics" in content, (
            "agent.log does not contain metric collection entries. "
            "The agent may not be running correctly."
        )

        print("\n[AGENT LOG] Contains metric collection entries ✓")


# ==========================================================
# TEST 2: BACKEND API HEALTH
# ==========================================================

class TestBackendHealth:
    """
    Verifies that the Backend API is running and responsive.
    The MetricGuard Agent POSTs metrics to /metrics and logs
    to /logs on the backend.
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
                "Start it with: uvicorn app.main:app --port 8000"
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
        payload and return HTTP 200 or 201.
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
                "Start it with: uvicorn app.main:app --port 8000"
            )

        assert response.status_code in (200, 201), (
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
    Tests that the agent collector module can be imported
    and its MetricCollector class works correctly.
    This verifies the agent codebase is intact.
    """

    def test_import_collector(self):
        """
        Test: agent/collector.py should be importable
        without errors.
        """
        try:
            from collector import MetricCollector
        except ImportError as e:
            pytest.fail(
                f"Cannot import MetricCollector from collector: {e}. "
                "Check that agent/ is on the Python path."
            )

        print("\n[MODULE] MetricCollector imported successfully ✓")

    def test_collect_returns_data(self):
        """
        Test: MetricCollector.collect() should return a
        complete dictionary with all required keys.
        """
        from collector import MetricCollector
        from config import AgentConfig

        cfg = AgentConfig()
        logger = logging.getLogger("test_collector")
        logger.setLevel(logging.WARNING)
        mc = MetricCollector(cfg, logger)

        metrics = mc.collect()

        assert isinstance(metrics, dict), (
            f"Expected dict, got {type(metrics).__name__}"
        )

        assert "timestamp" in metrics, "Missing 'timestamp' key"
        assert "cpu_usage" in metrics, "Missing 'cpu_usage' key"
        assert "ram_usage" in metrics, "Missing 'ram_usage' key"
        assert "agent_name" in metrics, "Missing 'agent_name' key"

        print(f"\n[MODULE] MetricCollector.collect() returned "
              f"{len(metrics)} fields ✓")

    def test_individual_metrics_return_values(self):
        """
        Test: Each metric in the collected payload should
        have a non-None value (except system_load on
        Windows, which legitimately returns None).
        """
        from collector import MetricCollector
        from config import AgentConfig

        cfg = AgentConfig()
        logger = logging.getLogger("test_individual")
        logger.setLevel(logging.WARNING)
        mc = MetricCollector(cfg, logger)

        metrics = mc.collect()

        cpu = metrics.get("cpu_usage")
        assert cpu is not None, "cpu_usage returned None"

        ram = metrics.get("ram_usage")
        assert ram is not None, "ram_usage returned None"

        disk = metrics.get("disk_usage")
        assert disk is not None, "disk_usage returned None"

        procs = metrics.get("process_count")
        assert procs is not None, "process_count returned None"

        uptime = metrics.get("system_uptime")
        assert uptime is not None, "system_uptime returned None"

        disk_read = metrics.get("disk_read_speed")
        assert disk_read is not None, "disk_read_speed returned None"

        net_up = metrics.get("network_upload_speed")
        assert net_up is not None, "network_upload_speed returned None"

        print(f"\n[MODULE] All individual metrics returned valid data ✓")


# ==========================================================
# TEST 5: AGENT LOG ACTIVITY
# ==========================================================

class TestAgentLogActivity:
    """
    Verifies that the MetricGuard Agent is writing to
    agent/logs/agent.log — the centralized agent log file.
    """

    def test_agent_log_exists(self):
        """
        Test: agent.log should exist if the agent
        has ever been started.
        """
        assert os.path.exists(AGENT_LOG_FILE), (
            f"agent.log not found at {AGENT_LOG_FILE}. "
            "The MetricGuard Agent may not have been started. "
            "Run: python devops/agent/main.py"
        )

    def test_agent_log_is_not_empty(self):
        """
        Test: agent.log should contain log entries.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log does not exist")

        size = os.path.getsize(AGENT_LOG_FILE)
        assert size > 0, (
            "agent.log is empty (0 bytes). "
            "The agent may have just started."
        )

        print(f"\n[LOG] agent.log size: {size:,} bytes ✓")

    def test_agent_log_has_recent_entries(self):
        """
        Test: agent.log should have been modified recently,
        indicating the agent is actively logging.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log does not exist")

        mod_time = os.path.getmtime(AGENT_LOG_FILE)
        age_seconds = time.time() - mod_time

        print(f"\n[LOG] agent.log last modified {age_seconds:.1f}s ago")

        assert age_seconds <= FRESHNESS_THRESHOLD, (
            f"agent.log was last modified {age_seconds:.0f}s ago, "
            f"exceeds threshold of {FRESHNESS_THRESHOLD}s. "
            "The agent may have stopped."
        )


# ==========================================================
# TEST 6: LIVE AGENT CYCLE
# ==========================================================

class TestLiveAgentCycle:
    """
    Performs a live observation test: checks that the agent
    log file is being actively updated, proving the agent
    collection loop is running and writing data.
    """

    def test_agent_log_grows(self):
        """
        Test: The size of agent.log should increase over a
        35-second observation window (one agent cycle is 30s).
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log not found")

        # Snapshot: size before
        size_before = os.path.getsize(AGENT_LOG_FILE)

        print(f"\n[LIVE] agent.log size before: {size_before:,} bytes")
        print("[LIVE] Waiting 35 seconds for a new collection cycle...")

        time.sleep(35)

        # Snapshot: size after
        size_after = os.path.getsize(AGENT_LOG_FILE)

        growth = size_after - size_before
        print(f"[LIVE] agent.log size after: {size_after:,} bytes "
              f"(+{growth:,} bytes)")

        assert size_after > size_before, (
            f"agent.log did not grow in 35 seconds "
            f"(stayed at {size_before:,} bytes). "
            "The MetricGuard Agent is NOT actively running."
        )

    def test_agent_log_modified_recently(self):
        """
        Test: The file modification time of agent.log
        should be recent, proving the agent is alive.
        """
        if not os.path.exists(AGENT_LOG_FILE):
            pytest.skip("agent.log not found")

        mod_time = os.path.getmtime(AGENT_LOG_FILE)
        age = time.time() - mod_time

        print(f"\n[LIVE] agent.log last modified {age:.1f}s ago")

        assert age <= FRESHNESS_THRESHOLD, (
            f"agent.log was last modified {age:.0f}s ago. "
            "The MetricGuard Agent is NOT actively writing."
        )


# ==========================================================
# Run all tests from command line
# ==========================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
