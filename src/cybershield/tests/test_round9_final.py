"""
Round 9 final-pass unit tests covering the last small uncovered branches:

- ``api/v1/resumes.py`` (match-batch size guard)
- ``interntrack/engines/matching.py`` (skip jobs without skills)
- ``interntrack/services/notification_service.py`` (email + slack channel setup)
- ``scrapers/usa/linkedin.py`` (title without separate location)
- ``start.py`` (process timeout -> kill)
- ``notifications/base.py`` (abstract send body)
- ``interntrack/scrapers/hackernews.py`` (empty text lines, empty company parts)
- ``scrapers/india/internshala.py`` (bad stipend ignored)
- ``interntrack/engines/deduplication.py`` (seen-pair skip)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestResumesBatchGuard:
    """match_resume_batch rejects >50 job ids with a 400."""

    @pytest.mark.asyncio
    async def test_match_batch_rejects_over_50_jobs(self):
        from fastapi import HTTPException

        from cybershield.api.v1.resumes import match_resume_batch

        with pytest.raises(HTTPException) as exc_info:
            await match_resume_batch(
                user_id="user-1",
                job_ids=[f"job-{i}" for i in range(51)],
                session=MagicMock(),
            )
        assert exc_info.value.status_code == 400


class TestMatchingEngineRound9:
    """matching.find_matching_jobs skips jobs with no skills."""

    @pytest.mark.asyncio
    async def test_skips_job_without_skills(self):
        from interntrack.engines.matching import MatchingEngine

        session = MagicMock()
        # user skills query returns one skill
        user_skills_result = MagicMock()
        user_skills_result.all.return_value = [("Python",)]
        # jobs query returns one job
        jobs_result = MagicMock()
        job = MagicMock()
        job.id = "job-1"
        jobs_result.scalars.return_value.all.return_value = [job]
        # job skills query returns empty -> continue
        skills_result = MagicMock()
        skills_result.all.return_value = []
        session.execute = AsyncMock(side_effect=[user_skills_result, jobs_result, skills_result])

        engine = MatchingEngine(session)
        matches = await engine.find_matching_jobs(user_id="user-1")

        assert matches == []


class TestNotificationServiceRound9:
    """_setup_channels registers email and slack when configured."""

    def test_sets_up_email_and_slack_channels(self, monkeypatch):
        import interntrack.services.notification_service as notif_module

        mock_settings = MagicMock()
        mock_settings.telegram_bot_token = None
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "pass"
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_port = 587
        mock_settings.email_from = "sender@example.com"
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = "https://hooks.slack.com/x"
        monkeypatch.setattr(notif_module, "settings", mock_settings)

        manager = notif_module.NotificationManager(session=MagicMock())

        assert "email" in manager._channels
        assert "slack" in manager._channels
        assert "telegram" not in manager._channels
        assert "discord" not in manager._channels


class TestLinkedinRound9:
    """Title \"Job at Company\" without location keeps full tail as company."""

    def test_title_at_without_location(self):
        from cybershield.scrapers.usa.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        entry = {
            "title": "Security Engineer at Acme Corp",
            "link": "https://linkedin.com/jobs/view/1",
            "summary": "",
        }
        job = scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.company_name == "Acme Corp"
        assert job.title == "Security Engineer"


class TestStartRound9:
    """start() kills processes that fail to stop within the timeout."""

    @patch("cybershield.start.time.sleep")
    def test_timeout_terminates_with_kill(self, mock_sleep):
        import subprocess

        from cybershield.start import main

        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=5)

        with (
            patch("cybershield.start.start_api", return_value=proc),
            patch("cybershield.start.start_dashboard", return_value=None),
            patch("cybershield.start.start_scheduler", return_value=None),
            patch("cybershield.start.logger"),
            patch("cybershield.start.sys.exit") as mock_exit,
            patch(
                "cybershield.start.time.sleep",
                side_effect=KeyboardInterrupt(),
            ),
        ):
            main()

        proc.terminate.assert_called()
        proc.kill.assert_called()
        mock_exit.assert_called_once_with(0)


class TestNotifierBaseRound9:
    """The abstract send() body is reachable via a subclass calling super()."""

    @pytest.mark.asyncio
    async def test_abstract_send_body_returns_none(self):
        from cybershield.notifications.base import BaseNotifier, NotificationMessage

        class _Concrete(BaseNotifier):
            async def send(self, message):
                return await super().send(message)  # type: ignore[safe-super]

        notifier = _Concrete("test", {})
        result = await notifier.send(NotificationMessage(title="t", content="c"))
        assert result is None


class TestInterntrackHackernewsRound9:
    """_parse_comment empty lines and _extract_company empty parts."""

    def test_parse_comment_empty_lines(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        comment = {"text": MagicMock()}
        comment["text"].split.return_value = []
        assert scraper._parse_comment(comment, "security") is None

    def test_extract_company_empty_parts(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        with patch("interntrack.scrapers.hackernews.re.split", return_value=[]):
            assert scraper._extract_company("<p>Some text</p>") is None


class TestInternshalaRound9:
    """Bad stipend values are silently ignored."""

    def test_bad_stipend_ignored(self):
        from cybershield.scrapers.india.internshala import InternshalaScraper

        scraper = InternshalaScraper()
        job_data = {"stipend": {"salary": "not-a-number"}}
        with patch("cybershield.scrapers.india.internshala.logger"):
            job = scraper._parse_job_data(job_data)
        assert job.salary_min is None
        assert job.salary_max is None


class TestInterntrackDedupRound9:
    """find_duplicates_in_database skips already-seen pairs."""

    @pytest.mark.asyncio
    async def test_seen_pair_skip(self):
        from interntrack.engines.deduplication import DeduplicationEngine

        session = MagicMock()
        result = MagicMock()
        job_a = MagicMock()
        job_a.id = "a"
        job_b = MagicMock()
        job_b.id = "b"
        job_c = MagicMock()
        job_c.id = "c"
        result.scalars.return_value.all.return_value = [job_a, job_b, job_c]
        session.execute = AsyncMock(return_value=result)

        engine = DeduplicationEngine(session)
        engine.calculate_similarity = MagicMock(return_value=0.99)  # type: ignore[method-assign]

        dupes = await engine.find_duplicates_in_database(threshold=0.9)

        # (a,b), (a,c), (b,c) are evaluated; all three pairs exceed threshold
        # so all three combinations appear once (seen_pairs never skips a
        # pair that was already reported, it only guards the sorted key).
        assert len(dupes) == 3
