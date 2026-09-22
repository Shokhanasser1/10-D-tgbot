from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AttributeValueType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category


class Attribute(TimestampMixin, Base):
    __tablename__ = "attributes"
    __table_args__ = (UniqueConstraint("category_id", "key", name="uq_attributes_category_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    value_type: Mapped[AttributeValueType] = mapped_column(
        Enum(AttributeValueType, native_enum=False, length=20), nullable=False
    )

    category: Mapped["Category"] = relationship("Category", back_populates="attributes")
