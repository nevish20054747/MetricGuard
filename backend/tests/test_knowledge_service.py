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
from backend.knowledge_base.models import IncidentHistory, RcaHistory, ResolutionHistory
from backend.knowledge_base.knowledge_service import get_knowledge_service


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def test_knowledge_service_archive_incident(db_session):
    # 1. Seed Incident & Correlation
    incident_service = get_incident_service()
    incident = incident_service.create_incident(
        db=db_session,
        root_cause="disk leak",
        impacted_services=["namenode"],
    )
    
    corr = Correlation(
        metric_anomaly_id=10,
        log_anomaly_id=20,
        correlation_score=0.90,
        inferred_cause="disk leak",
        confidence=90.0,
        service_name="namenode"
    )
    db_session.add(corr)
    db_session.commit()

    service = get_knowledge_service()

    # 2. Perform archival
    archived = service.archive_incident(db_session, incident.incident_id)
    assert archived is not None
    assert archived.incident_id == incident.incident_id
    assert archived.root_cause == "disk leak"
    assert archived.status == "OPEN"

    # 3. Check corresponding history database tables
    hist_inc = db_session.query(IncidentHistory).filter(IncidentHistory.incident_id == incident.incident_id).first()
    assert hist_inc is not None
    assert hist_inc.service_name == "namenode"

    hist_rca = db_session.query(RcaHistory).filter(RcaHistory.incident_id == incident.incident_id).first()
    assert hist_rca is not None
    assert hist_rca.confidence == 90.0

    hist_res = db_session.query(ResolutionHistory).filter(ResolutionHistory.incident_id == incident.incident_id).first()
    assert hist_res is not None
    assert "Resolve" in hist_res.action_taken


def test_knowledge_service_similar_search(db_session):
    # Archive a couple of mock incidents first
    repo = get_knowledge_service().repo
    
    repo.save_incident(
        db=db_session,
        incident_id="INC-HIST-099",
        title="High CPU Load on web-server",
        description="CPU spiked to 100% due to background threads",
        service_name="web-server",
        severity="High",
        status="RESOLVED",
        root_cause="CPU spike",
        resolution="Killed rogue thread pool processes",
        recommendation="None",
        impact_summary="Web latency spiked",
        created_at=datetime.utcnow(),
        resolved_at=datetime.utcnow()
    )
    db_session.commit()

    service = get_knowledge_service()
    
    # Search for similar incident
    matches = service.search_similar_incidents(
        db=db_session,
        title="CPU Load",
        description="web-server CPU 100% capacity threads"
    )

    assert len(matches) >= 1
    best_match = matches[0]
    assert best_match["incident_id"] == "INC-HIST-099"
    assert best_match["similarity_score"] >= 0.70
    assert best_match["resolution"] == "Killed rogue thread pool processes"


def test_knowledge_api_endpoints(client):
    # 1. Seed incident via POST
    payload = {
        "root_cause": "namenode deadlock",
        "impacted_services": ["namenode"]
    }
    create_resp = client.post("/incidents/", json=payload)
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["incident_id"]

    # 2. Call Archive API Endpoint
    arch_resp = client.post("/knowledge/archive", json={"incident_id": incident_id})
    assert arch_resp.status_code == 200
    assert arch_resp.json()["status"] == "success"

    # 3. Call GET /knowledge/incidents
    list_inc = client.get("/knowledge/incidents")
    assert list_inc.status_code == 200
    assert any(i["incident_id"] == incident_id for i in list_inc.json())

    # 4. Call GET /knowledge/rca
    list_rca = client.get("/knowledge/rca")
    assert list_rca.status_code == 200
    assert any(r["incident_id"] == incident_id for r in list_rca.json())

    # 5. Call GET /knowledge/resolutions
    list_res = client.get("/knowledge/resolutions")
    assert list_res.status_code == 200
    assert any(res["incident_id"] == incident_id for res in list_res.json())

    # 6. Call POST /knowledge/similar
    sim_resp = client.post("/knowledge/similar", json={
        "title": "namenode deadlock",
        "description": "Namenode deadlock occured"
    })
    assert sim_resp.status_code == 200
    matches = sim_resp.json()["matches"]
    assert len(matches) >= 1
    assert matches[0]["incident_id"] == incident_id
    assert matches[0]["similarity_score"] >= 0.70


def test_automatic_archiving_on_resolved_patch(client):
    # 1. Create incident (defaults to OPEN)
    payload = {
        "root_cause": "memory exhaustion",
        "impacted_services": ["datanode"]
    }
    create_resp = client.post("/incidents/", json=payload)
    assert create_resp.status_code == 201
    incident_id = create_resp.json()["incident_id"]

    # 2. Transition status: OPEN -> INVESTIGATING -> MITIGATED -> RESOLVED
    p1 = client.patch(f"/incidents/{incident_id}", json={"status": "INVESTIGATING"})
    assert p1.status_code == 200
    
    p2 = client.patch(f"/incidents/{incident_id}", json={"status": "MITIGATED"})
    assert p2.status_code == 200

    # Patching to RESOLVED should automatically archive the incident
    p3 = client.patch(f"/incidents/{incident_id}", json={"status": "RESOLVED"})
    assert p3.status_code == 200

    # 3. Verify it was archived automatically in get archived incidents list
    archived_list_resp = client.get("/knowledge/incidents")
    assert archived_list_resp.status_code == 200
    assert any(i["incident_id"] == incident_id for i in archived_list_resp.json())
