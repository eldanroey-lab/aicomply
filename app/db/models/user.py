from sqlalchemy import String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Tenant(Base):
    __tablename__ = 'tenants'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(50), default='free')  # free, pro, enterprise

    users: Mapped[list['User']] = relationship(back_populates='tenant', cascade='all, delete-orphan')
    frameworks: Mapped[list['Framework']] = relationship(back_populates='tenant')
    documents: Mapped[list['Document']] = relationship(back_populates='tenant')


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(50), default='member')  # admin, member, viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), nullable=False)

    tenant: Mapped['Tenant'] = relationship(back_populates='users')
    documents: Mapped[list['Document']] = relationship(back_populates='uploader')
    tasks: Mapped[list['Task']] = relationship(back_populates='assignee',
                                               foreign_keys='Task.assignee_id')
