#!/usr/bin/env python3
"""Generate puzzles for every grid that hasn't got any, one after another.

Usage:
    util/fill_puzzles.py                       # every grid with no puzzles yet
    util/fill_puzzles.py dtT daC               # just these
    util/fill_puzzles.py --puzzles 3 --display 1 --timeout 1800 [stem ...]
    util/fill_puzzles.py --force dtT           # regenerate even if it has some

Meant to be started and left alone: it walks the grids smallest first, so the
quick ones are done and safe on disk long before a big one is still grinding, and
reports each outcome as it goes. Defaults: 3 puzzles and 1 display puzzle per
grid, 1800 seconds each.

Each grid is generated through util/run_gen.py (so matplotlib stays headless and
the timeout is enforced) into a temporary file, which is moved into place only if
it contains at least one puzzle. A grid that times out therefore either gains the
puzzles it managed -- the generator writes what it has when interrupted -- or is
left exactly as it was.

Reads data/grids.json for the edge counts it orders by, if it's there; a grid
missing from the catalogue is still processed, just last. Standard library only.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

UTIL_DIR = Path(__file__).resolve().parent
DATA_DIR = UTIL_DIR.parent / 'data'
RUN_GEN = UTIL_DIR / 'run_gen.py'

DEFAULTS = {'--puzzles': '3', '--display': '1', '--timeout': '1800'}

# run_gen.py's exit status on timeout, mirroring GNU timeout.
TIMED_OUT = 124


def puzzle_count(stem):
    """How many playable puzzles a grid already has."""
    path = DATA_DIR / f'{stem}-puzzles.json'
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text()).get('puzzles', []))
    except json.JSONDecodeError:
        return 0        # A broken file counts as none, so it gets rewritten.


def grid_stems():
    """Every grid file's stem, smallest first by edge count where known."""
    stems = sorted(p.stem for p in DATA_DIR.glob('*.json')
                   if not p.name.endswith('-puzzles.json')
                   and p.name != 'grids.json')
    edges = {}
    catalogue = DATA_DIR / 'grids.json'
    if catalogue.exists():
        edges = {g['file']: g['edges']
                 for g in json.loads(catalogue.read_text())['grids']}
    # Grids the catalogue doesn't know about sort last, keeping their own order.
    return sorted(stems, key=lambda stem: (edges.get(stem, 10 ** 6), stem))


def generate(stem, options):
    """Run the generator for one grid. Returns (kept, puzzles, seconds, note)."""
    grid = DATA_DIR / f'{stem}.json'
    target = DATA_DIR / f'{stem}-puzzles.json'
    scratch = DATA_DIR / f'{stem}-puzzles.json.new'

    command = [str(RUN_GEN), '-q',
               f'--display={options["--display"]}', str(grid),
               options['--puzzles'], options['--timeout']]
    started = time.monotonic()
    with open(scratch, 'w') as out:
        status = subprocess.call(command, stdout=out)
    elapsed = time.monotonic() - started

    try:
        produced = len(json.loads(scratch.read_text()).get('puzzles', []))
    except (json.JSONDecodeError, FileNotFoundError):
        produced = 0

    note = 'timed out' if status == TIMED_OUT else ('' if status == 0
                                                   else f'exit {status}')
    if produced:
        scratch.replace(target)
        return (True, produced, elapsed, note)
    scratch.unlink(missing_ok=True)
    return (False, 0, elapsed, note or 'no puzzles produced')


def main():
    options = dict(DEFAULTS)
    force = False
    stems = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--force':
            force = True
        elif args[i] in options:
            key = args[i]
            i += 1
            if i >= len(args):
                print(f'{key} needs a value.', file=sys.stderr)
                sys.exit(1)
            options[key] = args[i]
        elif args[i].startswith('-'):
            print(f"Unrecognized option '{args[i]}'. See the docstring.",
                  file=sys.stderr)
            sys.exit(1)
        else:
            stems.append(args[i])
        i += 1

    candidates = stems or grid_stems()
    missing = [s for s in candidates if not (DATA_DIR / f'{s}.json').exists()]
    if missing:
        print(f'No such grid: {", ".join(missing)}', file=sys.stderr)
        sys.exit(1)
    todo = [s for s in candidates if force or puzzle_count(s) == 0]
    if not todo:
        print('Every grid asked for already has puzzles. --force to redo them.')
        return

    print(f'Generating {options["--puzzles"]} puzzles and '
          f'{options["--display"]} display puzzle(s) for {len(todo)} grid(s), '
          f'up to {options["--timeout"]}s each:')
    (done, failed) = ([], [])
    for stem in todo:
        print(f'  {stem} ... ', end='', flush=True)
        (kept, produced, elapsed, note) = generate(stem, options)
        detail = f' ({note})' if note else ''
        print(f'{produced} puzzles in {elapsed:.0f}s{detail}'
              if kept else f'nothing kept after {elapsed:.0f}s{detail}')
        (done if kept else failed).append(stem)

    print(f'\nFilled {len(done)} grid(s): {", ".join(done) or "none"}')
    if failed:
        print(f'Still without puzzles: {", ".join(failed)}')
    print('Rebuild the catalogue next: util/build_catalogue.py')


if __name__ == '__main__':
    main()
