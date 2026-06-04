import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import engine, Base, SessionLocal, get_db, verify_db_connection
from app.routers import metrics, anomalies, ml
from app.ml_service import get_ml_service

# =========================================================
# LOGGING CONFIGURATION
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("metricguard")


# =========================================================
# APPLICATION LIFESPAN (startup / shutdown)
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: verify database connection, create tables, and load ML models.
    On shutdown: dispose engine connections.
    """
    logger.info("MetricGuard backend starting up...")
    
    # Verify database connection on startup
    logger.info("Verifying database connection...")
    db = SessionLocal()
    is_connected = verify_db_connection(db)
    db.close()
    
    if not is_connected:
        logger.critical("Database connection verification FAILED. Database is unavailable.")
        raise SystemExit("Database connection failed. Application startup aborted.")
    
    logger.info("Database connection verified successfully.")
    
    logger.info("Creating database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")
    
    # Load ML models
    logger.info("Initializing ML models...")
    ml_service = get_ml_service()
    success = ml_service.load_models()
    if success:
        logger.info("ML models loaded successfully at startup.")
    else:
        logger.error("ML models failed to load at startup: %s", ml_service.model_load_error)
        
    yield
    logger.info("MetricGuard backend shutting down...")
    engine.dispose()


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="MetricGuard API",
    description="AIOps platform backend — stores system metrics and anomaly detection results in TiDB Cloud.",
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# CORS MIDDLEWARE
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MOUNT ROUTERS
# =========================================================

app.include_router(metrics.router)
app.include_router(anomalies.router)
app.include_router(ml.router)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Exposes detailed status of API service health and database connectivity.
    """
    db_healthy = verify_db_connection(db)
    db_status = "healthy" if db_healthy else "unhealthy"
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "api": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }
