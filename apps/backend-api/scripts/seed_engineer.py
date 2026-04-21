from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth_service import get_password_hash


def run():
    db = SessionLocal()
    try:
        stmt = select(User).where(User.username == "engineer")
        user = db.scalar(stmt)
        if user:
            user.hashed_password = get_password_hash("ChangeMe123!")
            db.commit()
            print("Engineer password reset.")
            return

        engineer = User(
            username="engineer",
            email="engineer@local",
            full_name="Default Engineer",
            hashed_password=get_password_hash("ChangeMe123!"),
            role=UserRole.ENGINEER,
        )
        db.add(engineer)
        db.commit()
        print("Engineer user created.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
