"""Final coverage push: tests for remaining scrapers, notification service, worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── HackerNews Scraper ─────────────────────────────────────────────────────

class TestHackerNewsScraperExtended:
    """Extended tests for HackerNewsScraper."""

    def test_source_name(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        assert scraper.source_name == "hackernews"

    def test_rate_limit(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        assert scraper.rate_limit == 30

    def test_extract_title_pipe(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        title = scraper._extract_title("TechCorp | Senior Python Developer | Remote")
        assert title is not None
        assert len(title) > 5

    def test_extract_title_hyphen(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        title = scraper._extract_title("TechCorp - Python Developer - NYC")
        assert title is not None

    def test_extract_title_no_match(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        assert scraper._extract_title("short") is None

    def test_extract_company(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        company = scraper._extract_company("TechCorp | Dev | Remote")
        assert company is not None
        assert "TechCorp" in company

    def test_extract_tags(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        tags = scraper._extract_tags("Looking for a senior Python developer with remote work")
        assert "python" in tags
        assert "senior" in tags
        assert "remote" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        tags = scraper._extract_tags("Looking for a general role")
        assert tags == []

    def test_parse_comment_valid(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        comment = {
            "id": 123,
            "text": "TechCorp | Python Developer | Remote<p>Build APIs with Python",
            "time": 1700000000,
        }
        job = scraper._parse_comment(comment, "python")
        assert job is not None
        assert job.title is not None
        assert job.source == "hackernews"

    def test_parse_comment_no_text(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        assert scraper._parse_comment({"id": 1}, "python") is None

    def test_parse_comment_no_match(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()
        comment = {
            "id": 123,
            "text": "TechCorp | Java Developer | Remote<p>Build Java apps",
            "time": 1700000000,
        }
        assert scraper._parse_comment(comment, "python") is None

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_found(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()

        mock_response = MagicMock()
        mock_response.json.return_value = [1, 2, 3]

        story_response = MagicMock()
        story_response.json.return_value = {"title": "Ask HN: Who is hiring?", "id": 2}

        scraper._get = AsyncMock(side_effect=[mock_response, story_response])

        result = await scraper._get_latest_hiring_thread()
        assert result == "1"  # Returns str(story_id) from the list

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_not_found(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        scraper = HackerNewsScraper()

        mock_response = MagicMock()
        mock_response.json.return_value = [1]
        story_response = MagicMock()
        story_response.json.return_value = {"title": "Other thread"}

        scraper._get = AsyncMock(side_effect=[mock_response, story_response])

        result = await scraper._get_latest_hiring_thread()
        assert result is None


# ─── LinkedIn Scraper ──────────────────────────────────────────────────────

class TestLinkedInScraperExtended:
    """Extended tests for LinkedInScraper."""

    def test_source_name(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()
        assert scraper.source_name == "linkedin"

    def test_rate_limit(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()
        assert scraper.rate_limit == 10

    def test_extract_tags(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()
        tags = scraper._extract_tags("Python Developer Remote", "React and AWS experience")
        assert "python" in tags
        assert "react" in tags
        assert "aws" in tags
        assert "remote" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()

        html = """
        <ul>
            <li class="result-card">
                <h3 class="result-card__title">Python Developer</h3>
                <h4 class="result-card__company-name">TechCorp</h4>
                <a class="result-card__full-card-link" href="https://linkedin.com/jobs/123">Link</a>
                <span class="job-result__location">Remote</span>
                <time class="result-card__listed-date" datetime="2026-01-15">Jan 15</time>
                <p class="result-card__snippet">Build APIs</p>
            </li>
        </ul>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("python", limit=5)
        assert len(jobs) == 1
        assert jobs[0].title == "Python Developer"

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        scraper = LinkedInScraper()
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── Indeed Scraper ────────────────────────────────────────────────────────

class TestIndeedScraperExtended:
    """Extended tests for IndeedScraper."""

    def test_source_name(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        assert scraper.source_name == "indeed"

    def test_rate_limit(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        assert scraper.rate_limit == 15

    def test_parse_salary_range(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000 per year")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        min_s, max_s = scraper._parse_salary("$100,000 per year")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_none(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        min_s, max_s = scraper._parse_salary("Competitive salary")
        assert min_s is None
        assert max_s is None

    def test_extract_tags(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        tags = scraper._extract_tags("Senior Python Developer Remote", "Docker and AWS required")
        assert "python" in tags
        assert "senior" in tags
        assert "remote" in tags
        assert "docker" in tags
        assert "aws" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        from interntrack.scrapers.indeed import IndeedScraper
        scraper = IndeedScraper()
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── Glassdoor Scraper ─────────────────────────────────────────────────────

class TestGlassdoorScraperExtended:
    """Extended tests for GlassdoorScraper."""

    def test_source_name(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        assert scraper.source_name == "glassdoor"

    def test_rate_limit(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        assert scraper.rate_limit == 10

    def test_parse_salary_range(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        min_s, max_s = scraper._parse_salary("$80K - $120K")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_full_numbers(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single_k(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        min_s, max_s = scraper._parse_salary("$100K")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_none(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        min_s, max_s = scraper._parse_salary("Competitive")
        assert min_s is None
        assert max_s is None

    def test_extract_tags(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        tags = scraper._extract_tags("Python Developer", "Machine learning experience")
        assert "python" in tags
        assert "ml" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        scraper = GlassdoorScraper()
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── Notification Service ──────────────────────────────────────────────────

class TestNotificationServiceExtended:
    """Extended tests for notification_service.py."""

    def test_notification_manager_init(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        assert manager.get_configured_channels() == []

    def test_notification_manager_with_channels(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = "token"
            mock_settings.telegram_chat_id = "123"
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = "https://discord.com/webhook"
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        channels = manager.get_configured_channels()
        assert "telegram" in channels
        assert "discord" in channels

    @pytest.mark.asyncio
    async def test_notify_channel_not_configured(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        results = await manager.notify(["email"], "test message")
        assert results["email"] is False

    @pytest.mark.asyncio
    async def test_notify_channel_success(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)
        manager._channels["test"] = mock_channel

        results = await manager.notify(["test"], "hello")
        assert results["test"] is True

    @pytest.mark.asyncio
    async def test_notify_channel_exception(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(side_effect=Exception("Error"))
        manager._channels["test"] = mock_channel

        results = await manager.notify(["test"], "hello")
        assert results["test"] is False

    @pytest.mark.asyncio
    async def test_notify_all(self):
        from interntrack.services.notification_service import NotificationManager
        session = AsyncMock()
        with patch("interntrack.services.notification_service.settings") as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)
        manager._channels["telegram"] = mock_channel

        results = await manager.notify_all("hello")
        assert "telegram" in results

    @pytest.mark.asyncio
    async def test_telegram_channel_send(self):
        from interntrack.services.notification_service import TelegramChannel
        channel = TelegramChannel("token", "123")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_discord_channel_send(self):
        from interntrack.services.notification_service import DiscordChannel
        channel = DiscordChannel("https://discord.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_slack_channel_send(self):
        from interntrack.services.notification_service import SlackChannel
        channel = SlackChannel("https://slack.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True


# ─── Worker ─────────────────────────────────────────────────────────────────

class TestWorkerExtended:
    """Extended tests for worker.py."""

    @pytest.mark.asyncio
    async def test_worker_main(self):
        from interntrack.worker import main

        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()

        with (
            patch("interntrack.worker.setup_logging"),
            patch("interntrack.worker.setup_scheduler", return_value=mock_scheduler),
            patch("interntrack.worker.signal"),
            patch("asyncio.sleep", side_effect=KeyboardInterrupt),
        ):
            await main()

        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called_once()
