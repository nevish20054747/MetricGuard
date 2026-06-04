import sys
import os
from datetime import datetime

# Add the workspace root to Python path so it can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Base, engine
from app.models import Metric, Anomaly
from app.schemas import MetricCreate, AnomalyCreate
from app.crud import insert_metric, insert_anomaly, get_anomalies_by_metric

def test_relationship_linkage():
    print("--------------------------------------------------")
    print("MetricGuard Database Relationship Verification Utility")
    print("--------------------------------------------------")

    # Recreate tables if they do not exist
    print("Creating database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)

    # 1. Open DB Session
    print("1. Opening DB Session...")
    db = SessionLocal()

    try:
        # 2. Insert parent Metric
        print("2. Inserting parent Metric record...")
        metric_in = MetricCreate(
            timestamp=datetime.now(),
            cpu_usage=88.5,
            memory_usage=90.2,
            disk_read=500.0,
            disk_write=150.0,
            network_rx=25.0,
            network_tx=12.0
        )
        db_metric = insert_metric(db, metric_in)
        print(f"   -> Metric inserted successfully with ID: {db_metric.id}")

        # 3. Insert child Anomaly linked to the Metric ID
        print("3. Inserting child Anomaly record linked to the Metric ID...")
        anomaly_in = AnomalyCreate(
            timestamp=datetime.now(),
            anomaly_score=0.95,
            root_cause="CPU Usage",
            severity="CRITICAL",
            detected_by="TEST_SUITE_LINKAGE",
            ml_model_version="1.0.0",
            metric_id=db_metric.id
        )
        db_anomaly = insert_anomaly(db, anomaly_in)
        print(f"   -> Anomaly inserted successfully with ID: {db_anomaly.id}, metric_id: {db_anomaly.metric_id}")

        # 4. Verify Anomaly -> Metric relationship
        print("4. Verifying Anomaly to Metric relationship...")
        db.refresh(db_anomaly)
        assert db_anomaly.metric is not None, "Failed: Anomaly.metric is None!"
        assert db_anomaly.metric.id == db_metric.id, "Failed: Anomaly.metric.id does not match Metric.id!"
        print(f"   -> Success! Anomaly linked back to Metric (CPU: {db_anomaly.metric.cpu_usage}%).")

        # 5. Verify Metric -> Anomaly relationship (one-to-many list)
        print("5. Verifying Metric to Anomalies one-to-many relationship...")
        db.refresh(db_metric)
        assert len(db_metric.anomalies) > 0, "Failed: Metric.anomalies list is empty!"
        assert db_metric.anomalies[0].id == db_anomaly.id, "Failed: Linked anomaly ID mismatch in Metric.anomalies list!"
        print(f"   -> Success! Metric has linked anomalies in back_populates list (Total: {len(db_metric.anomalies)}).")

        # 6. Verify get_anomalies_by_metric CRUD function
        print("6. Verifying get_anomalies_by_metric CRUD helper...")
        results = get_anomalies_by_metric(db, metric_id=db_metric.id)
        assert len(results) == 1, f"Failed: Expected 1 anomaly, got {len(results)}"
        assert results[0].id == db_anomaly.id, "Failed: Anomaly ID mismatch in CRUD query results!"
        print("   -> Success! CRUD helper returned correct anomaly list.")

        # 7. Verify Cascade Delete Behavior
        print("7. Verifying Cascade Delete behavior...")
        print("   Deleting parent Metric record...")
        db.delete(db_metric)
        db.commit()

        # Check if the child anomaly is deleted automatically
        orphaned_anomaly = db.query(Anomaly).filter(Anomaly.id == db_anomaly.id).first()
        assert orphaned_anomaly is None, "Failed: Linked anomaly was NOT cascade deleted!"
        print("   -> Success! Linked anomaly was automatically cascade-deleted with the Metric record.")

        print("\n🎉 Database Relationship Linkage Verification SUCCESSFUL!")

    except Exception as e:
        print(f"   [ERROR] Relationship verification failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_relationship_linkage()
