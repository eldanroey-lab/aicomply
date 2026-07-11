from sqlalchemy import String, Text, Float, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Document(Base):
    __tablename__ = 'documents'

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50))
    file_size: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    uploader_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey('frameworks.id'))

    # AI analysis results
    compliance_score: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(20))  # low, medium, high, critical
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_gaps: Mapped[dict | None] = mapped_column(JSON)   # [{control_id, gap, recommendation}]
    ai_tags: Mapped[dict | None] = mapped_column(JSON)   # [str]
    status: Mapped[str] = mapped_column(String(50), default='pending')  # pending, analyzed, failed

    tenant: Mapped['Tenant'] = relationship(back_populates='documents')
    uploader: Mapped['User'] = relationship(back_populates='documents')
    framework: Mapped['Framework'] = relationship(back_populates='documents')
