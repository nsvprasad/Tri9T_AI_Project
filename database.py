
import sys

# Tell Python where our installed packages are located
sys.path.insert(0, r"D:\Tri9T_AI_Project\packages")

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Location of our SQLite database file
DATABASE_URL = "sqlite:///tri9t.db"

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
