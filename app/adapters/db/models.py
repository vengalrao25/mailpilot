from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# No user table yet — hardcoded until multi-user lands (see ROADMAP.md).
DEFAULT_USER_ID = 1


class Base(DeclarativeBase):
    pass


class EmailORM(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    sender: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, default=DEFAULT_USER_ID, nullable=False)
