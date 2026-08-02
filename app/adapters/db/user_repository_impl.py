from app.adapters.db.models import UserORM
from app.adapters.db.session import SessionLocal


class SqlUserRepository:
    def get_or_create(self, email: str) -> int:
        with SessionLocal() as session:
            user = session.query(UserORM).filter_by(email=email).first()
            if user:
                return user.id

            user = UserORM(email=email)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id
