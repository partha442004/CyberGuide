"""Unit tests for email deliverability (From fallback + header hygiene)."""

from unittest.mock import MagicMock, patch

import pytest


class TestDeliverableFromEmail:
    """The From sanitizer must never send From a non-routable domain."""

    def test_keeps_valid_from(self):
        from interntrack.utils.helpers import deliverable_from_email

        assert (
            deliverable_from_email("Alerts <alerts@cyberguide.app>", "me@gmail.com")
            == "Alerts <alerts@cyberguide.app>"
        )
        assert deliverable_from_email("me@gmail.com", None) == "me@gmail.com"

    def test_falls_back_from_local_domain(self):
        from interntrack.utils.helpers import deliverable_from_email

        # The old config default — .local is non-routable → falls back to the
        # authenticated SMTP account whose domain has real SPF/DKIM records.
        assert (
            deliverable_from_email(
                "InternTrack <noreply@interntrack.local>", "me@gmail.com"
            )
            == "InternTrack <me@gmail.com>"
        )

    def test_falls_back_from_missing(self):
        from interntrack.utils.helpers import deliverable_from_email

        assert (
            deliverable_from_email(None, "me@gmail.com") == "InternTrack <me@gmail.com>"
        )
        assert deliverable_from_email("", None) == "InternTrack"

    def test_settings_effective_email_from(self):
        from interntrack.config import Settings

        s = Settings(
            email_from="InternTrack <noreply@interntrack.local>",
            smtp_user="me@gmail.com",
        )
        assert s.effective_email_from == "InternTrack <me@gmail.com>"

        s2 = Settings(
            email_from="Alerts <alerts@cyberguide.app>", smtp_user="me@gmail.com"
        )
        assert s2.effective_email_from == "Alerts <alerts@cyberguide.app>"

    def test_real_domains_with_test_or_local_label_are_kept(self):
        """Whole-label matching: never false-positive on legit domains."""
        from interntrack.utils.helpers import deliverable_from_email

        # ``.testing`` / ``.localdomain`` are real label substrings but not
        # the reserved ``.test`` / ``.local`` TLDs — must NOT fall back.
        assert (
            deliverable_from_email("A <a@myapp.testing.com>", "me@gmail.com")
            == "A <a@myapp.testing.com>"
        )
        assert (
            deliverable_from_email("A <a@foo.localdomain.com>", "me@gmail.com")
            == "A <a@foo.localdomain.com>"
        )
        # The actual reserved TLDs still fall back.
        assert (
            deliverable_from_email("A <a@x.test>", "me@gmail.com")
            == "InternTrack <me@gmail.com>"
        )
        assert (
            deliverable_from_email("A <a@x.local>", "me@gmail.com")
            == "InternTrack <me@gmail.com>"
        )

    def test_html_to_text_keeps_links(self):
        from interntrack.utils.helpers import html_to_text

        text = html_to_text(
            '<p>Apply here: <a href="https://in.indeed.com/viewjob?jk=abc">'
            "Apply now</a></p>"
        )
        assert "Apply now (https://in.indeed.com/viewjob?jk=abc)" in text


class TestEmailChannelHeaders:
    """EmailChannel.send must emit spam-hygiene headers + text alternative."""

    @pytest.fixture
    def sent_msg(self):
        """Build and send a message through EmailChannel (patched SMTP)."""
        sent = {}

        async def _do_send(
            from_email="Alerts <alerts@cyberguide.app>",
            user="me@gmail.com",
        ):
            from interntrack.services.notification_service import EmailChannel

            channel = EmailChannel(
                "smtp.gmail.com", 587, user, "pass", from_email, to_email="u@x.com"
            )
            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
                mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
                await channel.send("<p>Hello <b>world</b></p>", subject="Digest")
                sent["msg"] = mock_server.send_message.call_args.args[0]

        sent["do"] = _do_send
        return sent

    @pytest.mark.asyncio
    async def test_has_spam_hygiene_headers(self, sent_msg):
        await sent_msg["do"]()
        msg = sent_msg["msg"]
        assert msg["Date"]
        assert msg["Message-ID"].startswith("<")
        assert msg["Message-ID"].endswith("@cyberguide.app>")
        assert "mailto:me@gmail.com" in (msg["List-Unsubscribe"] or "")
        assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert msg["Precedence"] == "bulk"
        assert msg["Auto-Submitted"] == "auto-generated"

    @pytest.mark.asyncio
    async def test_has_plain_text_alternative(self, sent_msg):
        await sent_msg["do"]()
        msg = sent_msg["msg"]
        parts = [p.get_payload(decode=True).decode("utf-8") for p in msg.get_payload()]
        assert len(parts) == 2
        assert "Hello world" in parts[0]  # stripped of tags
        assert "<b>world</b>" in parts[1]  # HTML preserved

    @pytest.mark.asyncio
    async def test_local_from_is_replaced_in_init(self, sent_msg):
        await sent_msg["do"](from_email="InternTrack <noreply@interntrack.local>")
        msg = sent_msg["msg"]
        assert msg["From"] == "InternTrack <me@gmail.com>"
