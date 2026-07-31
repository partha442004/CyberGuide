"""
Base Engine

Provides common functionality for all AI engines.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class EngineResult:
    """Standardized engine result."""

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data or {}
        self.errors = errors or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class BaseEngine(ABC):
    """
    Base class for all AI engines.

    Provides:
    - Common configuration
    - Logging
    - Error handling
    - Result formatting
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"cybershield.engines.{name}")

    @abstractmethod
    async def process(self, data: Any, **kwargs) -> EngineResult:
        """Process input data and return result."""
        pass

    async def run(self, data: Any, **kwargs) -> EngineResult:
        """Run engine with error handling."""
        self.logger.info(f"Running {self.name} engine")
        try:
            result = await self.process(data, **kwargs)
            self.logger.info(f"{self.name} engine completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"{self.name} engine failed: {e}")
            return EngineResult(
                success=False,
                errors=[str(e)],
            )

    def _create_result(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        **metadata,
    ) -> EngineResult:
        """Create a standardized result."""
        return EngineResult(
            success=success,
            data=data or {},
            errors=errors or [],
            metadata=metadata,
        )
