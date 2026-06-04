import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables (check app/.env, root/.env, and process working directory)
db_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(db_dir, ".env"))
load_dotenv(os.path.join(os.path.dirname(db_dir), ".env"))
load_dotenv()

# Extract database connection details
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER") or os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME") or os.getenv("DB_DATABASE") or "test"

if not all([DB_HOST, DB_USER, DB_PASSWORD]):
    raise ValueError("Missing database configuration. Please check your environment variables (DB_HOST, DB_USER/DB_USERNAME, DB_PASSWORD)")

# Construct SQLAlchemy database URL for TiDB Cloud (MySQL compatible)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Configure SSL arguments to match connection.py (disabling strict certificate checking for developer setup)
connect_args = {
    "ssl": {
        "ssl_verify_cert": False,
        "ssl_verify_identity": False
    }
}

# Create engine with pool settings suitable for cloud database connections
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

# Setup Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for models
Base = declarative_base()

def get_db():
    """
    Dependency generator that yields a database session and ensures
    it is closed after the request lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_db_connection(db) -> bool:
    """
    Verify that the database connection is healthy by executing a simple query.
    """
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
