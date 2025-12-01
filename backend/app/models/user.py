"""
SQLAlchemy model for User authentication
"""
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime
from sqlalchemy.sql import func
from ..database import Base


class User(Base):
    """User account for authentication"""
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    full_name = Column(String(255))
    role = Column(String(50), default='user')  # 'admin' or 'user'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
