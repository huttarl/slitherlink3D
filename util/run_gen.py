#!/usr/bin/env python3.11
"""Run genSliPuzzles.py headlessly, with a timeout — for testing/smoke runs.

Wraps the generator so that:
  - matplotlib uses the non-interactive Agg backend (no GUI windows,
    safe to run headless or from automation);
  - the run is killed after a timeout (macOS has no `timeout` command);
  - the generator runs under this same interpreter (python3.11, which
    has compas/networkx/matplotlib installed — the default python3 may not).

Usage:
    util/run_gen.py <grid.json> [num_puzzles] [timeout_seconds]

Defaults: num_puzzles=1, timeout_seconds=60.

On timeout, the generator is first sent SIGINT so it can output any
puzzles that were already completed (it catches KeyboardInterrupt and
dumps its results); only if it doesn't exit within a grace period is it
killed outright.

Exit status: the generator's own exit status; 124 on timeout
(mirroring the GNU `timeout` convention), even if partial results
were output.
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

DEFAULT_NUM_PUZZLES = "1"
DEFAULT_TIMEOUT_SECONDS = 60
# How long to wait, after SIGINT, for the generator to output completed
# puzzles and exit on its own.
GRACE_SECONDS = 15


def usage():
    print("Usage: util/run_gen.py <grid.json> [num_puzzles] [timeout_seconds]",
          file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        usage()  # exits
    grid_file = sys.argv[1]
    num_puzzles = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_NUM_PUZZLES
    timeout = float(sys.argv[3]) if len(sys.argv) == 4 else DEFAULT_TIMEOUT_SECONDS

    generator = Path(__file__).resolve().parent / "genSliPuzzles.py"
    # Force the non-interactive backend for the child process only.
    env = dict(os.environ, MPLBACKEND="Agg")
    # sys.executable is the interpreter running this wrapper (python3.11),
    # so the generator gets the same one.
    cmd = [sys.executable, str(generator), grid_file, num_puzzles]

    proc = subprocess.Popen(cmd, env=env)
    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Ask the generator to wrap up: SIGINT raises KeyboardInterrupt in
        # it, and it responds by outputting the puzzles completed so far.
        print(f"\nrun_gen.py: generator timed out after {timeout}s; "
              f"interrupting it to salvage completed puzzles", file=sys.stderr)
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            print(f"run_gen.py: generator didn't exit within {GRACE_SECONDS}s "
                  f"of SIGINT; killing it", file=sys.stderr)
            proc.kill()
            proc.wait()
        sys.exit(124)
    sys.exit(returncode)


if __name__ == "__main__":
    main()
