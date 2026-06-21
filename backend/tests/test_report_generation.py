import os
import sys
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

# Ensure root of project is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.main import app
from app.database import SessionLocal, Base, engine
from backend.services.incident_service import get_incident_service
from backend.models.incident import Incident
from backend.models.correlation import Correlation
from backend.alerting.models import Alert
from backend.report_generator.report_generator import get_report_generator
from backend.report_generator.report_storage import get_report_storage


@pytest.fixture(scope="module")
def client():
    """
    Provide TestClient for reports API testing.
    """
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a transaction-backed database session.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def test_report_generation_payload_and_files(db_session):
    """
    Verify report generation aggregates correct data, saves metadata, 
    and writes CSV/PDF files to the filesystem.
    """
    # 1. Seed dependencies: Incident
    incident_service = get_incident_service()
    incident = incident_service.create_incident(
        db=db_session,
        root_cause="Node Failure",
        impacted_services=["namenode", "datanode"],
    )
    assert incident is not None

    # Seed correlation
    corr = Correlation(
        metric_anomaly_id=1,
        log_anomaly_id=1,
        correlation_score=0.95,
        inferred_cause="Node Failure",
        confidence=95.0,
        service_name="namenode"
    )
    db_session.add(corr)
    
    # Seed matching alert
    alert = Alert(
        alert_id="ALT-999",
        severity="HIGH",
        title="Node Failure",
        message="Node failure detected on namenode, datanode.",
        affected_services="namenode,datanode",
        status="OPEN"
    )
    db_session.add(alert)
    db_session.commit()

    generator = get_report_generator()
    storage = get_report_storage()

    # 2. Generate Report
    res = generator.generate_incident_report(
        db=db_session,
        incident_id=incident.incident_id,
        formats=["pdf", "csv"]
    )

    assert res["status"] == "success"
    report_id = res["report_id"]
    assert report_id.startswith("REP-")

    # 3. Verify files were generated on disk
    metadata = storage.get_metadata(report_id)
    assert metadata is not None
    assert metadata["incident_id"] == incident.incident_id
    assert "pdf" in metadata["available_formats"]
    assert "csv" in metadata["available_formats"]

    pdf_path = metadata["pdf_path"]
    csv_path = metadata["csv_path"]

    assert os.path.exists(pdf_path)
    assert os.path.exists(csv_path)

    # Cleanup generated test files
    try:
        os.remove(pdf_path)
        os.remove(csv_path)
        # Remove JSON metadata file
        meta_file = os.path.join(storage.metadata_dir, f"{report_id}.json")
        if os.path.exists(meta_file):
            os.remove(meta_file)
    except OSError:
        pass


def test_generate_report_missing_incident(db_session):
    """
    Verify error handling when trying to generate a report for a non-existent incident.
    """
    generator = get_report_generator()
    with pytest.raises(ValueError) as exc:
        generator.generate_incident_report(
            db=db_session,
            incident_id="INC-999999",
            formats=["pdf"]
        )
    assert "does not exist" in str(exc.value)


def test_report_routes_api(client):
    """
    Verify /reports REST API endpoints: POST generate, GET list, GET detail, GET download.
    """
    # 1. Seed incident via API
    payload = {
        "root_cause": "disk failure",
        "impacted_services": ["datanode"]
    }
    create_resp = client.post("/incidents/", json=payload)
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["incident_id"]

    # 2. Call API POST /reports/generate
    post_payload = {
        "incident_id": incident_id,
        "formats": ["pdf", "csv"]
    }
    response = client.post("/reports/generate", json=post_payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["status"] == "success"
    report_id = data["report_id"]
    assert report_id.startswith("REP-")

    # 3. Call API GET /reports/{report_id}
    detail_resp = client.get(f"/reports/{report_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["report_id"] == report_id
    assert detail_data["incident_id"] == incident_id

    # 4. Call API GET /reports/
    list_resp = client.get("/reports/")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert any(r["report_id"] == report_id for r in list_data)

    # 5. Call API GET /reports/download/{report_id} for PDF
    download_pdf_resp = client.get(f"/reports/download/{report_id}?format=pdf")
    assert download_pdf_resp.status_code == 200
    assert download_pdf_resp.headers["content-type"] == "application/pdf"

    # 6. Call API GET /reports/download/{report_id} for CSV
    download_csv_resp = client.get(f"/reports/download/{report_id}?format=csv")
    assert download_csv_resp.status_code == 200
    assert download_csv_resp.headers["content-type"].startswith("text/csv")

    # 7. Call API GET /reports/download/{report_id} with invalid format
    err_resp = client.get(f"/reports/download/{report_id}?format=xlsx")
    assert err_resp.status_code == 400

    # Cleanup generated files and metadata
    storage = get_report_storage()
    metadata = storage.get_metadata(report_id)
    if metadata:
        for fkey in ["pdf_path", "csv_path"]:
            path = metadata.get(fkey)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        meta_file = os.path.join(storage.metadata_dir, f"{report_id}.json")
        if os.path.exists(meta_file):
            try:
                os.remove(meta_file)
            except OSError:
                pass

