"""
Unit tests for cybershield.domain.exceptions.

Covers the base AppException (defaults, to_dict, attribute aliases) and
every concrete exception subclass.
"""

from cybershield.domain.exceptions import (
    AppException,
    ConfigurationError,
    CyberGuideException,
    DuplicateJobError,
    EngineNotFoundError,
    InvalidInputError,
    NotFoundError,
    NotificationError,
    ScamDetectedError,
    ScrapingError,
    ValidationError,
)


class TestAppException:
    def test_defaults(self):
        exc = AppException("boom")
        assert exc.message == "boom"
        assert exc.code == "APP_ERROR"
        assert exc.status == 500
        assert exc.error_code == "APP_ERROR"
        assert exc.status_code == 500
        assert exc.details == {}
        assert str(exc) == "boom"

    def test_custom_values_and_details(self):
        exc = AppException("oops", code="CUSTOM", status=418, details={"k": "v"})
        assert exc.code == "CUSTOM"
        assert exc.status == 418
        assert exc.status_code == 418
        assert exc.error_code == "CUSTOM"
        assert exc.details == {"k": "v"}

    def test_to_dict(self):
        exc = AppException("oops", code="CUSTOM", details={"k": "v"})
        assert exc.to_dict() == {
            "error": {"code": "CUSTOM", "message": "oops", "details": {"k": "v"}}
        }

    def test_cyberguide_alias(self):
        assert CyberGuideException is AppException


class TestConcreteExceptions:
    def test_not_found_error(self):
        exc = NotFoundError("Job", "j-1")
        assert exc.code == "NOT_FOUND"
        assert exc.status == 404
        assert "Job with identifier 'j-1' not found" in exc.message
        assert exc.details == {"resource": "Job", "identifier": "j-1"}

    def test_duplicate_job_error(self):
        exc = DuplicateJobError("Security Eng", "Acme")
        assert exc.code == "DUPLICATE_JOB"
        assert exc.status == 409
        assert "already exists" in exc.message
        assert exc.details == {"title": "Security Eng", "company": "Acme"}

    def test_scraping_error(self):
        exc = ScrapingError("naukri", "timeout")
        assert exc.code == "SCRAPING_ERROR"
        assert exc.status == 422
        assert exc.details == {"source": "naukri", "reason": "timeout"}

    def test_notification_error(self):
        exc = NotificationError("telegram", "auth failed")
        assert exc.code == "NOTIFICATION_ERROR"
        assert exc.status == 502
        assert exc.details == {"channel": "telegram", "reason": "auth failed"}

    def test_validation_error(self):
        exc = ValidationError("email", "invalid format")
        assert exc.code == "VALIDATION_ERROR"
        assert exc.status == 422
        assert exc.details == {"field": "email", "reason": "invalid format"}

    def test_configuration_error(self):
        exc = ConfigurationError("DATABASE_URL", "missing")
        assert exc.code == "CONFIGURATION_ERROR"
        assert exc.status == 500
        assert exc.details == {"setting": "DATABASE_URL", "reason": "missing"}

    def test_scam_detected_error(self):
        exc = ScamDetectedError("Easy Money", 95)
        assert exc.code == "SCAM_DETECTED"
        assert exc.status == 403
        assert "score: 95" in exc.message
        assert exc.details == {"title": "Easy Money", "scam_score": 95}

    def test_engine_not_found_error(self):
        exc = EngineNotFoundError("matching")
        assert exc.code == "ENGINE_NOT_FOUND"
        assert exc.status == 404
        assert exc.details == {"engine": "matching"}

    def test_invalid_input_error(self):
        exc = InvalidInputError("bad data")
        assert exc.code == "INVALID_INPUT"
        assert exc.status == 400
        assert "Invalid input: bad data" == exc.message
        assert exc.details == {"reason": "bad data"}

    def test_all_exceptions_are_app_exceptions(self):
        for exc in [
            NotFoundError("a", "b"),
            DuplicateJobError("a", "b"),
            ScrapingError("a", "b"),
            NotificationError("a", "b"),
            ValidationError("a", "b"),
            ConfigurationError("a", "b"),
            ScamDetectedError("a", 1),
            EngineNotFoundError("a"),
            InvalidInputError("a"),
        ]:
            assert isinstance(exc, AppException)
            assert exc.to_dict()["error"]["message"]
