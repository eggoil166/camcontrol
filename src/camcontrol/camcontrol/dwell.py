"""Dwell-to-select state machine (SPEC 7).

A cell must hold the dot for ``dwell_ms`` before it commits. Boundary hysteresis
requires the dot to be ``hysteresis_margin`` *inside* a cell before that cell can
become pending, killing border flicker. The already-selected cell never re-fires.
"""

from __future__ import annotations

from camcontrol.geometry import Grid
from camcontrol.intent import Emitter, Intent


class DwellMachine:
    def __init__(
        self,
        grid: Grid,
        emitter: Emitter,
        dwell_ms: float,
        hysteresis_margin: float,
        selected: str | None = None,
    ) -> None:
        self.grid = grid
        self.emitter = emitter
        self.dwell_ms = dwell_ms
        self.hysteresis_margin = hysteresis_margin
        self.selected = selected
        self.pending: str | None = None
        self.pending_since: float = 0.0

    def update(self, x: float, y: float, now_ms: float) -> str | None:
        """Feed the latest dot. Returns the cell id if it committed this call."""
        cell = self.grid.cell_at(x, y)

        if cell is None or cell == self.selected:
            self.pending = None
            return None

        if cell == self.pending:
            if now_ms - self.pending_since >= self.dwell_ms:
                self.selected = cell
                self.pending = None
                self.emitter.emit(Intent(kind="select_cell", target=cell))
                return cell
            return None

        # A different candidate cell: only enter pending once the dot is deep
        # enough inside it (hysteresis). Otherwise leave the current pending.
        if self._deep_inside(cell, x, y):
            self.pending = cell
            self.pending_since = now_ms
        return None

    def _deep_inside(self, cell: str, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.grid.cell_rect(cell)
        m = self.hysteresis_margin
        return x0 + m <= x <= x1 - m and y0 + m <= y <= y1 - m
