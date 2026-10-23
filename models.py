
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from database import Base


class ManualVersion(Base):
    __tablename__ = "manual_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import relationship


class ManualSection(Base):
    __tablename__ = "manual_sections"

    id = Column(Integer, primary_key=True, index=True)

    manual_version_id = Column(
        Integer,
        ForeignKey("manual_versions.id"),
        nullable=False
    )

    section_number = Column(String, nullable=False)
    heading = Column(String, nullable=False)
    content = Column(Text, nullable=True)

    parent_id = Column(
        Integer,
        ForeignKey("manual_sections.id"),
        nullable=True
    )

    manual_version = relationship("ManualVersion")

    parent = relationship(
        "ManualSection",
        remote_side=[id],
        back_populates="children"
    )

    children = relationship(
        "ManualSection",
        back_populates="parent"
    )
