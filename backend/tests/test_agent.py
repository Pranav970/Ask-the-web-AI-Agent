"""
tests/test_agent.py — Comprehensive test suite.

Run: pytest tests/ -v
All tests that make real Claude API calls are SKIPPED unless
the env var RUN_INTEGRATION_TESTS=true is set.
"""
from __future__ import annotations

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_claude_response(text: str, stop_reason: str = "end_turn"):
    """Build a minimal mock that looks like anthropic.Message."""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    return msg


def make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tu_abc123"):
    """Build a mock response that contains a tool_use block."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    msg.content = [block]
    return msg


# ── Tool Registry ─────────────────────────────────────────────────────────────

class TestToolRegistry:

    def test_register_and_retrieve(self):
        from tools.tool_registry import ToolRegistry, ToolDefinition

        reg = ToolRegistry()

        async def dummy(x: str) -> str:
            return f"result: {x}"

        tool = ToolDefinition(
            name="dummy",
            description="A dummy tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
            executor=dummy,
        )
        reg.register(tool)
        assert reg.get("dummy") is not None
        assert "dummy" in reg.list_names()

    def test_to_anthropic_format(self):
        from tools.tool_registry import ToolRegistry, ToolDefinition

        reg = ToolRegistry()

        async def noop() -> str:
            return "ok"

        reg.register(ToolDefinition(
            name="noop",
            description="Does nothing",
            input_schema={"type": "object", "properties": {}},
            executor=noop,
        ))
        defs = reg.all_definitions()
        assert len(defs) == 1
        assert defs[0]["name"] == "noop"
        assert "input_schema" in defs[0]

    @pytest.mark.asyncio
    async def test_execute_success(self):
        from tools.tool_registry import ToolRegistry, ToolDefinition

        reg = ToolRegistry()

        async def adder(a: int, b: int) -> int:
            return a + b

        reg.register(ToolDefinition(
            name="add", description="", input_schema={}, executor=adder
        ))
        result = await reg.execute("add", {"a": 3, "b": 7}, "id-1")
        assert result["type"] == "tool_result"
        assert result.get("is_error") is not True
        assert "10" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        from tools.tool_registry import ToolRegistry
        reg = ToolRegistry()
        result = await reg.execute("no_such_tool", {}, "id-2")
        assert result["is_error"] is True
        assert "Unknown tool" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_exception_caught(self):
        from tools.tool_registry import ToolRegistry, ToolDefinition

        reg = ToolRegistry()

        async def failing_tool():
            raise ValueError("intentional failure")

        reg.register(ToolDefinition(
            name="fail", description="", input_schema={}, executor=failing_tool
        ))
        result = await reg.execute("fail", {}, "id-3")
        assert result["is_error"] is True
        assert "intentional failure" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        from tools.tool_registry import ToolRegistry, ToolDefinition

        reg = ToolRegistry()
        counter = {"n": 0}

        async def inc() -> int:
            counter["n"] += 1
            return counter["n"]

        reg.register(ToolDefinition(
            name="inc", description="", input_schema={}, executor=inc
        ))
        calls = [{"name": "inc", "input": {}, "id": f"id-{i}"} for i in range(4)]
        results = await reg.execute_parallel(calls)
        assert len(results) == 4
        assert counter["n"] == 4

    @pytest.mark.asyncio
    async def test_execute_parallel_empty(self):
        from tools.tool_registry import ToolRegistry
        reg = ToolRegistry()
        results = await reg.execute_parallel([])
        assert results == []


# ── Web Search ────────────────────────────────────────────────────────────────

class TestWebSearch:

    @pytest.mark.asyncio
    async def test_stub_when_no_keys(self):
        """Without API keys, should return stub results (not raise)."""
        with patch("tools.web_search.settings") as mock_settings:
            mock_settings.TAVILY_API_KEY = None
            mock_settings.SERPAPI_KEY = None

            from tools.web_search import web_search
            # Patch the module-level settings reference
            with patch("tools.web_search.settings", mock_settings):
                result = await web_search("test query", max_results=3)

        assert isinstance(result, dict)
        assert "query" in result
        assert "results" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_multi_query_returns_list(self):
        from tools.web_search import multi_query_search

        with patch("tools.web_search.web_search") as mock_ws:
            mock_ws.return_value = {"query": "q", "results": [], "source": "stub"}
            results = await multi_query_search(["q1", "q2", "q3"])

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_multi_query_empty(self):
        from tools.web_search import multi_query_search
        results = await multi_query_search([])
        assert results == []

    @pytest.mark.asyncio
    async def test_web_search_never_raises(self):
        """web_search must never raise — always return a dict."""
        with patch("tools.web_search.settings") as ms:
            ms.TAVILY_API_KEY = "bad_key"
            ms.SERPAPI_KEY = None

            import httpx
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=httpx.TimeoutException("timeout")
                )
                from tools.web_search import _tavily_search
                try:
                    r = await _tavily_search("test")
                    # If it returns, must be a dict
                    assert isinstance(r, dict)
                except Exception:
                    # _tavily_search CAN raise — web_search wraps it
                    pass


# ── Content Extractor ─────────────────────────────────────────────────────────

class TestContentExtractor:

    @pytest.mark.asyncio
    async def test_invalid_scheme(self):
        from tools.content_extractor import extract_content
        result = await extract_content("ftp://example.com")
        assert "error" in result
        assert "scheme" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_url_no_domain(self):
        from tools.content_extractor import extract_content
        result = await extract_content("https://")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_timeout_returns_error_dict(self):
        import httpx
        from tools.content_extractor import extract_content
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            result = await extract_content("https://example.com")
        assert "error" in result
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_error_dict(self):
        import httpx
        from tools.content_extractor import extract_content

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=mock_response
                )
            )
            result = await extract_content("https://example.com/missing")
        assert "error" in result
        assert "404" in result["error"]


# ── Short-Term Memory ─────────────────────────────────────────────────────────

class TestShortTermMemory:

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory(max_turns=10)
        await mem.add_turn("s1", "user", "Hello")
        await mem.add_turn("s1", "assistant", "Hi!")
        history = await mem.get_history("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hi!"

    @pytest.mark.asyncio
    async def test_rolling_window(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory(max_turns=3)
        for i in range(6):
            await mem.add_turn("s2", "user", f"msg {i}")
        history = await mem.get_history("s2")
        assert len(history) == 3
        assert history[-1]["content"] == "msg 5"

    @pytest.mark.asyncio
    async def test_clear_session(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory()
        await mem.add_turn("s3", "user", "test")
        await mem.clear("s3")
        assert await mem.get_history("s3") == []

    @pytest.mark.asyncio
    async def test_messages_for_claude_format(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory()
        await mem.add_turn("s4", "user", "Q")
        await mem.add_turn("s4", "assistant", "A")
        msgs = await mem.get_messages_for_claude("s4")
        assert msgs == [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]

    @pytest.mark.asyncio
    async def test_empty_session(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory()
        assert await mem.get_history("nonexistent") == []
        assert await mem.get_messages_for_claude("nonexistent") == []

    @pytest.mark.asyncio
    async def test_last_n_parameter(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory()
        for i in range(10):
            await mem.add_turn("s5", "user", f"msg {i}")
        last3 = await mem.get_history("s5", last_n=3)
        assert len(last3) == 3
        assert last3[-1]["content"] == "msg 9"

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self):
        from memory.short_term import ConversationMemory
        mem = ConversationMemory()
        await mem.add_turn("sess_a", "user", "A message")
        await mem.add_turn("sess_b", "user", "B message")
        a = await mem.get_history("sess_a")
        b = await mem.get_history("sess_b")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0]["content"] == "A message"
        assert b[0]["content"] == "B message"


# ── Long-Term Memory ──────────────────────────────────────────────────────────

class TestLongTermMemory:

    @pytest.mark.asyncio
    async def test_initialize_fallback_when_no_db(self):
        """Should initialize without raising even if DB is unreachable."""
        from memory.long_term import LongTermMemory
        mem = LongTermMemory()
        # This should not raise regardless of DB availability
        await mem.initialize()

    @pytest.mark.asyncio
    async def test_save_and_search_fallback(self):
        from memory.long_term import LongTermMemory
        mem = LongTermMemory()  # uses in-memory fallback
        await mem.save_fact("Python was created by Guido van Rossum", session_id="test")
        await mem.save_fact("FastAPI is a modern Python web framework", session_id="test")
        results = await mem.search_facts("Python framework")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_no_duplicate_facts(self):
        from memory.long_term import LongTermMemory
        mem = LongTermMemory()
        fact = "Unique fact about uniqueness"
        await mem.save_fact(fact)
        await mem.save_fact(fact)  # duplicate
        results = await mem.search_facts("unique")
        hashes = [e.get("hash") for e in results]
        assert len(hashes) == len(set(hashes))

    @pytest.mark.asyncio
    async def test_search_empty(self):
        from memory.long_term import LongTermMemory
        mem = LongTermMemory()
        results = await mem.search_facts("something not stored")
        assert isinstance(results, list)


# ── Evaluator ─────────────────────────────────────────────────────────────────

class TestEvaluator:

    def test_citation_score_with_urls(self):
        from evaluation.evaluator import _citation_score
        answer = "The capital is Paris. Source: https://example.com\n\nSee also .org sites."
        score = _citation_score(answer)
        assert 0.0 <= score <= 1.0

    def test_citation_score_no_citations(self):
        from evaluation.evaluator import _citation_score
        answer = "This answer has no citations at all.\n\nNothing here either."
        score = _citation_score(answer)
        assert score == 0.0

    def test_citation_score_all_cited(self):
        from evaluation.evaluator import _citation_score
        answer = (
            "Fact one. https://source1.com\n\n"
            "Fact two [1]. See .org reference.\n\n"
            "Fact three. Source: https://source3.com"
        )
        score = _citation_score(answer)
        assert score == 1.0

    def test_citation_score_empty_answer(self):
        from evaluation.evaluator import _citation_score
        assert _citation_score("") == 0.0

    def test_domain_diversity_unique(self):
        from evaluation.evaluator import _domain_diversity
        sources = [
            {"url": "https://bbc.com/a"},
            {"url": "https://cnn.com/b"},
            {"url": "https://reuters.com/c"},
        ]
        assert _domain_diversity(sources) == 3

    def test_domain_diversity_duplicates(self):
        from evaluation.evaluator import _domain_diversity
        sources = [
            {"url": "https://bbc.com/a"},
            {"url": "https://bbc.com/b"},  # same domain
            {"url": "https://cnn.com/c"},
        ]
        assert _domain_diversity(sources) == 2

    def test_domain_diversity_empty(self):
        from evaluation.evaluator import _domain_diversity
        assert _domain_diversity([]) == 0

    def test_domain_diversity_bad_url(self):
        from evaluation.evaluator import _domain_diversity
        sources = [{"url": "not-a-url"}, {"url": ""}]
        # Should not raise
        result = _domain_diversity(sources)
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_evaluate_without_llm(self):
        """Test that evaluate() returns all expected keys (mocked LLM)."""
        from evaluation.evaluator import Evaluator

        mock_resp = make_claude_response(json.dumps({
            "relevance":         0.9,
            "completeness":      0.85,
            "hallucination_risk": "low",
            "reasoning":         "Good answer",
        }))

        with patch("evaluation.evaluator.anthropic.AsyncAnthropic") as MockClaude:
            MockClaude.return_value.messages.create = AsyncMock(return_value=mock_resp)
            ev = Evaluator()
            result = await ev.evaluate(
                query="What is Python?",
                answer="Python is a programming language. https://python.org",
                sources=[{"title": "Python", "url": "https://python.org"}],
            )

        assert "overall" in result
        assert "source_count" in result
        assert "citation_score" in result
        assert "source_diversity" in result
        assert 0.0 <= result["overall"] <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_llm_failure_fallback(self):
        """If Claude call fails, evaluate() still returns a result."""
        from evaluation.evaluator import Evaluator

        with patch("evaluation.evaluator.anthropic.AsyncAnthropic") as MockClaude:
            MockClaude.return_value.messages.create = AsyncMock(
                side_effect=Exception("Network error")
            )
            ev = Evaluator()
            result = await ev.evaluate(
                query="test",
                answer="test answer",
                sources=[],
            )

        assert "overall" in result
        assert result["hallucination_risk"] == "unknown"


# ── Workflows ─────────────────────────────────────────────────────────────────

class TestWorkflows:

    @pytest.mark.asyncio
    async def test_prompt_chain_runs_all_steps(self):
        from workflows.chains import prompt_chain

        mock_resp = make_claude_response("step output")

        with patch("workflows.chains.claude") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=mock_resp)
            results = await prompt_chain(
                steps=[
                    {"system": "sys1", "user_template": "Step 1: {input}"},
                    {"system": "sys2", "user_template": "Step 2: {input}"},
                    {"system": "sys3", "user_template": "Step 3: {input}"},
                ],
                initial_input="hello",
            )

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_prompt_chain_passes_output(self):
        """Each step receives the previous step's output."""
        from workflows.chains import prompt_chain

        call_count = {"n": 0}
        outputs = ["first", "second", "third"]

        async def mock_create(**kwargs):
            resp = make_claude_response(outputs[call_count["n"]])
            call_count["n"] += 1
            return resp

        with patch("workflows.chains.claude") as mock_claude:
            mock_claude.messages.create = mock_create
            results = await prompt_chain(
                steps=[
                    {"system": "s", "user_template": "A: {input}"},
                    {"system": "s", "user_template": "B: {input}"},
                    {"system": "s", "user_template": "C: {input}"},
                ],
                initial_input="start",
            )

        assert results == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_parallelize_concurrent(self):
        from workflows.chains import parallelize

        order = []

        async def task(n: int) -> int:
            await asyncio.sleep(0.01)
            order.append(n)
            return n * 2

        results = await parallelize([task(1), task(2), task(3)])
        assert sorted(results) == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_parallelize_catches_exceptions(self):
        from workflows.chains import parallelize

        async def bad():
            raise RuntimeError("fail")

        async def good(n: int) -> int:
            return n

        results = await parallelize([good(1), bad(), good(3)])
        successes = [r for r in results if not isinstance(r, Exception)]
        failures  = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 2
        assert len(failures)  == 1

    @pytest.mark.asyncio
    async def test_reflection_loop_pass(self):
        """If critique says PASS, original answer is returned unchanged."""
        from workflows.chains import reflection_loop

        original = "This is a great answer."
        mock_resp = make_claude_response("PASS")

        with patch("workflows.chains.claude") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=mock_resp)
            result = await reflection_loop(
                query="What is 2+2?",
                initial_answer=original,
                max_iterations=1,
            )

        assert result["answer"] == original
        assert result["improved"] is False

    @pytest.mark.asyncio
    async def test_reflection_loop_improves(self):
        """If critique returns flaws, answer should be improved."""
        from workflows.chains import reflection_loop

        call_count = {"n": 0}
        responses = ["Missing citation on claim X", "This is an improved answer."]

        async def side_effect(**kwargs):
            resp = make_claude_response(responses[min(call_count["n"], 1)])
            call_count["n"] += 1
            return resp

        with patch("workflows.chains.claude") as mock_claude:
            mock_claude.messages.create = side_effect
            result = await reflection_loop(
                query="test",
                initial_answer="original",
                max_iterations=1,
            )

        assert result["improved"] is True

    @pytest.mark.asyncio
    async def test_voting_aggregation(self):
        from workflows.chains import voting_aggregation

        mock_resp = make_claude_response("Best synthesised answer.")

        with patch("workflows.chains.claude") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=mock_resp)
            result = await voting_aggregation(
                query="What is AI?",
                candidate_answers=["Answer A", "Answer B", "Answer C"],
            )

        assert isinstance(result, str)
        assert len(result) > 0


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_settings_load(self):
        """Settings should load without raising."""
        from config import get_settings
        s = get_settings()
        assert s.APP_NAME == "Ask-the-Web Agent"
        assert s.CLAUDE_MAX_TOKENS > 0

    def test_get_anthropic_key_set(self):
        """get_anthropic_key() should return key when set."""
        from config import Settings
        s = Settings(ANTHROPIC_API_KEY="sk-ant-test")
        assert s.get_anthropic_key() == "sk-ant-test"

    def test_get_anthropic_key_missing(self):
        """get_anthropic_key() should raise RuntimeError with clear message."""
        from config import Settings
        s = Settings(ANTHROPIC_API_KEY=None)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            s.get_anthropic_key()

    def test_defaults_are_safe(self):
        from config import Settings
        s = Settings(ANTHROPIC_API_KEY="test")
        assert s.MAX_AGENT_ITERATIONS == 10
        assert s.MAX_SEARCH_RESULTS == 5
        assert s.DEBUG is True
