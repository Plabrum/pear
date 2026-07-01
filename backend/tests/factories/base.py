# Base factory for all SQLAlchemy models.
#
# Polyfactory builds model instances from the SQLAlchemy mapping; each domain
# factory subclass pins the fields that matter (enums, FK wiring) and lets faker
# fill the rest. The same factories back both the test fixtures (`tests/fixtures/`)
# and the demo seed, so "what a valid row looks like" has a single definition.

from datetime import UTC, datetime
from typing import Any

from faker import Faker
from polyfactory import Use
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.models import BaseDBModel


class BaseFactory[T: BaseDBModel](SQLAlchemyFactory[T]):
    __is_base_factory__ = True
    __faker__ = Faker()
    __check_model__ = False
    # Relationships / association proxies are wired explicitly by FK id in each
    # factory and the graph builder — never auto-generated.
    __set_relationships__ = False
    __set_association_proxy__ = False
    # `id` is a SqidType-backed INTEGER PK; let PostgreSQL sequences assign it so
    # ids stay real and FK targets resolve.
    __set_primary_key__ = False

    deleted_at = None
    # Pin audit timestamps to "now" (tz-aware) rather than letting polyfactory
    # invent random dates — recency-sensitive queries (e.g. weekly suggestion
    # counts) depend on freshly-created rows. Override per-call for time-spread data.
    created_at = Use(datetime.now, tz=UTC)
    updated_at = Use(datetime.now, tz=UTC)

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: Any) -> T:  # type: ignore[override]
        instance = cls.build(**kwargs)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance

    @classmethod
    async def create_batch_async(cls, session: AsyncSession, size: int, **kwargs: Any) -> list[T]:  # type: ignore[override]
        instances = [cls.build(**kwargs) for _ in range(size)]
        session.add_all(instances)
        await session.flush()
        for instance in instances:
            await session.refresh(instance)
        return instances
