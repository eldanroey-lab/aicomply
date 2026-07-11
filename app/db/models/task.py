from sqlalchemy import String, Text, ForeignKey, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date
from app.db.base import Base


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default='open')   # open, in_progress, done, overdue
    priority: Mapped[str] = mapped_column(String(20), default='medium')  # low, medium, high, critical
    due_date: Mapped[date | None] = mapped_column(Date)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    framework_id: Mapped[int | None] = mapped_column(ForeignKey('frameworks.id'))
    # Linked control id from framework JSON
    control_id: Mapped[str | None] = mapped_column(String(100))

    assignee: Mapped['User | None'] = relationship(back_populates='tasks',
                                                    foreign_keys=[assignee_id])
    created_by: Mapped['User'] = relationship(foreign_keys=[created_by_id])
    framework: Mapped['Framework | None'] = relationship(back_populates='tasks')
