"""The intent seam (SPEC 2/8/10).

The DwellMachine does not talk to tmux (or anything) directly; it hands a flat,
JSON-serializable ``Intent`` to an ``Emitter``. v1 ships ``LoggingEmitter``; the
tmux/driftwm backend later is just a different ``Emitter`` for the same Intent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    kind: str    # e.g. "select_cell"
    target: str  # e.g. "r0c1" (later a pane id like "%3")


class Emitter(Protocol):
    def emit(self, intent: Intent) -> None: ...


class LoggingEmitter:
    """Default emitter: logs the committed intent. Stand-in until tmux."""

    def emit(self, intent: Intent) -> None:
        logger.info("intent %s -> %s", intent.kind, intent.target)
