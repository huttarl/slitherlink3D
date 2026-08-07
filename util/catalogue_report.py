#!/usr/bin/env python3
"""Report what data/ currently holds: one line per grid, plus totals.

Usage:
    util/catalogue_report.py [--puzzles] [stem_or_gridId ...]

With no arguments, every grid in data/grids.json, in catalogue order (which is
progression order: by edges, then faces). With arguments, only the grids whose
file stem or gridId matches -- handy after adding or regenerating one.

Columns in the default view: file, gridId, name, F/E/V counts, puz (playable
puzzles), disp (display puzzles), categories.

--puzzles reports on the puzzles instead of the categories, and is the one to run
after generating and before committing. Columns:

    census    faces by size, as "12x5, 15x6" -- 12 pentagons and 15 hexagons
    clues     the clue values the puzzles actually use
    dens      share of faces carrying a clue, as a range over the puzzles
    loop/max  loop length, against the most this solid could have
    patch     largest connected group of faces the loop never touches

The first three answer "will these make decent puzzles?" -- a face with k sides
admits clues 0..k-1, so an all-triangle grid can only ever say 0, 1 or 2, and
comparing a new grid's clue density against the collection says whether the
generator had to work unusually hard.

The last two are about how the puzzles LOOK, which the others miss entirely. A big
patch is a field of 0 clues with nothing to do in it, and that is a real defect --
one generated puzzle covered barely half its solid, and it took someone looking at
the screen to notice, because no report showed it.

Reads data/grids.json for the geometry and playable-puzzle counts, and each
data/<stem>-puzzles.json for the display puzzles and clues, which the catalogue
doesn't track. Reporting only: rebuild the catalogue with
util/build_catalogue.py, and leave the checking to the test suites.

Because the counts come from the catalogue rather than from the puzzle files, a
stale grids.json makes this report quietly wrong. So it warns, on stderr and
before anything else, if any data file is newer -- see warn_if_stale.

Standard library only, so plain python3 runs it -- no compas or numpy needed.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grid_topology  # noqa: E402  (needs the path set up first)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# Grids at least this big are the ones the title screen can choose from, so a
# missing display puzzle is worth mentioning for them and not for the rest.
# Mirrors TITLE_SCREEN_MIN_FACES in js/constants.js.
TITLE_SCREEN_MIN_FACES = 11


def files_newer_than_catalogue(data_dir=None):
    """Names of data files modified more recently than grids.json.

    Any of them means the catalogue is stale, and since the playable-puzzle
    counts in this report come FROM the catalogue, they are then simply wrong --
    a grid regenerated without rebuilding still shows its old count, and a grid
    added without rebuilding does not appear at all. That has already caused one
    confident, wrong report of what data/ contained.
    """
    data_dir = data_dir or DATA_DIR
    catalogue = data_dir / 'grids.json'
    if not catalogue.exists():
        return []
    when = catalogue.stat().st_mtime
    return sorted(path.name for path in data_dir.glob('*.json')
                  if path != catalogue and path.stat().st_mtime > when)


def warn_if_stale(data_dir=None, out=None):
    """Print the staleness warning, if there is one. Returns True if it warned.

    `out` defaults to sys.stderr, but resolved at call time rather than as a
    default argument value -- a default would capture whatever sys.stderr was when
    this module was imported, and so ignore any later replacement of it.

    Deliberately on stderr and before the table, not appended at the end. Both
    choices come from how this went wrong in practice: a note at the bottom is
    easy to skip past -- fill_puzzles.py's own "rebuild the catalogue next"
    reminder was -- and the report is usually read through a pipe like
    `| grep dtC`, which would filter a stdout warning out of sight entirely.
    stderr goes to the terminal either way.
    """
    out = out or sys.stderr
    stale = files_newer_than_catalogue(data_dir)
    if not stale:
        return False
    shown = ', '.join(stale[:6])
    if len(stale) > 6:
        shown += f' and {len(stale) - 6} more'
    print(f'WARNING: {len(stale)} data file(s) are newer than grids.json, so the '
          f'puzzle counts below are out of date ({shown}).\n'
          f'         Run util/build_catalogue.py, then this again.', file=out)
    return True


def display_puzzle_count(stem):
    """How many display-only puzzles a grid's puzzle file holds (0 if none)."""
    path = DATA_DIR / f'{stem}-puzzles.json'
    if not path.exists():
        return 0
    return len(json.loads(path.read_text()).get('displayPuzzles', []))


def face_census(stem):
    """A grid's faces by size, as "12x5, 15x6" -- 12 pentagons and 15 hexagons."""
    faces = json.loads((DATA_DIR / f'{stem}.json').read_text())['faces']
    sizes = {}
    for face in faces:
        sizes[len(face)] = sizes.get(len(face), 0) + 1
    return (len(faces),
            ', '.join(f'{count}x{size}' for (size, count) in sorted(sizes.items())))


def as_range(values, suffix=''):
    """"3" for one distinct value, "3-7" for several. Empty for nothing."""
    if not values:
        return ''
    (low, high) = (min(values), max(values))
    return f'{low}{suffix}' if low == high else f'{low}-{high}{suffix}'


def shape_summary(stem):
    """How interesting the grid's stored puzzles look, as (loop, patch).

    loop is the loop length over the puzzles against the most this solid could
    have (its vertex count, since the loop is a simple cycle through vertices),
    e.g. "19-28/62". patch is the largest connected group of faces the loop never
    touches -- the field of 0 clues a player sees as a dull blank area, and the
    thing that catches a puzzle covering only part of the solid.

    Display puzzles count too: one is shown on the title screen, so a dull one is
    the first thing anybody sees.
    """
    grid_path = DATA_DIR / f'{stem}.json'
    puzzle_path = DATA_DIR / f'{stem}-puzzles.json'
    if not grid_path.exists() or not puzzle_path.exists():
        return ('', '')
    data = json.loads(puzzle_path.read_text())
    puzzles = data.get('puzzles', []) + data.get('displayPuzzles', [])
    if not puzzles:
        return ('', '')

    faces = grid_topology.load_grid(grid_path)['faces']
    adjacency = grid_topology.face_adjacency(faces)
    loops = [grid_topology.loop_edges(p['solution']) for p in puzzles]
    lengths = [len(loop) for loop in loops]
    patches = [grid_topology.largest_quiet_patch(faces, loop, adjacency)
               for loop in loops]
    return (f'{as_range(lengths)}/{grid_topology.loop_ceiling(faces)}',
            as_range(patches))


def clue_summary(stem, num_faces):
    """What the grid's playable puzzles do with clues.

    @returns (values, density) -- the clue values used, as "0-5" or "1, 3, 5",
        and the percentage of faces carrying a clue, as a range over the puzzles
    """
    path = DATA_DIR / f'{stem}-puzzles.json'
    if not path.exists() or not num_faces:
        return ('', '')
    puzzles = json.loads(path.read_text()).get('puzzles', [])
    if not puzzles:
        return ('', '')

    values = sorted({c for p in puzzles for c in p['clues'] if c != -1})
    # A run of consecutive values is the common case and reads better collapsed.
    contiguous = values == list(range(values[0], values[-1] + 1))
    shown = (f'{values[0]}-{values[-1]}' if contiguous and len(values) > 1
             else ', '.join(str(v) for v in values))

    counts = [len([c for c in p['clues'] if c != -1]) for p in puzzles]
    (low, high) = (min(counts) / num_faces, max(counts) / num_faces)
    density = (f'{100 * low:.0f}%' if low == high
               else f'{100 * low:.0f}-{100 * high:.0f}%')
    return (shown, density)


def main():
    warn_if_stale()
    catalogue = json.loads((DATA_DIR / 'grids.json').read_text())
    args = sys.argv[1:]
    per_puzzle = '--puzzles' in args
    wanted = [a for a in args if a != '--puzzles']
    grids = [g for g in catalogue['grids']
             if not wanted or g['file'] in wanted or g['gridId'] in wanted]
    if not grids:
        print(f'No grid matches {wanted}. Names are file stems or gridIds; '
              f'run with no arguments to list them all.', file=sys.stderr)
        sys.exit(1)

    if per_puzzle:
        print(f'{"file":6} {"name":28} {"E":>4} {"puz":>4}  {"census":22} '
              f'{"clues":7} {"dens":8} {"loop/max":>9} {"patch":>6}')
        for g in grids:
            stem = g['file']
            (num_faces, census) = face_census(stem)
            (values, density) = clue_summary(stem, num_faces)
            (loop, patch) = shape_summary(stem)
            print(f'{stem:6} {g["gridName"][:28]:28} {g["edges"]:4} '
                  f'{g["numPuzzles"]:4}  {census:22} {values:7} {density:8} '
                  f'{loop:>9} {patch:>6}')
    else:
        print(f'{"file":6} {"gridId":7} {"name":42} {"F":>4} {"E":>4} {"V":>4} '
              f'{"puz":>4} {"disp":>4}  categories')
        for g in grids:
            stem = g['file']
            print(f'{stem:6} {g["gridId"]:7} {g["gridName"]:42} '
                  f'{g["faces"]:4} {g["edges"]:4} {g["vertices"]:4} '
                  f'{g["numPuzzles"]:4} {display_puzzle_count(stem):4}  '
                  f'{", ".join(g.get("categories", []))}')

    playable = sum(g['numPuzzles'] for g in grids)
    display = sum(display_puzzle_count(g['file']) for g in grids)
    print(f'\n{len(grids)} grid(s), {playable} playable puzzles, '
          f'{display} display puzzles')

    # Two things that are easy to forget after adding a grid, and quiet when
    # they go wrong: an unplayable grid, and a title-screen solid with no loop
    # to show.
    unplayable = [g['file'] for g in grids if g['numPuzzles'] == 0]
    if unplayable:
        print(f'No puzzles (so absent from the picker): {", ".join(unplayable)}')
    loopless = [g['file'] for g in grids
                if g['faces'] >= TITLE_SCREEN_MIN_FACES
                and g['numPuzzles'] > 0 and display_puzzle_count(g['file']) == 0]
    if loopless:
        print(f'Big enough for the title screen but with no display puzzle: '
              f'{", ".join(loopless)}')


if __name__ == '__main__':
    main()
