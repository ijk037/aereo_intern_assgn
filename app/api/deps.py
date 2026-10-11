from typing import Generator
from sqlalchemy.orm import Session
from app.db.database import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """Dependency that yields a database session and ensures closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
