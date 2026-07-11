from sqlalchemy import String, Text, Float, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Framework(Base):
    __tablename__ = 'frameworks'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(50))
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    # Structured controls as JSON: [{id, title, description, category, weight}]
    controls: Mapped[dict | None] = mapped_column(JSON, default=list)
    compliance_score: Mapped[float | None] = mapped_column(Float)

    tenant: Mapped['Tenant'] = relationship(back_populates='frameworks')
    tasks: Mapped[list['Task']] = relationship(back_populates='framework')
    documents: Mapped[list['Document']] = relationship(back_populates='framework')
