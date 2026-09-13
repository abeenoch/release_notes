"""Regression tests for the branded changelog email template."""
from app.services.email_template import changelog_email_html
from app.services.notification_service import NotificationService
from types import SimpleNamespace


def test_logo_replaces_r_badge():
    html = changelog_email_html(subject="v1.2.3", markdown="- fix")
    assert ">R</span>" not in html
    assert "rn-grad" in html  # inlined Release Notes icon (favicon.svg copy)
    assert "Release Notes" in html


def test_leading_changelog_heading_not_duplicated():
    md = "# Changelog \u2014 v1.2.3\n\n## Features\n\n- cool thing"
    html = changelog_email_html(subject="v1.2.3", markdown=md)
    # Template H1 renders the version once; the markdown H1 is stripped.
    assert html.count("Changelog \u2014 v1.2.3") == 0
    assert "<h1" in html  # the template's own subject H1 remains
    assert "cool thing" in html


def test_non_changelog_markdown_kept():
    html = changelog_email_html(subject="v1.2.3", markdown="## Features\n\n- x")
    assert "<h2" in html


def test_html_subject_strips_prefix_once():
    svc = NotificationService()
    cfg = SimpleNamespace(subject_prefix=None)
    subject = svc.build_subject(cfg, SimpleNamespace(version="v1.2.3", to_tag="v1.2.3"))
    assert subject == "[Changelog] v1.2.3"
    assert svc.build_html_subject(cfg, subject) == "v1.2.3"


def test_html_subject_custom_prefix():
    svc = NotificationService()
    cfg = SimpleNamespace(subject_prefix="MyApp Releases")
    subject = svc.build_subject(cfg, SimpleNamespace(version="v1.2.3", to_tag="v1.2.3"))
    assert svc.build_html_subject(cfg, subject) == "v1.2.3"
