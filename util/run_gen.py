#!/usr/bin/env python3
"""Run genSliPuzzles.py headlessly, with a timeout — for testing/smoke runs.

Wraps the generator so that:
  - matplotlib uses the non-interactive Agg backend (no GUI windows,
    safe to run headless or from automation);
  - the run is killed after a timeout (macOS has no `timeout` command);
  - the generator runs under this same interpreter, whichever python3 that
    turned out to be, so it can't end up on a different one than this wrapper.

Usage:
    util/run_gen.py [--quiet|--verbose] <grid.json> [num_puzzles] [timeout_seconds]

Defaults: num_puzzles=1, timeout_seconds=60.

--quiet (-q) and --verbose (-v) are passed straight through to the
generator, which uses them to set its stderr verbosity: --quiet leaves
only errors, warnings and the outcome of the run, --verbose adds per-edge
detail. Note that --quiet still lets errors through, so it is a better
way to keep a batch run's output manageable than redirecting stderr to
/dev/null, which hides real failures too.

--display=N and --existing=FILE are passed through as well; see the
generator's own docstring for what they do. In short, --existing keeps
everything in that file and both counts become "how many MORE", so adding
a display puzzle to a grid that already has puzzles is this (via a
temporary file, since the shell would truncate the input before the
generator reads it):

    util/run_gen.py -q --display=1 --existing=data/aC-puzzles.json \\
        data/aC.json 0 600 > /tmp/aC.json && mv /tmp/aC.json data/aC-puzzles.json

and adding two playable puzzles while keeping the display puzzle is the
same shape without --display, which defaults to 0 under --existing:

    util/run_gen.py -q --existing=data/aC-puzzles.json \\
        data/aC.json 2 600 > /tmp/aC.json && mv /tmp/aC.json data/aC-puzzles.json

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
    print("Usage: util/run_gen.py [--quiet|--verbose] [--display=N] "
          "[--existing=FILE] <grid.json> [num_puzzles] [timeout_seconds]",
          file=sys.stderr)
    print("  -q, --quiet      only errors, warnings and the outcome of the run",
          file=sys.stderr)
    print("  -v, --verbose    add per-edge/per-face detail (very wordy)",
          file=sys.stderr)
    print("  --display=N      also generate N display-only puzzles",
          file=sys.stderr)
    print("  --existing=FILE  keep the puzzles already in FILE",
          file=sys.stderr)
    sys.exit(1)


def main():
    # The flags may appear anywhere among the arguments; everything else is
    # positional, in the order given in usage().
    flags = []
    positional = []
    for arg in sys.argv[1:]:
        if (arg in ("-q", "--quiet", "-v", "--verbose")
                or arg.startswith(("--display=", "--existing="))):
            # Passed through to the generator, which parses them; this wrapper
            # only needs to know they aren't its own positional arguments.
            flags.append(arg)
        elif arg.startswith("-"):
            print(f"run_gen.py: unrecognized option '{arg}'", file=sys.stderr)
            usage()  # exits
        else:
            positional.append(arg)

    if len(positional) < 1 or len(positional) > 3:
        usage()  # exits
    grid_file = positional[0]
    num_puzzles = positional[1] if len(positional) >= 2 else DEFAULT_NUM_PUZZLES
    timeout = float(positional[2]) if len(positional) == 3 else DEFAULT_TIMEOUT_SECONDS

    generator = Path(__file__).resolve().parent / "genSliPuzzles.py"
    # Force the non-interactive backend for the child process only. Having done
    # that, silence matplotlib's complaint that the backend can't show a
    # figure: the generator calls plt.pause and plt.show to animate its
    # progress, which is exactly what we don't want here, so the warning is
    # telling us something we already arranged. Suppressed by message so that
    # other warnings still come through, including under --quiet.
    env = dict(os.environ, MPLBACKEND="Agg",
               PYTHONWARNINGS="ignore:FigureCanvasAgg is non-interactive")
    # sys.executable is the interpreter running this wrapper, so the generator
    # gets exactly the same one -- which matters because "python3" on PATH is
    # not necessarily the python3 that started this script.
    cmd = [sys.executable, str(generator), grid_file, num_puzzles] + flags

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
