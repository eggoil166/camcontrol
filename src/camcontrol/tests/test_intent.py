import dataclasses
import json
import logging

from camcontrol.intent import Intent, LoggingEmitter


def test_intent_is_json_serializable():
    intent = Intent(kind="select_cell", target="r0c1")
    encoded = json.dumps(dataclasses.asdict(intent))
    assert json.loads(encoded) == {"kind": "select_cell", "target": "r0c1"}


def test_logging_emitter_logs_target(caplog):
    emitter = LoggingEmitter()
    with caplog.at_level(logging.INFO):
        emitter.emit(Intent(kind="select_cell", target="r0c1"))
    assert "r0c1" in caplog.text
