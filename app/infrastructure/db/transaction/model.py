from sqlalchemy import Column, String, DateTime, Float, Boolean, Integer, BigInteger
import datetime
from app.infrastructure.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    hash = Column(String, primary_key=True)
    asset = Column(String, nullable=False)
    address_from = Column(String, nullable=False)
    address_to = Column(String, nullable=False)
    value = Column(BigInteger, nullable=False)
    is_token = Column(Boolean, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    effective_fee = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        nullable=False,
    )
    deleted_at = Column(DateTime, nullable=True)
    contract_address = Column(String, nullable=True)
