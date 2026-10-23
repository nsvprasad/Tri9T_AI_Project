import hashlib
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


def calculate_sha256(text: str) -> str:
    """Calculate SHA-256 fingerprint for text."""
    if text is None:
        text = ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ManualVersion(Base):
    __tablename__ = "manual_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False, unique=True)
    filename = Column(String, nullable=False)
    document_title = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    sections = relationship("ManualSection", back_populates="manual_version", cascade="all, delete-orphan")


class ManualSection(Base):
    __tablename__ = "manual_sections"

    id = Column(Integer, primary_key=True, index=True)
    manual_version_id = Column(
        Integer,
        ForeignKey("manual_versions.id"),
        nullable=False
    )
    logical_id = Column(String, nullable=True, index=True)
    section_number = Column(String, nullable=False, index=True)
    heading = Column(String, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    content = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)

    parent_id = Column(
        Integer,
        ForeignKey("manual_sections.id"),
        nullable=True
    )

    manual_version = relationship("ManualVersion", back_populates="sections")

    parent = relationship(
        "ManualSection",
        remote_side=[id],
        back_populates="children"
    )

    children = relationship(
        "ManualSection",
        back_populates="parent",
        cascade="all"
    )

    def compute_hash(self) -> str:
        """Compute SHA-256 content hash based on normalized heading and content."""
        text = f"{self.heading.strip()}\n{(self.content or '').strip()}"
        return calculate_sha256(text)

    def to_dict(self, include_children=False):
        data = {
            "id": self.id,
            "manual_version_id": self.manual_version_id,
            "logical_id": self.logical_id or self.section_number,
            "section_number": self.section_number,
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "content_hash": self.content_hash,
            "display_order": self.display_order,
            "parent_id": self.parent_id,
        }
        if include_children and self.children:
            data["children"] = [
                child.to_dict(include_children=True)
                for child in sorted(self.children, key=lambda c: (c.display_order, c.section_number))
            ]
        return data


class Selection(Base):
    __tablename__ = "selections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    manual_version = Column(String, nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    items = relationship(
        "SelectionItem",
        back_populates="selection",
        cascade="all, delete-orphan",
        order_by="SelectionItem.id"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "manual_version": self.manual_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_items": len(self.items),
            "items": [item.to_dict() for item in self.items]
        }


class SelectionItem(Base):
    __tablename__ = "selection_items"

    id = Column(Integer, primary_key=True, index=True)
    selection_id = Column(
        Integer,
        ForeignKey("selections.id"),
        nullable=False
    )
    section_id = Column(
        Integer,
        ForeignKey("manual_sections.id"),
        nullable=False
    )
    logical_id = Column(String, nullable=True)
    section_number = Column(String, nullable=False)
    heading = Column(String, nullable=False)
    version = Column(String, nullable=False)
    pinned_hash = Column(String, nullable=False)
    pinned_content = Column(Text, nullable=True)

    selection = relationship("Selection", back_populates="items")
    section = relationship("ManualSection")

    def to_dict(self):
        return {
            "id": self.id,
            "selection_id": self.selection_id,
            "section_id": self.section_id,
            "logical_id": self.logical_id,
            "section_number": self.section_number,
            "heading": self.heading,
            "version": self.version,
            "pinned_hash": self.pinned_hash,
            "pinned_content": self.pinned_content
        }
