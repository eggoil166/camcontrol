"""A fixed grid over the normalized [0,1]x[0,1] region (terminal client rect).

Cells are pure geometry, identified ``r{row}c{col}`` with row 0 at the top and
col 0 at the left. When tmux lands, a PaneRegistry replaces this behind the same
``cell_at`` shape.
"""

from __future__ import annotations


class Grid:
    def __init__(self, rows: int, cols: int) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("grid needs at least 1 row and 1 col")
        self.rows = rows
        self.cols = cols

    def cell_at(self, x: float, y: float) -> str | None:
        """Cell id containing normalized point (x, y), or None if outside [0,1]."""
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return None
        col = min(int(x * self.cols), self.cols - 1)
        row = min(int(y * self.rows), self.rows - 1)
        return f"r{row}c{col}"

    def cell_rect(self, cell_id: str) -> tuple[float, float, float, float]:
        """Normalized (x0, y0, x1, y1) bounds of a cell."""
        row, col = self._parse(cell_id)
        x0 = col / self.cols
        x1 = (col + 1) / self.cols
        y0 = row / self.rows
        y1 = (row + 1) / self.rows
        return (x0, y0, x1, y1)

    def _parse(self, cell_id: str) -> tuple[int, int]:
        row_s, _, col_s = cell_id.lstrip("r").partition("c")
        row, col = int(row_s), int(col_s)
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise ValueError(f"{cell_id} out of range for {self.rows}x{self.cols} grid")
        return row, col
