"""ops/watchdog.sh against a stub launchctl: reloads only what is really lost."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "ops" / "watchdog.sh"
LABELS = ("nordcast.archive", "nordcast.jobs", "nordcast.stack")


def run(tmp_path, loaded, plists=LABELS, pause=False, bootstrap_rc=0):
    agents = tmp_path / "Library" / "LaunchAgents"
    logs = tmp_path / "Library" / "Logs" / "nordcast"
    agents.mkdir(parents=True)
    logs.mkdir(parents=True)
    for label in plists:
        (agents / f"{label}.plist").touch()
    if pause:
        (logs / "watchdog.pause").touch()
    calls = tmp_path / "calls"
    stub = tmp_path / "launchctl"
    stub.write_text(
        "#!/bin/zsh\n"
        f'echo "$@" >> {calls}\n'
        "if [[ $1 == print ]]; then\n"
        f'  [[ " {" ".join(loaded)} " == *" ${{2:t}} "* ]]; exit $?\n'
        "fi\n"
        f"exit {bootstrap_rc}\n"
    )
    stub.chmod(0o755)
    out = subprocess.run(
        ["/bin/zsh", str(SCRIPT)],
        env={**os.environ, "HOME": str(tmp_path), "LAUNCHCTL": str(stub)},
        capture_output=True,
        text=True,
        check=True,
    )
    made = calls.read_text().splitlines() if calls.exists() else []
    return out.stdout, [c for c in made if c.startswith("bootstrap")]


def test_nothing_happens_when_all_are_loaded(tmp_path):
    assert run(tmp_path, LABELS) == ("", [])


def test_a_lost_agent_is_reloaded_and_logged(tmp_path):
    out, boots = run(tmp_path, ("nordcast.archive", "nordcast.stack"))
    assert "reloaded nordcast.jobs" in out
    assert len(boots) == 1 and boots[0].endswith("nordcast.jobs.plist")


def test_an_uninstalled_agent_is_left_alone(tmp_path):
    assert run(tmp_path, (), plists=()) == ("", [])


def test_the_pause_file_stops_it(tmp_path):
    assert run(tmp_path, (), pause=True) == ("", [])


def test_a_failed_reload_is_logged(tmp_path):
    out, _ = run(tmp_path, ("nordcast.archive", "nordcast.stack"), bootstrap_rc=5)
    assert "nordcast.jobs is unloaded and failed to reload" in out
