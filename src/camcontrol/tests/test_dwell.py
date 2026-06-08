from camcontrol.dwell import DwellMachine
from camcontrol.geometry import Grid
from camcontrol.intent import Intent


class RecordingEmitter:
    def __init__(self) -> None:
        self.intents: list[Intent] = []

    def emit(self, intent: Intent) -> None:
        self.intents.append(intent)


def make(dwell_ms=400, hysteresis_margin=0.04, selected=None):
    emitter = RecordingEmitter()
    machine = DwellMachine(
        grid=Grid(rows=1, cols=2),
        emitter=emitter,
        dwell_ms=dwell_ms,
        hysteresis_margin=hysteresis_margin,
        selected=selected,
    )
    return machine, emitter


def test_commits_after_dwell_elapses():
    machine, emitter = make(dwell_ms=400)
    # Deep inside the left cell.
    assert machine.update(0.25, 0.5, now_ms=0) is None  # pending starts
    committed = machine.update(0.25, 0.5, now_ms=400)
    assert committed == "r0c0"
    assert emitter.intents == [Intent(kind="select_cell", target="r0c0")]


def test_does_not_commit_before_dwell_elapses():
    machine, emitter = make(dwell_ms=400)
    machine.update(0.25, 0.5, now_ms=0)
    assert machine.update(0.25, 0.5, now_ms=399) is None
    assert emitter.intents == []


def test_does_not_refire_already_selected_cell():
    machine, emitter = make(dwell_ms=400)
    machine.update(0.25, 0.5, now_ms=0)
    machine.update(0.25, 0.5, now_ms=400)  # commit r0c0
    assert machine.update(0.25, 0.5, now_ms=900) is None
    assert len(emitter.intents) == 1


def test_leaving_all_cells_clears_pending():
    machine, emitter = make(dwell_ms=400)
    machine.update(0.25, 0.5, now_ms=0)  # pending left cell
    machine.update(1.5, 0.5, now_ms=200)  # dot leaves the unit square
    assert machine.update(0.25, 0.5, now_ms=400) is None  # pending restarted, not 400ms old
    assert emitter.intents == []


def test_hysteresis_blocks_pending_near_cell_edge():
    machine, emitter = make(dwell_ms=400, hysteresis_margin=0.04)
    # x=0.49 is within 0.04 of the r0c0/r0c1 divider at 0.5 -> not deep enough.
    machine.update(0.49, 0.5, now_ms=0)
    assert machine.update(0.49, 0.5, now_ms=400) is None
    assert emitter.intents == []
