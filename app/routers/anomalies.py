import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnomalyCreate, AnomalyResponse
from app.crud import insert_anomaly, get_anomalies_filtered

logger = logging.getLogger("metricguard.routers.anomalies")

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.post("/", response_model=AnomalyResponse, status_code=201)
def create_anomaly(payload: AnomalyCreate, db: Session = Depends(get_db)):
    """
    Store an anomaly result in TiDB.

    Called by the AI detection pipeline after Isolation Forest,
    LSTM Autoencoder, and Root Cause Analysis complete.
    """
    try:
        db_anomaly = insert_anomaly(db, payload)
        logger.info("Anomaly stored (ID: %d, root_cause: %s)", db_anomaly.id, db_anomaly.root_cause)
        return db_anomaly
    except Exception as e:
        logger.error("Failed to store anomaly: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store anomaly: {str(e)}")


@router.get("/", response_model=list[AnomalyResponse])
def read_anomalies(
    limit: int = Query(default=100, ge=1, le=1000, description="Number of records to retrieve"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    sort_by: str = Query(default="timestamp", description="Column to sort by (timestamp, anomaly_score, severity)"),
    sort_order: str = Query(default="desc", description="Sort order (asc, desc)"),
    severity: str = Query(default=None, description="Filter by severity"),
    root_cause: str = Query(default=None, description="Filter by root cause"),
    detected_by: str = Query(default=None, description="Filter by detection method"),
    include_metric: bool = Query(default=False, description="Whether to include associated metric details"),
    db: Session = Depends(get_db),
):
    """
    Retrieve anomaly history from TiDB with filtering, sorting, and pagination.
    """
    try:
        anomalies = get_anomalies_filtered(
            db,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            severity=severity,
            root_cause=root_cause,
            detected_by=detected_by,
            include_metric=include_metric
        )
        
        # If include_metric is False, explicitly prevent lazy-loading nested metric object during Pydantic serialization
        if not include_metric:
            for a in anomalies:
                a.__dict__['metric'] = None
                
        return anomalies
    except Exception as e:
        logger.error("Failed to retrieve anomalies: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve anomalies: {str(e)}")
