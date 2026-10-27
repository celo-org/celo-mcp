"""The README's tool list must match what the server actually registers.

The README documented seven tools that list_tools() did not register, and left
out one it did. Nothing compared the two, so the gap survived a year. This test
is that comparison: tool names, and each tool's parameter names.
"""

import re
from pathlib import Path

import pytest

from celo_mcp.server import TOOL_HANDLERS, list_tools

README = Path(__file__).resolve().parents[1] / "README.md"

_ENTRY = re.compile(r"^\d+\. \*\*(?P<name>[a-z_]+)\*\*\s*$")
_PARAM = re.compile(r"`([a-z_][a-z0-9_]*)`")


def _readme_tools() -> dict[str, set[str]]:
    """Parse the Available Tools section into {tool name: parameter names}."""
    text = README.read_text()
    start = text.index("### Available Tools\n")
    end = text.index("\n### ", start + 1)
    section = text[start:end].splitlines()

    tools: dict[str, set[str]] = {}
    order: list[str] = []
    current = None
    for line in section:
        entry = _ENTRY.match(line.strip())
        if entry:
            current = entry["name"]
            order.append(current)
            tools[current] = set()
            continue
        stripped = line.strip()
        if current and stripped.startswith("- Parameters:"):
            tools[current] = set(_PARAM.findall(stripped))

    assert len(order) == len(set(order)), "a tool is documented twice"
    return tools


@pytest.fixture(scope="module")
def documented():
    return _readme_tools()


@pytest.fixture
async def registered():
    return {tool.name: tool for tool in await list_tools()}


async def test_readme_documents_exactly_the_registered_tools(documented, registered):
    only_in_readme = sorted(set(documented) - set(registered))
    only_registered = sorted(set(registered) - set(documented))

    assert only_in_readme == [], f"documented but not registered: {only_in_readme}"
    assert only_registered == [], f"registered but not documented: {only_registered}"


async def test_readme_parameters_match_each_input_schema(documented, registered):
    mismatched = {
        name: {
            "readme": sorted(documented[name]),
            "schema": sorted(tool.input_schema.get("properties", {})),
        }
        for name, tool in registered.items()
        if name in documented
        and documented[name] != set(tool.input_schema.get("properties", {}))
    }

    assert mismatched == {}


async def test_every_registered_tool_has_a_handler(registered):
    assert set(TOOL_HANDLERS) == set(registered)
