from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from mcp.types import CallToolResult

from pyslang_mcp.cache import AnalysisCache
from pyslang_mcp.server import create_server

FIXTURES = Path(__file__).parent / "fixtures"


def _call_tool_json(tool_name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    server = create_server(cache=AnalysisCache())

    async def run() -> tuple[dict[str, Any], bool]:
        result = await server.call_tool(tool_name, arguments)
        assert isinstance(result, CallToolResult)
        assert result.structuredContent is not None
        structured = cast(dict[str, Any], result.structuredContent)
        if "result" in structured and isinstance(structured["result"], dict):
            return cast(dict[str, Any], structured["result"]), bool(result.isError)
        return structured, bool(result.isError)

    return asyncio.run(run())


def test_tools_list_exposes_output_schema() -> None:
    server = create_server(cache=AnalysisCache())

    async def run() -> dict[str, Any]:
        tools = await server.list_tools()
        parse_files = next(tool for tool in tools if tool.name == "parse_files")
        assert parse_files.outputSchema is not None
        return cast(dict[str, Any], parse_files.outputSchema)

    output_schema = asyncio.run(run())
    assert "result" in output_schema["properties"]
    result_schema = output_schema["properties"]["result"]
    assert any(entry["$ref"].endswith("ParseFilesResult") for entry in result_schema["anyOf"])


def test_parse_filelist_tool() -> None:
    payload, is_error = _call_tool_json(
        "parse_filelist",
        {
            "project_root": str(FIXTURES / "multi_file"),
            "filelist": "project.f",
        },
    )

    assert not is_error
    assert payload["project_status"]["status"] == "ok"
    assert payload["parse"]["file_count"] == 3
    assert payload["filelist"]["filelists"] == ["project.f", "rtl.f"]


def test_get_hierarchy_tool() -> None:
    payload, is_error = _call_tool_json(
        "get_hierarchy",
        {
            "project_root": str(FIXTURES / "multi_file"),
            "filelist": "project.f",
        },
    )

    assert not is_error
    assert payload["summary"]["total_instances"] == 2
    assert payload["hierarchy"][0]["children"][0]["name"] == "u_child"


def test_describe_design_unit_not_found_is_not_a_protocol_error() -> None:
    payload, is_error = _call_tool_json(
        "describe_design_unit",
        {
            "project_root": str(FIXTURES / "multi_file"),
            "filelist": "project.f",
            "name": "missing_top",
        },
    )

    assert not is_error
    assert payload["found"] is False
    assert payload["design_unit"] is None


def test_invalid_argument_combo_returns_structured_tool_error() -> None:
    payload, is_error = _call_tool_json(
        "get_diagnostics",
        {
            "project_root": str(FIXTURES / "multi_file"),
            "files": ["top.sv"],
            "filelist": "project.f",
        },
    )

    assert is_error
    assert payload["error"]["code"] == "invalid_arguments"


def test_get_diagnostics_reports_incomplete_project_status() -> None:
    payload, is_error = _call_tool_json(
        "get_diagnostics",
        {
            "project_root": str(FIXTURES / "broken"),
            "files": ["broken.sv"],
        },
    )

    assert not is_error
    assert payload["project_status"]["status"] == "incomplete"
    assert payload["project_status"]["unresolved_references"] >= 1
