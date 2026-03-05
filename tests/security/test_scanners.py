"""Security scanner tests — dedicated test suite for all security scanners."""

from __future__ import annotations

from octoauthor.core.security import content, pii, sanitizer, unicode, urls, validator
from octoauthor.core.security.engine import validate_content
from octoauthor.core.security.models import FindingSeverity


class TestSanitizer:
    def test_clean_content(self) -> None:
        assert sanitizer.scan("# Hello\n\n1. Click **Save**") == []

    def test_detects_script_tag(self) -> None:
        findings = sanitizer.scan('<script>alert("xss")</script>')
        assert len(findings) >= 1
        assert findings[0].severity == FindingSeverity.CRITICAL
        assert findings[0].category == "sanitizer"

    def test_detects_iframe(self) -> None:
        findings = sanitizer.scan('<iframe src="evil.com">')
        assert len(findings) >= 1

    def test_detects_event_handler(self) -> None:
        findings = sanitizer.scan('<img onerror="alert(1)" src="x">')
        assert len(findings) >= 1
        assert findings[0].severity == FindingSeverity.CRITICAL

    def test_detects_javascript_uri(self) -> None:
        findings = sanitizer.scan('[link](javascript:alert(1))')
        assert len(findings) >= 1


class TestUnicode:
    def test_clean_content(self) -> None:
        assert unicode.scan("Normal text with no hidden chars") == []

    def test_detects_zero_width_space(self) -> None:
        findings = unicode.scan("Hello\u200bWorld")
        assert len(findings) >= 1
        assert findings[0].category == "unicode"

    def test_detects_rtl_override(self) -> None:
        findings = unicode.scan("normal\u202eesrever")
        assert len(findings) >= 1
        assert any(f.severity == FindingSeverity.CRITICAL for f in findings)

    def test_detects_bom(self) -> None:
        findings = unicode.scan("\ufeffContent with BOM")
        assert len(findings) >= 1


class TestPII:
    def test_clean_content(self) -> None:
        assert pii.scan("Click **Save** to continue") == []

    def test_detects_email(self) -> None:
        findings = pii.scan("Contact john.doe@company.com for help")
        assert len(findings) >= 1
        assert findings[0].category == "pii"
        assert "Email" in findings[0].message

    def test_excludes_example_emails(self) -> None:
        assert pii.scan("Send to user@example.com") == []
        assert pii.scan("From noreply@service.com") == []
        assert pii.scan("Use demo@test.com") == []

    def test_detects_phone(self) -> None:
        findings = pii.scan("Call us at (555) 123-4567")
        assert len(findings) >= 1
        assert "Phone" in findings[0].message

    def test_detects_ssn(self) -> None:
        findings = pii.scan("SSN: 123-45-6789")
        assert len(findings) >= 1
        assert findings[0].severity == FindingSeverity.CRITICAL

    def test_detects_api_key(self) -> None:
        findings = pii.scan("Authorization: sk-1234567890abcdefghijklmnop")
        assert len(findings) >= 1
        assert findings[0].severity == FindingSeverity.CRITICAL

    def test_detects_aws_key(self) -> None:
        findings = pii.scan("AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        assert len(findings) >= 1

    def test_detects_github_token(self) -> None:
        findings = pii.scan("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcd")
        assert len(findings) >= 1


class TestContent:
    def test_clean_content(self) -> None:
        assert content.scan("1. Click **Save**\n2. Enter the `Name`") == []

    def test_detects_code_blocks(self) -> None:
        findings = content.scan("```python\nprint('hello')\n```")
        assert len(findings) >= 1

    def test_detects_terminal_commands(self) -> None:
        findings = content.scan("Run: pip install octoauthor")
        assert len(findings) >= 1

    def test_detects_wrong_voice(self) -> None:
        findings = content.scan("You should click the button")
        assert len(findings) >= 1

    def test_detects_placeholder(self) -> None:
        findings = content.scan("This section is TODO")
        assert len(findings) >= 1

    def test_detects_lorem_ipsum(self) -> None:
        findings = content.scan("Lorem ipsum dolor sit amet")
        assert len(findings) >= 1


class TestURLChecker:
    def test_no_urls(self) -> None:
        assert urls.scan("Click **Save** to continue") == []

    def test_flags_unlisted_domain(self) -> None:
        findings = urls.scan("Visit https://evil.com/phish", allowlist=["example.com"])
        assert len(findings) >= 1
        assert findings[0].category == "urls"

    def test_allows_listed_domain(self) -> None:
        findings = urls.scan("See https://docs.example.com/guide", allowlist=["example.com"])
        assert len(findings) == 0

    def test_no_allowlist_no_findings(self) -> None:
        findings = urls.scan("Visit https://any-site.com")
        assert len(findings) == 0


class TestDocStandardValidator:
    def test_valid_doc(self) -> None:
        doc = (
            "---\ntag: test-doc\ntitle: Test\nversion: '1.0'\nlast_updated: '2026-03-05'\n"
            "applies_to: [app]\nroute: /test\ngenerated_by: octoauthor\ncategory: features\n---\n\n"
            "1. Click **Save**\n2. Enter the name"
        )
        findings = validator.scan(doc)
        assert len(findings) == 0

    def test_missing_frontmatter(self) -> None:
        findings = validator.scan("# Just markdown\n\nNo frontmatter here")
        assert len(findings) >= 1
        assert any("frontmatter" in f.message.lower() for f in findings)

    def test_missing_required_fields(self) -> None:
        doc = "---\ntag: test\n---\n\nContent"
        findings = validator.scan(doc)
        missing_fields = [f for f in findings if "Missing required" in f.message]
        assert len(missing_fields) >= 4  # title, version, last_updated, etc.

    def test_invalid_tag_format(self) -> None:
        doc = (
            "---\ntag: InvalidTag\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\n---\n\nContent"
        )
        findings = validator.scan(doc)
        assert any("Tag format" in f.message for f in findings)

    def test_too_many_steps(self) -> None:
        steps = "\n".join(f"{i}. Step {i}" for i in range(1, 15))
        doc = (
            "---\ntag: test\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            f"applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\n---\n\n{steps}"
        )
        findings = validator.scan(doc)
        assert any("Too many steps" in f.message for f in findings)


class TestValidationEngine:
    def test_clean_doc_passes(self) -> None:
        doc = (
            "---\ntag: test-doc\ntitle: Test\nversion: '1.0'\nlast_updated: '2026-03-05'\n"
            "applies_to: [app]\nroute: /test\ngenerated_by: octoauthor\n---\n\n"
            "1. Click **Save**"
        )
        result = validate_content(doc, "test.md")
        assert result.passed is True
        assert len(result.scanners_run) == 6

    def test_xss_detected(self) -> None:
        doc = (
            "---\ntag: test\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\n---\n\n"
            '<script>alert("xss")</script>'
        )
        result = validate_content(doc, "test.md")
        assert result.passed is False
        assert any(f.category == "sanitizer" for f in result.findings)

    def test_skip_scanners(self) -> None:
        result = validate_content("no frontmatter", skip_scanners={"doc-standard"})
        assert "doc-standard" not in result.scanners_run
        assert "sanitizer" in result.scanners_run

    def test_pii_in_doc(self) -> None:
        doc = (
            "---\ntag: test\ntitle: T\nversion: '1'\nlast_updated: '2026-01-01'\n"
            "applies_to: [a]\nroute: /t\ngenerated_by: octoauthor\n---\n\n"
            "Contact john.doe@realcompany.org"
        )
        result = validate_content(doc, "test.md")
        assert result.passed is False
        assert any(f.category == "pii" for f in result.findings)
