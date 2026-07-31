"""
Domain exceptions for CyberShield.
"""

from typing import Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        status: int = 500,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.code = code
        self.status = status
        self.error_code = code
        self.status_code = status
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# Alias for backward compatibility
CyberShieldException = AppException


class NotFoundError(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' not found",
            code="NOT_FOUND",
            status=404,
            details={"resource": resource, "identifier": identifier},
        )


class DuplicateJobError(AppException):
    """Duplicate job exception."""

    def __init__(self, job_title: str, company: str):
        super().__init__(
            message=f"Job '{job_title}' at '{company}' already exists",
            code="DUPLICATE_JOB",
            status=409,
            details={"title": job_title, "company": company},
        )


class ScrapingError(AppException):
    """Scraping error exception."""

    def __init__(self, source: str, reason: str):
        super().__init__(
            message=f"Scraping failed for {source}: {reason}",
            code="SCRAPING_ERROR",
            status=422,
            details={"source": source, "reason": reason},
        )


class NotificationError(AppException):
    """Notification error exception."""

    def __init__(self, channel: str, reason: str):
        super().__init__(
            message=f"Notification failed for {channel}: {reason}",
            code="NOTIFICATION_ERROR",
            status=502,
            details={"channel": channel, "reason": reason},
        )


class ValidationError(AppException):
    """Validation error exception."""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"Validation failed for {field}: {reason}",
            code="VALIDATION_ERROR",
            status=422,
            details={"field": field, "reason": reason},
        )


class ConfigurationError(AppException):
    """Configuration error exception."""

    def __init__(self, setting: str, reason: str):
        super().__init__(
            message=f"Configuration error for {setting}: {reason}",
            code="CONFIGURATION_ERROR",
            status=500,
            details={"setting": setting, "reason": reason},
        )


class ScamDetectedError(AppException):
    """Scam detected exception."""

    def __init__(self, job_title: str, scam_score: int):
        super().__init__(
            message=f"Scam detected for job '{job_title}' (score: {scam_score})",
            code="SCAM_DETECTED",
            status=403,
            details={"title": job_title, "scam_score": scam_score},
        )


class EngineNotFoundError(AppException):
    """AI engine not found exception."""

    def __init__(self, engine_name: str):
        super().__init__(
            message=f"Engine '{engine_name}' not found",
            code="ENGINE_NOT_FOUND",
            status=404,
            details={"engine": engine_name},
        )


class InvalidInputError(AppException):
    """Invalid input exception."""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Invalid input: {reason}",
            code="INVALID_INPUT",
            status=400,
            details={"reason": reason},
        )
