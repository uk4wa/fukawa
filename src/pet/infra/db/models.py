import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    DateTime,
    func,
    String,
)
import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from pet.infra.db.base import Base


class IdMixin:
    id: Mapped[int] = mapped_column(
        BigInteger,
        sa.Identity(start=1),
        primary_key=True,
    )

    public_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrgRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))

    org_memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="assignee",
        lazy="raise_on_sql",
    )


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)

    members: Mapped[list["Membership"]] = relationship(
        back_populates="org",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class Membership(Base, IdMixin, TimestampMixin):
    __tablename__ = "memberships"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    org_id: Mapped[int] = mapped_column(
        BigInteger,
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_role: Mapped[str] = mapped_column(
        sa.Enum(OrgRole, name="org_role"),
        nullable=False,
        server_default=sa.text("'member'"),
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "org_id", name="uq_memberships_org_user"),
        sa.Index("ix_memberships_org_id", "org_id"),
        # sa.Index("ix_memberships_user_id", "user_id"),
    )

    user: Mapped["User"] = relationship(
        back_populates="org_memberships",
        lazy="raise_on_sql",
    )

    org: Mapped["Organization"] = relationship(
        back_populates="members",
        lazy="raise_on_sql",
    )


class Project(Base, IdMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(320), nullable=False)

    org_id: Mapped[int] = mapped_column(
        BigInteger,
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("org_id", "name", name="uq_projects_org_name"),
        # sa.Index("ix_projects_org_id", "org_id"),
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )


class TaskStatus(str, enum.Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class Task(Base, IdMixin, TimestampMixin):
    __tablename__ = "tasks"
    name: Mapped[str] = mapped_column(String(320), nullable=False)

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    assignee_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        sa.Enum(TaskStatus, name="task_status"),
        nullable=False,
        server_default=sa.text("'todo'"),
    )

    project: Mapped["Project"] = relationship(
        back_populates="tasks",
        lazy="raise_on_sql",
    )
    assignee: Mapped["User"] = relationship(
        back_populates="tasks",
        lazy="raise_on_sql",
    )
    __table_args__ = (
        sa.Index("ix_tasks_project_id", "project_id"),
        sa.Index("ix_tasks_assignee_user_id", "assignee_user_id"),
        sa.Index("ix_tasks_status", "status"),
    )
