import sys
from pathlib import Path

# Tell Python where our installed packages are located
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "packages"))

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Location of our SQLite database file
DATABASE_URL = f"sqlite:///{PROJECT_DIR / 'tri9t.db'}"

# Create the database connection
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create a factory for database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for defining database tables
Base = declarative_base()


def get_db():
    """Create a database session and close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
