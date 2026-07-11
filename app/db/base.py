from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy import DateTime, func
from sqlalchemy.orm import mapped_column, MappedColumn
from datetime import datetime


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'

    created_at: MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: MappedColumn[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
