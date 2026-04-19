from __future__ import annotations

import shutil

import pytest

from pyslang_mcp.hdl_examples import load_examples, validate_example

pytestmark = pytest.mark.skipif(
    shutil.which("verilator") is None,
    reason="Verilator is required for HDL smoke validation.",
)

SMOKE_EXAMPLES = load_examples(smoke_only=True)


@pytest.mark.parametrize("example", SMOKE_EXAMPLES, ids=lambda example: str(example["id"]))
def test_hdl_smoke_examples(example: dict[str, object]) -> None:
    validate_example(example)
