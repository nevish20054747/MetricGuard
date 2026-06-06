import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LogCreate, LogResponse
from app.crud import insert_log, get_logs

logger = logging.getLogger("metricguard.routers.logs")

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.post("/", response_model=LogResponse, status_code=201)
def create_log(
    payload: LogCreate,
    db: Session = Depends(get_db),
):
    """
    Ingest a single application log entry from the MetricGuard Agent.

    The agent's log_collector watches application log files, parses each
    new line into structured JSON, and POSTs it here.
    """
    try:
        db_log = insert_log(db, payload)
        logger.info(
            "Log stored (ID: %d) [%s] service=%s",
            db_log.id, db_log.level, db_log.service_name,
        )
        return db_log
    except Exception as e:
        logger.error("Failed to store log entry: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store log: {str(e)}")


@router.get("/", response_model=list[LogResponse])
def read_logs(
    limit: int = Query(default=100, ge=1, le=1000, description="Max number of log entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip for pagination"),
    level: Optional[str] = Query(default=None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    service_name: Optional[str] = Query(default=None, description="Filter by originating service name"),
    start_date: Optional[datetime] = Query(default=None, description="Filter logs on or after this datetime"),
    end_date: Optional[datetime] = Query(default=None, description="Filter logs on or before this datetime"),
    db: Session = Depends(get_db),
):
    """
    Retrieve stored application logs with optional filtering.

    Supports filtering by level, service_name, and date range.
    Results are ordered by timestamp descending (newest first).
    """
    try:
        logs = get_logs(
            db,
            limit=limit,
            offset=offset,
            level=level,
            service_name=service_name,
            start_date=start_date,
            end_date=end_date,
        )
        return logs
    except Exception as e:
        logger.error("Failed to retrieve logs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")
