"""
==========================================================
MetricGuard - Phase 5 Root Cause Analysis Test Suite
==========================================================

Purpose:
    Verifies the RCA pipeline end-to-end:
    1. Speed-string parser handles all unit formats.
    2. Feature extraction produces 9-element vectors.
    3. Autoencoder loads and performs inference.
    4. RCA logic correctly maps feature errors to categories.
    5. Backend API endpoints accept and return RCA events.

Legacy Compatibility Note:
    This test suite imports from monitoring/realtime_ai_detection.py
    and monitoring/test_backend.py.  These ML/RCA functions have NOT
    been ported to the agent/ architecture yet and remain in
    monitoring/ as the sole source for AI inference and RCA logic.
    This is an intentional legacy compatibility dependency.

How to run:
    cd devops/
    python -m pytest testing/rca_test.py -v

    Or run individual test classes:
    python -m pytest testing/rca_test.py::TestSpeedParser -v
    python -m pytest testing/rca_test.py::TestFeatureExtraction -v
    python -m pytest testing/rca_test.py::TestAutoencoderInference -v
    python -m pytest testing/rca_test.py::TestRCALogic -v
    python -m pytest testing/rca_test.py::TestRCAEndpoints -v

Dependencies:
    pip install psutil pytest requests flask numpy joblib tensorflow
"""

import sys
import os
import json
import pytest
import numpy as np

# =========================================================
# PATH SETUP — Legacy Compatibility
# =========================================================
# The ML/RCA functions (parse_speed_string, extract_ae_features,
# perform_rca, ae_model, ae_scaler) live exclusively in
# monitoring/realtime_ai_detection.py and have not been
# ported to the agent/ architecture.  This is intentional:
# the AI pipeline is maintained separately and tested here
# via its original module path.

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
DEVOPS_DIR = os.path.dirname(TEST_DIR)
MONITORING_DIR = os.path.join(DEVOPS_DIR, "monitoring")

sys.path.insert(0, MONITORING_DIR)


# ==========================================================
# TEST 1: SPEED STRING PARSER
# ==========================================================

class TestSpeedParser:
    """
    Verify parse_speed_string converts formatted speed strings
    back to numeric KB values.
    """

    def test_parse_bytes(self):
        from realtime_ai_detection import parse_speed_string

        result = parse_speed_string("1024.00 B")
        assert abs(result - 1.0) < 0.01, (
            f"Expected ~1.0 KB, got {result}"
        )

    def test_parse_kilobytes(self):
        from realtime_ai_detection import parse_speed_string

        result = parse_speed_string("200 KB")
        assert abs(result - 200.0) < 0.01, (
            f"Expected 200.0 KB, got {result}"
        )

    def test_parse_megabytes(self):
        from realtime_ai_detection import parse_speed_string

        result = parse_speed_string("4.39 MB")
        expected = 4.39 * 1024.0
        assert abs(result - expected) < 0.1, (
            f"Expected ~{expected} KB, got {result}"
        )

    def test_parse_gigabytes(self):
        from realtime_ai_detection import parse_speed_string

        result = parse_speed_string("1.5 GB")
        expected = 1.5 * 1024.0 * 1024.0
        assert abs(result - expected) < 1.0, (
            f"Expected ~{expected} KB, got {result}"
        )

    def test_parse_zero(self):
        from realtime_ai_detection import parse_speed_string

        result = parse_speed_string("0.00 B")
        assert result == 0.0

    def test_parse_none(self):
        from realtime_ai_detection import parse_speed_string

        assert parse_speed_string(None) == 0.0

    def test_parse_empty_string(self):
        from realtime_ai_detection import parse_speed_string

        assert parse_speed_string("") == 0.0

    def test_parse_invalid_string(self):
        from realtime_ai_detection import parse_speed_string

        assert parse_speed_string("not a speed") == 0.0

    def test_parse_case_insensitive(self):
        from realtime_ai_detection import parse_speed_string

        result_lower = parse_speed_string("10 kb")
        result_upper = parse_speed_string("10 KB")
        assert abs(result_lower - result_upper) < 0.01

    def test_all_units_produce_expected_output(self):
        """Quick smoke test across every supported unit."""
        from realtime_ai_detection import parse_speed_string

        cases = {
            "512.00 B":  512.0 / 1024,
            "100 KB":    100.0,
            "2 MB":      2 * 1024.0,
            "0.5 GB":    0.5 * 1024 * 1024,
            "0.001 TB":  0.001 * 1024 * 1024 * 1024,
        }
        for speed_str, expected in cases.items():
            result = parse_speed_string(speed_str)
            assert abs(result - expected) < 1.0, (
                f"parse_speed_string('{speed_str}') "
                f"= {result}, expected ~{expected}"
            )
        print("\n[SPEED PARSER] All unit conversions passed ✓")


# ==========================================================
# TEST 2: FEATURE EXTRACTION
# ==========================================================

class TestFeatureExtraction:
    """
    Verify extract_ae_features returns a 9-element array
    with sensible values.
    """

    def test_feature_vector_shape(self):
        from realtime_ai_detection import extract_ae_features

        fake_metrics = {
            "cpu_usage": 25.0,
            "ram_usage": 60.0,
            "disk_usage": 50.0,
            "disk_read_speed": "10 MB",
            "disk_write_speed": "5 MB",
            "network_upload_speed": "200 KB",
            "network_download_speed": "300 KB",
            "process_count": 200,
            "system_load": 1.5,
            "system_uptime": "10h 0m 0s",
        }

        features = extract_ae_features(fake_metrics)

        assert features.shape == (9,), (
            f"Expected shape (9,), got {features.shape}"
        )

    def test_feature_values_are_non_negative(self):
        from realtime_ai_detection import extract_ae_features

        fake_metrics = {
            "cpu_usage": 10.0,
            "disk_read_speed": "1 KB",
            "disk_write_speed": "0.50 KB",
            "network_upload_speed": "0.00 B",
            "network_download_speed": "0.00 B",
        }

        features = extract_ae_features(fake_metrics)

        for i, v in enumerate(features):
            assert v >= 0, (
                f"Feature index {i} is negative: {v}"
            )

        print(
            "\n[FEATURE EXTRACTION] 9-element vector"
            " with non-negative values ✓"
        )

    def test_cpu_capacity_is_positive(self):
        from realtime_ai_detection import extract_ae_features

        features = extract_ae_features({"cpu_usage": 50.0})

        # Index 0 = CPU capacity provisioned [MHZ]
        assert features[0] > 0, (
            f"CPU capacity should be positive, got {features[0]}"
        )

    def test_memory_capacity_is_positive(self):
        from realtime_ai_detection import extract_ae_features

        features = extract_ae_features({"cpu_usage": 10.0})

        # Index 3 = Memory capacity provisioned [KB]
        assert features[3] > 0, (
            f"Memory capacity should be positive, got {features[3]}"
        )


# ==========================================================
# TEST 3: AUTOENCODER INFERENCE
# ==========================================================

class TestAutoencoderInference:
    """
    Verify the autoencoder model loads and can run inference
    on a dummy sequence, producing the correct output shape.
    """

    def test_model_loads_and_predicts(self):
        from realtime_ai_detection import (
            ae_model,
            ae_scaler,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        # Create a dummy sequence of 30 time steps × 9 features
        dummy_raw = np.random.rand(SEQUENCE_LENGTH, 9) * 100
        dummy_scaled = ae_scaler.transform(dummy_raw)

        input_tensor = dummy_scaled.reshape(
            1, SEQUENCE_LENGTH, FEATURE_COUNT
        )

        reconstructed = ae_model.predict(
            input_tensor, verbose=0
        )

        assert reconstructed.shape == (
            1, SEQUENCE_LENGTH, FEATURE_COUNT
        ), (
            f"Expected output shape "
            f"(1, {SEQUENCE_LENGTH}, {FEATURE_COUNT}), "
            f"got {reconstructed.shape}"
        )

        print(
            "\n[AUTOENCODER] Model loaded and produced"
            f" output shape {reconstructed.shape} ✓"
        )

    def test_reconstruction_error_is_non_negative(self):
        from realtime_ai_detection import (
            ae_model,
            ae_scaler,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        dummy_raw = np.ones((SEQUENCE_LENGTH, 9)) * 50
        dummy_scaled = ae_scaler.transform(dummy_raw)

        input_tensor = dummy_scaled.reshape(
            1, SEQUENCE_LENGTH, FEATURE_COUNT
        )

        reconstructed = ae_model.predict(
            input_tensor, verbose=0
        )

        mse = float(
            np.mean(
                np.square(input_tensor - reconstructed)
            )
        )

        assert mse >= 0.0, f"MSE should be >= 0, got {mse}"

        print(
            f"\n[AUTOENCODER] Reconstruction MSE = {mse:.6f} ✓"
        )


# ==========================================================
# TEST 4: RCA LOGIC
# ==========================================================

class TestRCALogic:
    """
    Verify perform_rca correctly identifies root causes and
    ranks top contributors.
    """

    def test_rca_identifies_cpu_as_root_cause(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        # Actual sequence: all zeros
        actual = np.zeros((1, SEQUENCE_LENGTH, FEATURE_COUNT))

        # Reconstructed: mostly matches actual, except
        # CPU features (indices 0, 1, 2) have large error
        reconstructed = np.zeros(
            (1, SEQUENCE_LENGTH, FEATURE_COUNT)
        )
        reconstructed[:, :, 0] = 0.9   # CPU capacity error
        reconstructed[:, :, 1] = 0.8   # CPU usage MHZ error
        reconstructed[:, :, 2] = 0.7   # CPU usage % error

        root_cause, category_errors, top_contributors = (
            perform_rca(actual, reconstructed)
        )

        assert root_cause == "CPU Usage", (
            f"Expected 'CPU Usage', got '{root_cause}'"
        )
        assert top_contributors[0][0] == "CPU Usage"

        print(
            "\n[RCA] Correctly identified CPU Usage"
            " as root cause ✓"
        )

    def test_rca_identifies_memory_as_root_cause(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        actual = np.zeros((1, SEQUENCE_LENGTH, FEATURE_COUNT))
        reconstructed = np.zeros(
            (1, SEQUENCE_LENGTH, FEATURE_COUNT)
        )
        reconstructed[:, :, 3] = 0.9   # Memory capacity
        reconstructed[:, :, 4] = 0.8   # Memory usage

        root_cause, _, _ = perform_rca(actual, reconstructed)

        assert root_cause == "Memory Usage", (
            f"Expected 'Memory Usage', got '{root_cause}'"
        )

    def test_rca_identifies_disk_as_root_cause(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        actual = np.zeros((1, SEQUENCE_LENGTH, FEATURE_COUNT))
        reconstructed = np.zeros(
            (1, SEQUENCE_LENGTH, FEATURE_COUNT)
        )
        reconstructed[:, :, 5] = 0.9   # Disk read
        reconstructed[:, :, 6] = 0.8   # Disk write

        root_cause, _, _ = perform_rca(actual, reconstructed)

        assert root_cause == "Disk Usage", (
            f"Expected 'Disk Usage', got '{root_cause}'"
        )

    def test_rca_identifies_network_as_root_cause(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        actual = np.zeros((1, SEQUENCE_LENGTH, FEATURE_COUNT))
        reconstructed = np.zeros(
            (1, SEQUENCE_LENGTH, FEATURE_COUNT)
        )
        reconstructed[:, :, 7] = 0.9   # Net received
        reconstructed[:, :, 8] = 0.8   # Net transmitted

        root_cause, _, _ = perform_rca(actual, reconstructed)

        assert root_cause == "Network Usage", (
            f"Expected 'Network Usage', got '{root_cause}'"
        )

    def test_top_contributors_are_sorted_descending(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
        )

        actual = np.zeros((1, SEQUENCE_LENGTH, FEATURE_COUNT))
        reconstructed = np.zeros(
            (1, SEQUENCE_LENGTH, FEATURE_COUNT)
        )
        reconstructed[:, :, 0:3] = 0.5  # CPU
        reconstructed[:, :, 3:5] = 0.3  # Memory
        reconstructed[:, :, 5:7] = 0.1  # Disk
        reconstructed[:, :, 7:9] = 0.05 # Network

        _, _, top_contributors = perform_rca(
            actual, reconstructed
        )

        errors = [err for _, err in top_contributors]
        assert errors == sorted(errors, reverse=True), (
            f"Top contributors not sorted descending: {errors}"
        )

        print(
            "\n[RCA] Top contributors correctly sorted ✓"
        )

    def test_category_errors_has_four_entries(self):
        from realtime_ai_detection import (
            perform_rca,
            SEQUENCE_LENGTH,
            FEATURE_COUNT,
            FEATURES,
        )

        actual = np.random.rand(
            1, SEQUENCE_LENGTH, FEATURE_COUNT
        )
        reconstructed = np.random.rand(
            1, SEQUENCE_LENGTH, FEATURE_COUNT
        )

        _, category_errors, _ = perform_rca(
            actual, reconstructed
        )

        assert len(category_errors) == 4, (
            f"Expected 4 categories, got {len(category_errors)}"
        )

        for cat in FEATURES:
            assert cat in category_errors, (
                f"Missing category '{cat}'"
            )


# ==========================================================
# TEST 5: RCA API ENDPOINTS
# ==========================================================

class TestRCAEndpoints:
    """
    Verify the RCA API endpoints work correctly.
    Uses the Flask test_backend.py test client (no live
    server needed).  This tests the legacy mock backend's
    RCA endpoints which mirror the production API contract.
    """

    @pytest.fixture(autouse=True)
    def setup_client(self, tmp_path):
        """Create a test client and temp store file."""
        # Import and patch the app
        sys.path.insert(0, MONITORING_DIR)
        import test_backend

        # Override the store file to a temp location
        self._store_file = str(
            tmp_path / "rca_test_store.json"
        )
        test_backend.RCA_STORE_FILE = self._store_file

        test_backend.app.testing = True
        self.client = test_backend.app.test_client()

    def test_post_rca_event(self):
        """POST /api/rca should accept and store an event."""
        payload = {
            "timestamp": "2026-06-01T12:00:00",
            "anomaly": True,
            "anomaly_score": 0.91,
            "root_cause": "CPU Usage",
            "feature_errors": {
                "CPU Usage": 0.91,
                "Memory Usage": 0.20,
                "Disk Usage": 0.08,
                "Network Usage": 0.03,
            },
            "top_contributors": [
                {"metric": "CPU Usage", "error": 0.91},
                {"metric": "Memory Usage", "error": 0.20},
            ],
        }

        response = self.client.post(
            "/api/rca",
            json=payload,
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "success"
        assert data["total_events"] == 1

        print("\n[API] POST /api/rca works ✓")

    def test_post_rca_empty_payload(self):
        """POST /api/rca with empty body should return 400."""
        response = self.client.post(
            "/api/rca",
            data="",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_get_latest_rca_no_events(self):
        """GET /api/rca/latest with no events returns 404."""
        response = self.client.get("/api/rca/latest")
        assert response.status_code == 404

    def test_get_latest_rca_after_post(self):
        """GET /api/rca/latest returns the most recent event."""
        # Post two events
        for i in range(2):
            self.client.post(
                "/api/rca",
                json={
                    "timestamp": f"2026-06-01T12:0{i}:00",
                    "root_cause": "Memory Usage"
                    if i == 1
                    else "CPU Usage",
                },
            )

        response = self.client.get("/api/rca/latest")
        assert response.status_code == 200

        data = response.get_json()
        assert data["root_cause"] == "Memory Usage"

        print("\n[API] GET /api/rca/latest works ✓")

    def test_get_rca_stats_empty(self):
        """GET /api/rca/stats with no events returns zeroes."""
        response = self.client.get("/api/rca/stats")
        assert response.status_code == 200

        data = response.get_json()
        assert data["total_anomalies"] == 0

    def test_get_rca_stats_after_posts(self):
        """GET /api/rca/stats returns correct aggregation."""
        # Post 3 events: 2 CPU, 1 Memory
        for rc in ["CPU Usage", "CPU Usage", "Memory Usage"]:
            self.client.post(
                "/api/rca",
                json={"root_cause": rc},
            )

        response = self.client.get("/api/rca/stats")
        assert response.status_code == 200

        data = response.get_json()
        assert data["total_anomalies"] == 3
        assert data["most_frequent_root_cause"] == "CPU Usage"
        assert data["anomaly_count_per_metric"]["CPU Usage"] == 2
        assert data["anomaly_count_per_metric"]["Memory Usage"] == 1
        assert abs(
            data["root_cause_distribution"]["CPU Usage"] - 66.67
        ) < 0.1

        print("\n[API] GET /api/rca/stats works ✓")


# ==========================================================
# Run all tests from command line
# ==========================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
