from __future__ import annotations

import json
import logging

from relayforge.logging import JsonFormatter


def test_json_formatter_emits_structured_fields() -> None:
    record = logging.LogRecord(
        name="relayforge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="workflow complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.workflow_id = "wf-1"
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "relayforge.test"
    assert parsed["message"] == "workflow complete"
    assert parsed["request_id"] == "req-123"
    assert parsed["workflow_id"] == "wf-1"
    assert "timestamp" in parsed
