from sqlalchemy import Column, DateTime, String

from app.infrastructure.db.base import Base


class Wallet(Base):
    __tablename__ = "wallets"
    address = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
