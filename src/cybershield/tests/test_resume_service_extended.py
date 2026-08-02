"""
Unit Tests for Resume Parsing Service (extended)

Covers the remaining file-handling paths of
``cybershield/services/resume_service.py``:
- ``parse_pdf`` with a mocked PDF document
- ``parse_upload`` for PDF content and unsupported formats
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

from cybershield.services.resume_service import ResumeParser


class FakePage:
    """Fake PyMuPDF page."""

    def __init__(self, text):
        self._text = text

    def get_text(self):
        return self._text


class FakeDoc:
    """Fake PyMuPDF document."""

    def __init__(self, pages):
        self._pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self._pages)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_pymupdf(monkeypatch):
    """Inject a fake pymupdf module into sys.modules."""

    fake_module = types.ModuleType("pymupdf")
    fake_module.open = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pymupdf", fake_module)
    return fake_module


class TestParsePdf:
    """Tests for the parse_pdf method."""

    @pytest.mark.asyncio
    async def test_parse_pdf_extracts_text(self, fake_pymupdf):
        """Should open the PDF, join page text, and parse it."""
        fake_pymupdf.open.return_value = FakeDoc(
            [
                FakePage("Security Engineer with SIEM and Nmap experience.\n"),
                FakePage("Certified: CEH"),
            ]
        )

        parser = ResumeParser()
        result = await parser.parse_pdf("/tmp/fake_resume.pdf")

        assert "skills" in result
        skill_names = [s["name"].lower() for s in result["skills"]]
        assert "siem" in skill_names
        assert "nmap" in skill_names
        assert "ceh" in skill_names
        # raw_text should contain the joined page text
        assert "Certified: CEH" in result["raw_text"]
        assert fake_pymupdf.open.return_value.closed is True


class TestParseUpload:
    """Tests for the parse_upload method."""

    @pytest.mark.asyncio
    async def test_parse_upload_pdf(self, fake_pymupdf):
        """Should parse a PDF upload and attach file metadata."""
        fake_pymupdf.open.return_value = FakeDoc([FakePage("Penetration testing skills")])

        parser = ResumeParser()
        result = await parser.parse_upload(b"%PDF-1.4 fake content", "resume.pdf")

        assert "skills" in result
        assert result["file_name"] == "resume.pdf"
        assert isinstance(result["file_hash"], str)
        assert len(result["file_hash"]) == 64  # sha256 hex digest

    @pytest.mark.asyncio
    async def test_parse_upload_unsupported_format_raises(self):
        """Should raise ValueError for non-PDF uploads."""
        parser = ResumeParser()
        with pytest.raises(ValueError, match="Unsupported file format"):
            await parser.parse_upload(b"some text", "resume.txt")

    @pytest.mark.asyncio
    async def test_parse_upload_cleans_up_temp_file(self, fake_pymupdf, monkeypatch):
        """Should delete the temp file even when parsing fails."""
        fake_pymupdf.open.side_effect = RuntimeError("corrupt pdf")

        parser = ResumeParser()
        unlink_mock = MagicMock()

        import os

        monkeypatch.setattr(os, "unlink", unlink_mock)

        with pytest.raises(RuntimeError):
            await parser.parse_upload(b"%PDF-1.4 corrupt", "resume.pdf")

        unlink_mock.assert_called_once()
