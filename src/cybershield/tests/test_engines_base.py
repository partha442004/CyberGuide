"""
Unit tests for cybershield.engines.base.

Covers EngineResult defaults/serialization, BaseEngine.run success and
error handling, and the _create_result helper.
"""

from unittest.mock import AsyncMock, patch

import pytest

from cybershield.engines.base import BaseEngine, EngineResult


class TestEngineResult:
    def test_defaults(self):
        result = EngineResult(success=True)
        assert result.success is True
        assert result.data == {}
        assert result.errors == []
        assert result.metadata == {}

    def test_custom_values(self):
        result = EngineResult(
            success=False,
            data={"a": 1},
            errors=["e1"],
            metadata={"m": 2},
        )
        assert result.data == {"a": 1}
        assert result.errors == ["e1"]
        assert result.metadata == {"m": 2}

    def test_to_dict(self):
        result = EngineResult(success=True, data={"a": 1}, errors=[], metadata={"m": 2})
        assert result.to_dict() == {
            "success": True,
            "data": {"a": 1},
            "errors": [],
            "metadata": {"m": 2},
        }


class _ConcreteEngine(BaseEngine):
    """Concrete engine that returns a canned result or raises."""

    def __init__(self, name="test", config=None, behavior="ok"):
        super().__init__(name, config)
        self.behavior = behavior

    async def process(self, data, **kwargs):
        if self.behavior == "raise":
            raise ValueError("engine exploded")
        if self.behavior == "fail":
            return EngineResult(success=False, errors=["not now"])
        return self._create_result(
            success=True,
            data={"input": str(data)},
            engine=self.name,
            version="1.0",
        )


class TestBaseEngine:
    def test_initializes_name_and_config(self):
        engine = _ConcreteEngine("matching", {"timeout": 5})
        assert engine.name == "matching"
        assert engine.config == {"timeout": 5}
        assert engine.logger.name == "cybershield.engines.matching"

    def test_config_defaults_to_empty(self):
        engine = _ConcreteEngine("matching")
        assert engine.config == {}

    @pytest.mark.asyncio
    async def test_run_success_returns_result(self):
        engine = _ConcreteEngine()
        result = await engine.run("hello")
        assert result.success is True
        assert result.data == {"input": "hello"}
        assert result.metadata == {"engine": "test", "version": "1.0"}

    @pytest.mark.asyncio
    async def test_run_captures_exception_as_failure(self):
        engine = _ConcreteEngine(behavior="raise")
        result = await engine.run("x")
        assert result.success is False
        assert result.errors == ["engine exploded"]

    @pytest.mark.asyncio
    async def test_run_passes_through_failed_result(self):
        engine = _ConcreteEngine(behavior="fail")
        result = await engine.run("x")
        assert result.success is False
        assert result.errors == ["not now"]

    @pytest.mark.asyncio
    async def test_run_logs_on_exception(self):
        engine = _ConcreteEngine(behavior="raise")
        with patch.object(engine.logger, "error") as mock_error:
            await engine.run("x")
        mock_error.assert_called_once()

    def test_create_result_builds_engine_result(self):
        engine = _ConcreteEngine()
        result = engine._create_result(
            True,
            data={"x": 1},
            errors=["warn"],
            extra="meta",
        )
        assert isinstance(result, EngineResult)
        assert result.success is True
        assert result.data == {"x": 1}
        assert result.errors == ["warn"]
        assert result.metadata == {"extra": "meta"}
