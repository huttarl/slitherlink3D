"""Readable JSON for the data files.

Both extremes are hard to read. Minified, a grid is one 1000-character line
(genUniformPolyh used to write them that way). Fully indented, every coordinate
and every clue gets a line of its own, so a puzzle file ran to 491 lines to say
very little -- json.dump(..., indent=3) does that.

The rule here is the middle ground: a list of plain values stays on ONE line,
and anything containing a list or a dict is expanded. That gives one line per
vertex, per face, per clue array, which is the level a human wants to read:

    {
      "gridId": "C",
      "categories": ["Platonic solid", "parallelohedron", "zonohedron"],
      "vertices": [
        [-0.577350269, -0.577350269, -0.577350269],
        ...

Run it over files to reformat them in place:

    python3 util/json_format.py data/*.json
"""

import json
import sys


def is_leaf_list(value):
    """A list with nothing nested in it, so it can sit on one line."""
    return (isinstance(value, list)
            and not any(isinstance(item, (list, dict)) for item in value))


def format_json(value, indent=2, level=0):
    """
    Serializes value as JSON, keeping leaf lists on one line.

    @param value: anything json.dumps accepts
    @param indent: spaces per level
    @param level: current depth, for the recursive calls
    @returns: the JSON text, with no trailing newline
    """
    pad = ' ' * (indent * level)
    inner_pad = ' ' * (indent * (level + 1))

    if isinstance(value, dict):
        if not value:
            return '{}'
        lines = [f'{inner_pad}{json.dumps(str(key))}: '
                 f'{format_json(item, indent, level + 1)}'
                 for (key, item) in value.items()]
        return '{\n' + ',\n'.join(lines) + f'\n{pad}}}'

    if isinstance(value, list):
        if not value:
            return '[]'
        if is_leaf_list(value):
            # The whole point: coordinates, face indices and clue lists read as
            # one line each, not as a column of numbers.
            return json.dumps(value)
        lines = [f'{inner_pad}{format_json(item, indent, level + 1)}'
                 for item in value]
        return '[\n' + ',\n'.join(lines) + f'\n{pad}]'

    # Scalars: let json handle the escaping and the float repr (which is the
    # shortest string that round-trips, so rounded coordinates stay as written).
    return json.dumps(value)


def write_json(value, file, indent=2):
    """Writes value to an open file as formatted JSON, with a trailing newline."""
    file.write(format_json(value, indent))
    file.write('\n')


def reformat_file(path, indent=2):
    """
    Rewrites one JSON file in this format. Idempotent, and it round-trips: the
    parsed data is compared before and after, so a bug here can't silently
    corrupt a data file.
    """
    with open(path) as f:
        original = json.load(f)
    text = format_json(original, indent) + '\n'
    if json.loads(text) != original:
        raise AssertionError(f'reformatting {path} would change its data')
    with open(path, 'w') as f:
        f.write(text)


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        print('Usage: python3 util/json_format.py <file.json> ...')
        return 1
    for path in paths:
        reformat_file(path)
        print(f'formatted {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
