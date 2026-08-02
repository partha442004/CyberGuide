"""
Tests for BaseRepository (generic CRUD) and CompanyRepository.

Uses the shared in-memory-SQLite ``db_session`` fixture from conftest so all
operations run against a real (throwaway) database.
"""

import pytest

from cybershield.domain.exceptions import NotFoundError
from cybershield.domain.models import Company
from cybershield.repositories.base import BaseRepository
from cybershield.repositories.company_repository import CompanyRepository


class TestBaseRepositoryCRUD:
    @pytest.mark.asyncio
    async def test_create_generates_id(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"name": "Acme"})
        assert company.id  # auto-generated uuid
        assert company.name == "Acme"

    @pytest.mark.asyncio
    async def test_create_respects_provided_id(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"id": "fixed-id", "name": "Beta"})
        assert company.id == "fixed-id"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, db_session):
        repo = BaseRepository(Company, db_session)
        assert await repo.get("nope") is None

    @pytest.mark.asyncio
    async def test_get_or_raise_raises_not_found(self, db_session):
        repo = BaseRepository(Company, db_session)
        with pytest.raises(NotFoundError):
            await repo.get_or_raise("missing")

    @pytest.mark.asyncio
    async def test_get_or_raise_returns_record(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"name": "Gamma"})
        fetched = await repo.get_or_raise(str(company.id))
        assert fetched.id == company.id

    @pytest.mark.asyncio
    async def test_get_all_with_pagination_and_filters(self, db_session):
        repo = BaseRepository(Company, db_session)
        await repo.create_many(
            [
                {"name": "One", "industry": "tech"},
                {"name": "Two", "industry": "tech"},
                {"name": "Three", "industry": "finance"},
            ]
        )
        all_companies = await repo.get_all()
        assert len(all_companies) == 3

        tech = await repo.get_all(filters={"industry": "tech"})
        assert len(tech) == 2

        first_page = await repo.get_all(skip=0, limit=2)
        assert len(first_page) == 2

    @pytest.mark.asyncio
    async def test_get_all_list_filter_uses_in(self, db_session):
        repo = BaseRepository(Company, db_session)
        await repo.create_many([{"name": "A"}, {"name": "B"}, {"name": "C"}])
        result = await repo.get_all(filters={"name": ["A", "B"]})
        names = {c.name for c in result}
        assert names == {"A", "B"}

    @pytest.mark.asyncio
    async def test_count_with_and_without_filters(self, db_session):
        repo = BaseRepository(Company, db_session)
        await repo.create_many(
            [{"name": "A", "is_trusted": True}, {"name": "B", "is_trusted": False}]
        )
        assert await repo.count() == 2
        assert await repo.count(filters={"is_trusted": True}) == 1

    @pytest.mark.asyncio
    async def test_update_changes_fields(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"name": "Old Name"})
        updated = await repo.update(str(company.id), {"name": "New Name", "industry": "tech"})
        assert updated.name == "New Name"
        assert updated.industry == "tech"

    @pytest.mark.asyncio
    async def test_update_missing_raises(self, db_session):
        repo = BaseRepository(Company, db_session)
        with pytest.raises(NotFoundError):
            await repo.update("missing", {"name": "X"})

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"name": "Delete Me"})
        assert await repo.delete(str(company.id)) is True
        assert await repo.get(str(company.id)) is None

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self, db_session):
        repo = BaseRepository(Company, db_session)
        assert await repo.delete("missing") is False

    @pytest.mark.asyncio
    async def test_exists(self, db_session):
        repo = BaseRepository(Company, db_session)
        company = await repo.create({"name": "Exists"})
        assert await repo.exists(str(company.id)) is True
        assert await repo.exists("nope") is False

    @pytest.mark.asyncio
    async def test_search_finds_matching_records(self, db_session):
        repo = BaseRepository(Company, db_session)
        await repo.create_many([{"name": "Acme Corp"}, {"name": "Other Inc"}])
        results = await repo.search("acme", fields=["name"])
        assert len(results) == 1
        assert results[0].name == "Acme Corp"


class TestCompanyRepository:
    @pytest.mark.asyncio
    async def test_get_by_name_case_insensitive(self, db_session):
        repo = CompanyRepository(db_session)
        await repo.create({"name": "Acme Corp"})
        company = await repo.get_by_name("acme corp")
        assert company is not None
        assert company.name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_get_or_create_by_name_creates(self, db_session):
        repo = CompanyRepository(db_session)
        company = await repo.get_or_create_by_name("Brand New")
        assert company.name == "Brand New"
        # second call reuses the same record
        again = await repo.get_or_create_by_name("Brand New")
        assert again.id == company.id

    @pytest.mark.asyncio
    async def test_get_with_jobs_empty(self, db_session):
        repo = CompanyRepository(db_session)
        company = await repo.create({"name": "Has Jobs"})
        fetched = await repo.get_with_jobs(str(company.id))
        assert fetched is not None
        assert fetched.jobs == []

    @pytest.mark.asyncio
    async def test_search_companies(self, db_session):
        repo = CompanyRepository(db_session)
        await repo.create_many([{"name": "SecureSoft"}, {"name": "DataWorks"}])
        results = await repo.search_companies("secure")
        assert [c.name for c in results] == ["SecureSoft"]

    @pytest.mark.asyncio
    async def test_get_top_hiring_companies(self, db_session):
        from cybershield.domain.models import Job

        repo = CompanyRepository(db_session)
        company = await repo.create({"name": "BigCo"})

        job_repo = BaseRepository(Job, db_session)
        await job_repo.create_many(
            [
                {
                    "title": "Engineer 1",
                    "company": "BigCo",
                    "company_id": company.id,
                    "url": "https://job.example/1",
                    "source": "linkedin",
                    "job_type": "full_time",
                    "is_active": True,
                    "country": "USA",
                },
                {
                    "title": "Engineer 2",
                    "company": "BigCo",
                    "company_id": company.id,
                    "url": "https://job.example/2",
                    "source": "linkedin",
                    "job_type": "full_time",
                    "is_active": True,
                    "country": "USA",
                },
            ]
        )

        top = await repo.get_top_hiring_companies()
        assert len(top) == 1
        assert top[0]["company"].name == "BigCo"
        assert top[0]["job_count"] == 2

        usa = await repo.get_top_hiring_companies(country="USA")
        assert usa[0]["company"].name == "BigCo"
        no_match = await repo.get_top_hiring_companies(country="IN")
        assert no_match == []

    @pytest.mark.asyncio
    async def test_get_trusted_companies(self, db_session):
        repo = CompanyRepository(db_session)
        await repo.create_many(
            [{"name": "Trusted1", "is_trusted": True}, {"name": "NotTrusted", "is_trusted": False}]
        )
        trusted = await repo.get_trusted_companies()
        assert [c.name for c in trusted] == ["Trusted1"]

    @pytest.mark.asyncio
    async def test_update_trust_status(self, db_session):
        repo = CompanyRepository(db_session)
        company = await repo.create({"name": "Flip"} | {"is_trusted": False})
        updated = await repo.update_trust_status(str(company.id), True)
        assert updated.is_trusted is True
