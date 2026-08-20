#!/usr/bin/env python3
"""Build data/grids.json, the catalogue of available grids, from data/*.json.

The web app can't list the data/ directory over HTTP (static hosting has no
directory listing), so it fetches this manifest instead. Re-run this script
whenever grid or puzzle files are added to or removed from data/.

Usage: python3 util/build_catalogue.py
(No arguments; runs from anywhere, writes <repo>/data/grids.json.)

Grid files are recognized by having "gridId", "vertices" and "faces"
properties. Each is paired with its "<stem>-puzzles.json" file (if any) to
count available puzzles. Entries are sorted by size (edges, then faces) as
a first approximation of difficulty; the app presents them in this order,
which will eventually also serve as the player's progression order.

Note that the "file" property (the filename stem used to fetch
data/<file>.json) can differ from the grid's internal "gridId" —
e.g. cube.json has gridId "C".

Besides the grid files, this folds in data/lore.json, the hand-edited
lore registry (aliases, dual pairs — see the _comment in that file): each
solid's lore lands on its catalogue entry, so the app reads one manifest and
the registry survives regeneration of the tool-written grid files. The
registry is validated first, and a bad registry stops the build with the old
catalogue left in place — a typo should be a loud error, not a silently
dropped alias.
"""
import json
import sys
from pathlib import Path

import grid_topology
import json_format

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOGUE_PATH = DATA_DIR / "grids.json"
LORE_PATH = DATA_DIR / "lore.json"

# The lore attributes a solid's registry entry may carry. Closed on purpose: an
# unrecognized key in a hand-edited file is far more likely a typo ("aliasses")
# than a new feature, and a typo that validation waves through is lore that
# quietly never reaches the app. Extend this when the registry grows a
# deliberate new attribute.
KNOWN_LORE_ATTRIBUTES = ("aliases",)


def count_edges(faces):
    """How many distinct edges the grid has.

    Counted from the edges themselves rather than as half the face sides. Halving
    is right only where every edge has two faces, and the open nanotube
    (util/genNanotube.py) has 40 rim edges with one face each -- which halving
    reported as 20, putting its edge count 20 short and mis-sorting it in a
    catalogue ordered by size."""
    return len(grid_topology.edges_of(faces))


def build_entry(grid_path):
    """Build one catalogue entry from a grid file, or return None if the
    file isn't a grid (e.g. a puzzles file or this catalogue itself)."""
    data = json.load(open(grid_path))
    if not all(prop in data for prop in ("gridId", "vertices", "faces")):
        return None

    puzzles_path = grid_path.with_name(grid_path.stem + "-puzzles.json")
    num_puzzles = 0
    if puzzles_path.exists():
        puzzles_data = json.load(open(puzzles_path))
        if puzzles_data.get("gridId") != data["gridId"]:
            print(f"Warning: {puzzles_path.name} has gridId "
                  f"'{puzzles_data.get('gridId')}' but {grid_path.name} has "
                  f"'{data['gridId']}'; skipping its puzzles.", file=sys.stderr)
        else:
            num_puzzles = len(puzzles_data.get("puzzles", []))

    return {
        "file": grid_path.stem,   # fetch as data/<file>.json
        "gridId": data["gridId"],
        "gridName": data.get("gridName", grid_path.stem),
        "categories": data.get("categories", []),
        "faces": len(data["faces"]),
        "edges": count_edges(data["faces"]),
        "vertices": len(data["vertices"]),
        "numPuzzles": num_puzzles,
    }


def load_lore(lore_path=LORE_PATH):
    """The lore registry's two parts, or empty ones if there is no registry.

    A missing registry is fine — the catalogue is then built from the grid
    files alone, exactly as before the registry existed."""
    if not lore_path.exists():
        return ({}, [])
    data = json.load(open(lore_path))
    return (data.get("solids", {}), data.get("duals", []))


def validate_lore(solids, duals, known_ids):
    """Raises ValueError listing everything wrong with the registry.

    All the problems at once, not the first: the registry is hand-edited, and
    fix-rerun-fix against one error at a time is the workflow that teaches
    people to stop reading error messages.

    @param solids: the registry's per-solid attribute dictionaries, by gridId
    @param duals: the registry's list of dual pairs
    @param known_ids: every gridId found in the grid files
    """
    problems = []

    for (grid_id, attributes) in solids.items():
        if grid_id not in known_ids:
            problems.append(f"solids['{grid_id}']: no grid in data/ has that gridId")
        if not isinstance(attributes, dict):
            problems.append(f"solids['{grid_id}']: expected a dictionary of "
                            f"attributes, got {type(attributes).__name__}")
            continue
        for key in attributes:
            if key not in KNOWN_LORE_ATTRIBUTES:
                problems.append(f"solids['{grid_id}']: unknown attribute '{key}' "
                                f"(knows: {', '.join(KNOWN_LORE_ATTRIBUTES)})")
        aliases = attributes.get("aliases")
        if aliases is not None and (
                not isinstance(aliases, list) or len(aliases) == 0
                or not all(isinstance(a, str) and a.strip() for a in aliases)):
            problems.append(f"solids['{grid_id}']: aliases must be a non-empty "
                            f"list of non-empty strings")

    seen_in_pair = set()
    for pair in duals:
        if not (isinstance(pair, list) and len(pair) == 2
                and all(isinstance(i, str) for i in pair)):
            problems.append(f"duals: {json.dumps(pair)} is not a pair of gridIds")
            continue
        (a, b) = pair
        if a == b:
            # The registry's own convention: the 'self-dual' category in the
            # grid file says this, not a [X, X] pair here.
            problems.append(f"duals: ['{a}', '{b}'] pairs a solid with itself; "
                            f"self-duals carry the 'self-dual' category instead")
        for grid_id in (a, b):
            if grid_id not in known_ids:
                problems.append(f"duals: no grid in data/ has gridId '{grid_id}'")
            if grid_id in seen_in_pair:
                problems.append(f"duals: '{grid_id}' appears in more than one pair")
            seen_in_pair.add(grid_id)

    if problems:
        raise ValueError("\n".join(problems))


def fold_lore(entries, solids, duals):
    """Adds the registry's lore to the catalogue entries, in place.

    Following the data files' convention, a key is absent rather than empty:
    a solid with no aliases has no "aliases" key, one whose dual we don't ship
    has no "dual" key. Each pair, stored once in the registry, lands on BOTH
    solids' entries here — the reader of one entry shouldn't need to know the
    pair might be spelled the other way round."""
    by_id = {entry["gridId"]: entry for entry in entries}
    for (grid_id, attributes) in solids.items():
        if "aliases" in attributes:
            by_id[grid_id]["aliases"] = attributes["aliases"]
    for (a, b) in duals:
        by_id[a]["dual"] = b
        by_id[b]["dual"] = a


def main():
    entries = []
    for grid_path in sorted(DATA_DIR.glob("*.json")):
        if grid_path.name == CATALOGUE_PATH.name or grid_path.stem.endswith("-puzzles"):
            continue
        if grid_path == LORE_PATH:
            continue    # not skipped, just read separately -- see below

        entry = build_entry(grid_path)
        if entry is None:
            print(f"Skipping {grid_path.name}: not a grid file.", file=sys.stderr)
            continue
        entries.append(entry)

    # The lore registry: validated BEFORE anything is written, so a typo in the
    # hand-edited file stops the build and leaves the old catalogue standing.
    (solids, duals) = load_lore()
    try:
        validate_lore(solids, duals, {e["gridId"] for e in entries})
    except ValueError as err:
        print(f"{LORE_PATH.name} is invalid; catalogue NOT rebuilt:\n{err}",
              file=sys.stderr)
        return 1
    fold_lore(entries, solids, duals)

    # Sort by size as a rough difficulty progression. The sort must stay
    # deterministic, since regeneration overwrites any manual reordering.
    entries.sort(key=lambda e: (e["edges"], e["faces"], e["gridId"]))

    catalogue = {
        "_comment": "Generated by util/build_catalogue.py -- do not edit by hand.",
        "grids": entries,
    }
    with open(CATALOGUE_PATH, "w") as f:
        json_format.write_json(catalogue, f)
    print(f"Wrote {CATALOGUE_PATH} with {len(entries)} grids:")
    for e in entries:
        print(f"  {e['file']:6s} {e['gridName']:24s} "
              f"F={e['faces']:3d} E={e['edges']:3d} puzzles={e['numPuzzles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
