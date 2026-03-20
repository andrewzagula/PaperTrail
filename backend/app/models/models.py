import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    papers: Mapped[list["Paper"]] = relationship(back_populates="user")
    chats: Mapped[list["Chat"]] = relationship(back_populates="user")
    saved_items: Mapped[list["SavedItem"]] = relationship(back_populates="user")
    discovery_runs: Mapped[list["DiscoveryRun"]] = relationship(back_populates="user")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    authors: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    arxiv_url: Mapped[str | None] = mapped_column(String(500))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured_breakdown: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="papers")
    sections: Mapped[list["PaperSection"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    chats: Mapped[list["Chat"]] = relationship(back_populates="paper")


class PaperSection(Base):
    __tablename__ = "paper_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    # Note: embeddings are stored in ChromaDB, linked by section id

    # Relationships
    paper: Mapped["Paper"] = relationship(back_populates="sections")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("papers.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="chats")
    paper: Mapped["Paper"] = relationship(back_populates="chats")


class SavedItem(Base):
    __tablename__ = "saved_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # "comparison", "idea", "implementation"
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    paper_ids: Mapped[list | None] = mapped_column(JSON)  # related paper UUIDs
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="saved_items")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_queries: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, running, complete, failed
    budget_used: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="discovery_runs")
    results: Mapped[list["DiscoveryResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class DiscoveryResult(Base):
    __tablename__ = "discovery_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    arxiv_id: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    authors: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    published: Mapped[str | None] = mapped_column(String(50))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("papers.id"), nullable=True, index=True
    )  # set when user ingests this result

    # Relationships
    run: Mapped["DiscoveryRun"] = relationship(back_populates="results")
    paper: Mapped["Paper | None"] = relationship()
