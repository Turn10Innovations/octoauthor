"""Tests for the doc-writer MCP server."""

from __future__ import annotations

import pytest

from octoauthor.mcp_servers.doc_writer.config import DocWriterConfig
from octoauthor.mcp_servers.doc_writer.models import (
    GenerateGuideInput,
    GenerateGuideResult,
    RewriteSectionInput,
    ValidateContentResult,
)
from octoauthor.mcp_servers.doc_writer.prompts import SYSTEM_PROMPT, build_generate_prompt, build_rewrite_prompt
from octoauthor.mcp_servers.doc_writer.tools import generate_guide, rewrite_section, validate_content


class TestDocWriterConfig:
    def test_defaults(self) -> None:
        config = DocWriterConfig()
        assert config.max_steps_per_guide == 10
        assert config.max_guide_length_words == 1500


class TestModels:
    def test_generate_guide_input(self) -> None:
        inp = GenerateGuideInput(
            tag="company-maintenance",
            title="Company Management",
            route="/companies",
            version="1.0.0",
            applies_to=["octohub-core"],
        )
        assert inp.screenshots == []
        assert inp.category == "general"

    def test_generate_guide_result(self) -> None:
        result = GenerateGuideResult(
            tag="test",
            title="Test",
            content_markdown="# Test\n\n1. Step one",
            step_count=1,
            word_count=5,
            provider_used="ollama",
            model_used="qwen3:32b",
        )
        assert result.step_count == 1

    def test_validate_content_result(self) -> None:
        result = ValidateContentResult(valid=True, issues=[])
        assert result.valid is True


class TestPrompts:
    def test_system_prompt_has_rules(self) -> None:
        formatted = SYSTEM_PROMPT.format(max_steps=10)
        assert "imperative voice" in formatted.lower()
        assert "10" in formatted

    def test_generate_prompt_basic(self) -> None:
        inp = GenerateGuideInput(
            tag="test",
            title="Test Guide",
            route="/test",
            version="1.0",
            applies_to=["app"],
        )
        prompt = build_generate_prompt(inp)
        assert "Test Guide" in prompt
        assert "/test" in prompt

    def test_generate_prompt_with_context(self) -> None:
        inp = GenerateGuideInput(
            tag="test",
            title="Test",
            route="/test",
            version="1.0",
            applies_to=["app"],
            dom_summary="A table with company names",
            form_fields=["Company Name", "Email"],
            screenshots=["test-01.png", "test-02.png"],
        )
        prompt = build_generate_prompt(inp)
        assert "Company Name" in prompt
        assert "test-01.png" in prompt
        assert "table with company" in prompt

    def test_rewrite_prompt(self) -> None:
        inp = RewriteSectionInput(
            content_markdown="# Guide\n\n1. Old step",
            section_name="steps",
            instructions="make clearer",
        )
        prompt = build_rewrite_prompt(inp)
        assert "steps" in prompt
        assert "make clearer" in prompt


class TestValidateContent:
    def test_valid_content(self) -> None:
        content = (
            "## Overview\n\nThis guide shows how to manage companies.\n\n"
            "1. Click **Add Company**\n2. Enter the `Company Name`\n3. Click **Save**"
        )
        config = DocWriterConfig()
        result = validate_content(content, config)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_too_many_steps(self) -> None:
        steps = "\n".join(f"{i}. Step {i}" for i in range(1, 15))
        config = DocWriterConfig(max_steps_per_guide=10)
        result = validate_content(steps, config)
        assert result["valid"] is False
        assert any("Step count" in i for i in result["issues"])

    def test_code_blocks_prohibited(self) -> None:
        content = "1. Run:\n```bash\npip install foo\n```"
        config = DocWriterConfig()
        result = validate_content(content, config)
        assert result["valid"] is False
        assert any("Code blocks" in i for i in result["issues"])

    def test_wrong_voice(self) -> None:
        content = "1. You should click the Save button"
        config = DocWriterConfig()
        result = validate_content(content, config)
        assert result["valid"] is False
        assert any("imperative" in i for i in result["issues"])

    def test_placeholder_text(self) -> None:
        content = "1. Click TODO"
        config = DocWriterConfig()
        result = validate_content(content, config)
        assert result["valid"] is False
        assert any("TODO" in i for i in result["issues"])


class TestGenerateGuide:
    @pytest.mark.asyncio
    async def test_generate_guide_with_mock(self, mock_provider_factory) -> None:  # type: ignore[no-untyped-def]
        mock_response = (
            "## Overview\n\nManage your companies.\n\n## Prerequisites\n\nNone\n\n"
            "## Steps\n\n1. Click **Companies** in the sidebar\n2. Click **Add Company**\n3. Click **Save**"
        )
        provider = mock_provider_factory(response_text=mock_response)
        config = DocWriterConfig()

        result = await generate_guide(
            provider,
            config,
            tag="company-maintenance",
            title="Company Management",
            route="/companies",
            version="1.0.0",
            applies_to=["octohub-core"],
        )

        assert result["tag"] == "company-maintenance"
        assert result["step_count"] == 3
        assert result["word_count"] > 0
        assert "Companies" in result["content_markdown"]
        # Verify the provider was called
        assert len(provider.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_rewrite_section_with_mock(self, mock_provider_factory) -> None:  # type: ignore[no-untyped-def]
        provider = mock_provider_factory(response_text="## Steps\n\n1. Improved step")
        config = DocWriterConfig()

        result = await rewrite_section(
            provider,
            config,
            content_markdown="## Steps\n\n1. Old step",
            section_name="steps",
            instructions="improve clarity",
        )

        assert result["section_changed"] == "steps"
        assert "Improved" in result["content_markdown"]
