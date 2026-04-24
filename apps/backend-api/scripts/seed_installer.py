from sqlalchemy import select, text

from app.db.session import SessionLocal, engine
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import get_password_hash


DEFAULT_USERNAME = "installer"
DEFAULT_PASSWORD = "ChangeMe123!"
DEFAULT_EMAIL = "installer@local"
DEFAULT_FULL_NAME = "Default Installer"


def ensure_enum_value() -> None:
    """PostgreSQL userrole enum'una INSTALLER degeri ekle (idempotent)."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as ac_conn:
        ac_conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'INSTALLER'"))


def run():
    ensure_enum_value()
    db = SessionLocal()
    try:
        stmt = select(User).where(User.username == DEFAULT_USERNAME)
        user = db.scalar(stmt)
        if user:
            user.hashed_password = get_password_hash(DEFAULT_PASSWORD)
            user.role = UserRole.INSTALLER
            db.commit()
            print(f"Installer user password reset (username={DEFAULT_USERNAME}).")
            return

        installer = User(
            username=DEFAULT_USERNAME,
            email=DEFAULT_EMAIL,
            full_name=DEFAULT_FULL_NAME,
            hashed_password=get_password_hash(DEFAULT_PASSWORD),
            role=UserRole.INSTALLER,
        )
        db.add(installer)
        db.commit()
        print(f"Installer user created (username={DEFAULT_USERNAME}, password={DEFAULT_PASSWORD}).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
