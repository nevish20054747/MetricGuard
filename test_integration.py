"""
MetricGuard — Integration Test Suite (Phase 5: Database Persistence Layer)

Tests the full database integration layer end-to-end:
 • Health check endpoint
 • Metric CRUD through the FastAPI API
 • Anomaly CRUD with mandatory metric_id foreign key
 • One-to-many relationship (Metric -> Anomalies)
 • Cascade delete behaviour
 • Filtering, sorting, and pagination on anomalies
 • Metric-scoped anomaly retrieval
 • RCA stats aggregation
 • Input validation and constraint enforcement

Run with:
    python -m pytest test_integration.py -v
"""

import sys
import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import SessionLocal, Base, engine


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient that lasts for the entire test module.
    Tables are created before and dropped after the suite.
    """
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    # Note: Tables are intentionally NOT dropped after tests so user
    # can inspect the database manually. Drop manually if required.


@pytest.fixture(scope="module")
def db_session():
    """
    Provide a raw SQLAlchemy session for low-level verification queries.
    """
    session = SessionLocal()
    yield session
    session.close()


# ============================================================
# 1. Health Check
# ============================================================

class TestHealthCheck:
    """Verify the /health endpoint reports database and API status."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert "api" in data
        assert "database" in data
        assert "timestamp" in data

    def test_health_reports_healthy(self, client):
        data = client.get("/health").json()
        assert data["api"] == "healthy"
        assert data["database"] == "healthy"
        assert data["status"] == "healthy"


# ============================================================
# 2. Metrics CRUD
# ============================================================

class TestMetricsCRUD:
    """Verify metric creation and retrieval through the API."""

    @pytest.fixture(autouse=True, scope="class")
    def _create_test_metric(self, client):
        """Insert a metric used by all tests in this class."""
        payload = {
            "timestamp": "2026-06-04T12:00:00",
            "cpu_usage": 75.5,
            "ram_usage": 60.0,
            "disk_usage": 50.0,
            "disk_read_speed": "10 MB",
            "disk_write_speed": "5 MB",
            "network_upload_speed": "200 KB",
            "network_download_speed": "2 MB",
            "process_count": 200,
            "system_load": 4.0,
            "system_uptime": "48h",
        }
        resp = client.post("/metrics/?detect=false", json=payload)
        assert resp.status_code == 201
        self.__class__._metric = resp.json()

    def test_metric_has_id(self):
        assert self._metric["id"] is not None

    def test_metric_values_stored(self):
        assert self._metric["cpu_usage"] == 75.5
        assert self._metric["memory_usage"] == 60.0

    def test_metric_speed_parsed_to_kb(self):
        # 10 MB -> 10 * 1024 = 10240 KB
        assert self._metric["disk_read"] == 10240.0
        # 200 KB -> 200
        assert self._metric["network_tx"] == 200.0

    def test_metric_has_audit_fields(self):
        assert "created_at" in self._metric
        assert "updated_at" in self._metric

    def test_get_metrics_returns_list(self, client):
        resp = client.get("/metrics/?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_metrics_ordered_by_timestamp_desc(self, client):
        # Insert a second metric with a later timestamp
        payload2 = {
            "timestamp": "2026-06-04T13:00:00",
            "cpu_usage": 50.0,
            "ram_usage": 40.0,
        }
        client.post("/metrics/?detect=false", json=payload2)

        resp = client.get("/metrics/?limit=10")
        data = resp.json()
        if len(data) >= 2:
            ts0 = datetime.fromisoformat(data[0]["timestamp"])
            ts1 = datetime.fromisoformat(data[1]["timestamp"])
            assert ts0 >= ts1


# ============================================================
# 3. Anomalies CRUD & Foreign Key Enforcement
# ============================================================

class TestAnomaliesCRUD:
    """Verify anomaly creation, foreign key enforcement, and retrieval."""

    @pytest.fixture(autouse=True, scope="class")
    def _setup(self, client):
        """Insert a parent metric and a linked anomaly."""
        metric_payload = {
            "timestamp": "2026-06-04T14:00:00",
            "cpu_usage": 99.0,
            "ram_usage": 95.0,
        }
        metric_resp = client.post("/metrics/?detect=false", json=metric_payload)
        assert metric_resp.status_code == 201
        self.__class__._metric_id = metric_resp.json()["id"]

        anomaly_payload = {
            "timestamp": "2026-06-04T14:00:01",
            "anomaly_score": 0.92,
            "root_cause": "CPU Usage",
            "severity": "critical",
            "detected_by": "isolation_forest",
            "ml_model_version": "1.0.0",
            "metric_id": self.__class__._metric_id,
        }
        anomaly_resp = client.post("/anomalies/", json=anomaly_payload)
        assert anomaly_resp.status_code == 201
        self.__class__._anomaly = anomaly_resp.json()

    def test_anomaly_has_id(self):
        assert self._anomaly["id"] is not None

    def test_anomaly_linked_to_metric(self):
        assert self._anomaly["metric_id"] == self._metric_id

    def test_anomaly_has_audit_fields(self):
        assert "created_at" in self._anomaly
        assert "updated_at" in self._anomaly

    def test_anomaly_without_metric_id_fails(self, client):
        """Attempting to create an anomaly without metric_id should fail (422)."""
        bad_payload = {
            "timestamp": "2026-06-04T14:00:02",
            "anomaly_score": 0.5,
            "severity": "low",
            "detected_by": "test",
        }
        resp = client.post("/anomalies/", json=bad_payload)
        assert resp.status_code == 422  # Pydantic validation error

    def test_anomaly_with_invalid_metric_id_fails(self, client):
        """Anomaly pointing to a non-existent metric_id should fail (500 FK violation)."""
        bad_payload = {
            "timestamp": "2026-06-04T14:00:03",
            "anomaly_score": 0.3,
            "severity": "low",
            "detected_by": "test",
            "ml_model_version": "1.0.0",
            "metric_id": 999999,
        }
        resp = client.post("/anomalies/", json=bad_payload)
        assert resp.status_code == 500  # FK constraint error


# ============================================================
# 4. One-to-Many: Metric -> Anomalies
# ============================================================

class TestOneToMany:
    """Verify the /metrics/{id}/anomalies sub-resource endpoint."""

    @pytest.fixture(autouse=True, scope="class")
    def _setup(self, client):
        """Create a metric with two linked anomalies."""
        metric_resp = client.post("/metrics/?detect=false", json={
            "timestamp": "2026-06-04T15:00:00",
            "cpu_usage": 88.0,
            "ram_usage": 92.0,
        })
        self.__class__._metric_id = metric_resp.json()["id"]

        for i, sev in enumerate(["critical", "warning"]):
            client.post("/anomalies/", json={
                "timestamp": f"2026-06-04T15:00:0{i}",
                "anomaly_score": 0.8 + i * 0.05,
                "root_cause": "CPU Usage" if i == 0 else "Memory Usage",
                "severity": sev,
                "detected_by": "isolation_forest",
                "ml_model_version": "1.0.0",
                "metric_id": self.__class__._metric_id,
            })

    def test_get_metric_anomalies(self, client):
        resp = client.get(f"/metrics/{self._metric_id}/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_all_anomalies_point_to_parent(self, client):
        data = client.get(f"/metrics/{self._metric_id}/anomalies").json()
        for a in data:
            assert a["metric_id"] == self._metric_id

    def test_nonexistent_metric_returns_404(self, client):
        resp = client.get("/metrics/999999/anomalies")
        assert resp.status_code == 404


# ============================================================
# 5. Filtering, Sorting & Pagination
# ============================================================

class TestAnomalyFiltering:
    """Verify query parameters on GET /anomalies/."""

    @pytest.fixture(autouse=True, scope="class")
    def _setup(self, client):
        """Create a metric and anomalies with varying severities for filtering tests."""
        metric_resp = client.post("/metrics/?detect=false", json={
            "timestamp": "2026-06-04T16:00:00",
            "cpu_usage": 50.0,
            "ram_usage": 40.0,
        })
        mid = metric_resp.json()["id"]
        self.__class__._metric_id = mid

        for i, (sev, rc) in enumerate([
            ("critical", "CPU Usage"),
            ("warning", "Memory Usage"),
            ("low", "Disk I/O"),
        ]):
            client.post("/anomalies/", json={
                "timestamp": f"2026-06-04T16:0{i}:00",
                "anomaly_score": 0.5 + i * 0.15,
                "root_cause": rc,
                "severity": sev,
                "detected_by": "integration_test",
                "ml_model_version": "1.0.0",
                "metric_id": mid,
            })

    def test_filter_by_severity(self, client):
        resp = client.get("/anomalies/?severity=critical")
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["severity"] == "critical" for a in data)

    def test_filter_by_detected_by(self, client):
        resp = client.get("/anomalies/?detected_by=integration_test")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3

    def test_sort_by_anomaly_score_asc(self, client):
        resp = client.get("/anomalies/?sort_by=anomaly_score&sort_order=asc&detected_by=integration_test")
        data = resp.json()
        if len(data) >= 2:
            scores = [a["anomaly_score"] for a in data]
            assert scores == sorted(scores)

    def test_pagination_limit(self, client):
        resp = client.get("/anomalies/?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 2

    def test_pagination_offset(self, client):
        all_resp = client.get("/anomalies/?limit=100&detected_by=integration_test")
        offset_resp = client.get("/anomalies/?limit=100&offset=1&detected_by=integration_test")
        all_data = all_resp.json()
        offset_data = offset_resp.json()
        if len(all_data) > 1:
            assert len(offset_data) == len(all_data) - 1

    def test_include_metric_true(self, client):
        resp = client.get("/anomalies/?include_metric=true&limit=1")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["metric"] is not None

    def test_include_metric_false(self, client):
        resp = client.get("/anomalies/?include_metric=false&limit=1")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["metric"] is None


# ============================================================
# 6. RCA Stats
# ============================================================

class TestRCAStats:
    """Verify the /ml/rca/stats aggregation endpoint."""

    def test_rca_stats_returns_200(self, client):
        resp = client.get("/ml/rca/stats")
        assert resp.status_code == 200

    def test_rca_stats_structure(self, client):
        data = client.get("/ml/rca/stats").json()
        assert "total_anomalies" in data
        assert "by_root_cause" in data
        assert "by_severity" in data

    def test_rca_stats_total_positive(self, client):
        data = client.get("/ml/rca/stats").json()
        assert data["total_anomalies"] > 0


# ============================================================
# 7. Cascade Delete (ORM-level)
# ============================================================

class TestCascadeDelete:
    """Verify that deleting a Metric cascades to its child Anomalies at ORM level."""

    def test_cascade_deletes_anomalies(self, client, db_session):
        from app.models import Metric, Anomaly
        from app.schemas import MetricCreate, AnomalyCreate
        from app.crud import insert_metric, insert_anomaly

        # Insert a metric + anomaly through CRUD
        metric_in = MetricCreate(
            timestamp=datetime.now(),
            cpu_usage=77.0,
            memory_usage=80.0,
        )
        db_metric = insert_metric(db_session, metric_in)

        anomaly_in = AnomalyCreate(
            timestamp=datetime.now(),
            anomaly_score=0.6,
            root_cause="Test Cascade",
            severity="low",
            detected_by="cascade_test",
            ml_model_version="1.0.0",
            metric_id=db_metric.id,
        )
        db_anomaly = insert_anomaly(db_session, anomaly_in)
        anomaly_id = db_anomaly.id

        # Delete the parent metric
        db_session.delete(db_metric)
        db_session.commit()

        # Verify the child anomaly is gone
        orphan = db_session.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
        assert orphan is None, "Anomaly was NOT cascade-deleted with its parent Metric!"


# ============================================================
# 8. Input Validation & Constraints
# ============================================================

class TestInputValidation:
    """Verify Pydantic and DB-level constraint enforcement."""

    def test_negative_anomaly_score_rejected(self, client):
        """
        Pydantic field_validator rejects negative anomaly_score values
        before they ever reach the database.
        """
        # First create a parent metric
        metric_resp = client.post("/metrics/?detect=false", json={
            "timestamp": "2026-06-04T17:00:00",
            "cpu_usage": 10.0,
        })
        mid = metric_resp.json()["id"]

        bad_payload = {
            "timestamp": "2026-06-04T17:00:01",
            "anomaly_score": -1.0,
            "severity": "low",
            "detected_by": "test",
            "ml_model_version": "1.0.0",
            "metric_id": mid,
        }
        resp = client.post("/anomalies/", json=bad_payload)
        # Pydantic validation error
        assert resp.status_code == 422

    def test_invalid_severity_rejected(self, client):
        """
        Pydantic field_validator rejects unknown severity values
        before they ever reach the database.
        """
        metric_resp = client.post("/metrics/?detect=false", json={
            "timestamp": "2026-06-04T17:01:00",
            "cpu_usage": 10.0,
        })
        mid = metric_resp.json()["id"]

        bad_payload = {
            "timestamp": "2026-06-04T17:01:01",
            "anomaly_score": 0.5,
            "severity": "INVALID_SEVERITY",
            "detected_by": "test",
            "ml_model_version": "1.0.0",
            "metric_id": mid,
        }
        resp = client.post("/anomalies/", json=bad_payload)
        assert resp.status_code == 422
