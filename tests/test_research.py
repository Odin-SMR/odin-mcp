"""Offline content and MCP protocol tests; never query the observation archive."""

import json

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from odin_mcp.research import (
    MAX_SNIPPET_LENGTH,
    get_research_topic,
    research_catalog,
    research_sources,
    search_research_guidance,
)
from odin_mcp.server import mcp


def test_catalog_resolves_all_content_and_sources():
    catalog = research_catalog()
    sources = research_sources()
    source_ids = [source["id"] for source in sources["sources"]]
    assert len(source_ids) == len(set(source_ids))
    assert sources["checked_on"]
    assert len(catalog["topics"]) >= 8
    for topic in catalog["topics"]:
        result = get_research_topic(topic["id"])
        assert result["markdown"].startswith("# ")
        assert result["source_ids"]
        assert set(result["source_ids"]) <= set(source_ids)
        assert result["sources"]
        assert result["uri"] == f"odin://research/topics/{topic['id']}"


@pytest.mark.parametrize("topic_id", ["", "../README", "%2e%2e/README", "/etc/passwd", "made-up-topic"])
def test_topic_rejects_unknown_and_path_input(topic_id):
    with pytest.raises(ValueError):
        get_research_topic(topic_id)


@pytest.mark.parametrize("query", ["", "  \n ", "!!!", "a" * 501])
def test_search_rejects_unusable_queries(query):
    with pytest.raises(ValueError):
        search_research_guidance(query)


@pytest.mark.parametrize("limit", [0, -1, 9, True, 1.5, "2"])
def test_search_rejects_invalid_limits(limit):
    with pytest.raises(ValueError):
        search_research_guidance("ozone", limit)


def test_search_is_bounded_deterministic_and_understands_subscripts():
    first = search_research_guidance("averaging kernel", limit=2)
    assert first == search_research_guidance("averaging kernel", limit=2)
    assert 1 <= len(first["results"]) <= 2
    for result in first["results"]:
        assert len(result["snippet"]) <= MAX_SNIPPET_LENGTH
        assert result["sources"]
    ascii_results = search_research_guidance("N2O")["results"]
    assert ascii_results
    assert ascii_results == search_research_guidance("N₂O")["results"]
    assert search_research_guidance("zzzxxyyunknownword")["results"] == []


def test_species_search_does_not_match_inside_unrelated_words(monkeypatch):
    from odin_mcp import research

    topics = [
        {"id": "comparison", "title": "Comparison coordinates", "summary": "Noise and nocturnal conditions", "keywords": ["columns"], "file": "comparison.md", "source_ids": ["reference"]},
        {"id": "molecules", "title": "CO and NO profiles", "summary": "Carbon monoxide and nitric oxide", "keywords": ["species"], "file": "molecules.md", "source_ids": ["reference"]},
    ]
    monkeypatch.setattr(research, "research_catalog", lambda: {"version": "test", "topics": topics})
    monkeypatch.setattr(research, "research_sources", lambda: {"sources": [{"id": "reference"}]})
    monkeypatch.setattr(research, "_read", lambda filename: "Compare coordinates and noise.\n\nCO and NO." if filename == "molecules.md" else "Compare coordinates and noise.")
    for species in ("CO", "NO"):
        results = research.search_research_guidance(species)["results"]
        assert [result["id"] for result in results] == ["molecules"]
        assert results[0]["snippet"] == "CO and NO."


def _payload(result):
    assert not result.isError
    return result.structuredContent or json.loads(result.content[0].text)


def test_offline_mcp_protocol(monkeypatch):
    """Exercise discovery, reads, calls and prompt rendering through MCP messages."""
    def deny_io(*args, **kwargs):
        raise AssertionError("Knowledge requests must not open network/archive connections")

    monkeypatch.setattr("odin_mcp.s3_browser._client", deny_io)
    monkeypatch.setattr("odin_mcp.parquet_reader._read_single_file", deny_io)

    async def exercise():
        async with create_connected_server_and_client_session(mcp) as session:
            resources = await session.list_resources()
            resource_uris = {str(resource.uri) for resource in resources.resources}
            assert {"odin://research/guide", "odin://research/catalog", "odin://research/sources"} <= resource_uris
            assert "odin://dataset/schema" in resource_uris
            templates = await session.list_resource_templates()
            assert "odin://research/topics/{topic_id}" in {template.uriTemplate for template in templates.resourceTemplates}

            catalog = await session.read_resource("odin://research/catalog")
            assert json.loads(catalog.contents[0].text)["topics"]
            guide = await session.read_resource("odin://research/guide")
            assert guide.contents[0].mimeType == "text/markdown"
            assert guide.contents[0].text == get_research_topic("overview")["markdown"]
            topic = await session.read_resource("odin://research/topics/odin-contract")
            assert topic.contents[0].text == get_research_topic("odin-contract")["markdown"]
            bibliography = await session.read_resource("odin://research/sources")
            assert json.loads(bibliography.contents[0].text)["sources"]

            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert {"list_research_topics_tool", "get_research_topic_tool", "search_research_guidance_tool"} <= tool_names
            assert {"list_partition_values_tool", "list_parquet_files_tool", "read_parquet_preview_tool", "read_parquet_columns_tool"} <= tool_names
            listed = _payload(await session.call_tool("list_research_topics_tool", {}))
            assert listed["ok"] and listed["data"]["topics"]
            found = _payload(await session.call_tool("search_research_guidance_tool", {"query": "averaging kernel", "limit": 2}))
            assert found["ok"] and found["data"]["results"]
            read = _payload(await session.call_tool("get_research_topic_tool", {"topic_id": "quality-screening"}))
            assert read["ok"] and read["data"]["markdown"]
            for args in ({"topic_id": "../README"}, {"topic_id": "unknown-topic"}):
                assert not _payload(await session.call_tool("get_research_topic_tool", args))["ok"]
            for args in ({"query": " "}, {"query": "ozone", "limit": 9}):
                assert not _payload(await session.call_tool("search_research_guidance_tool", args))["ok"]
            malformed = await session.call_tool("search_research_guidance_tool", {"query": [], "limit": "wrong"})
            assert malformed.isError
            for invalid_limit in (True, "2", 1.5):
                malformed = await session.call_tool("search_research_guidance_tool", {"query": "ozone", "limit": invalid_limit})
                assert malformed.isError

            prompts = await session.list_prompts()
            assert "plan_odin_analysis" in {prompt.name for prompt in prompts.prompts}
            prompt = await session.get_prompt("plan_odin_analysis", {"question": "How does N₂O vary seasonally?", "product": "N2O"})
            text = prompt.messages[0].content.text
            assert "How does N₂O vary seasonally?" in text
            assert "do not perform numerical analysis" in text
            assert "linear versus log" in text
            assert "thresholds must not be invented" in text

    anyio.run(exercise)
