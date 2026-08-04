/**
 * Navigation over the grid catalogue (data/grids.json).
 *
 * Catalogue order IS the progression order: util/build_catalogue.py sorts
 * grids by size (edges, then faces), so walking the catalogue climbs steadily
 * in difficulty, and the polyhedron families interleave along the way.
 *
 * The navigation and grouping helpers are pure functions over a parsed
 * catalogue, with no imports, so they unit-test headless (see
 * js/tests/catalogue.test.js). loadCatalogue, at the end, is the one part that
 * touches the network.
 */

// The polyhedron families, in the order a player meets them: the five Platonic
// solids first, then the Archimedeans, and so on. These PARTITION the
// collection -- a solid belongs to at most one -- which is what makes them the
// right thing to group the picker by.
//
// A grid's other categories (deltahedron, chiral, quasiregular,
// parallelohedron) are cross-cutting attributes rather than families: the
// tetrahedron is a Platonic solid AND a deltahedron. Those belong on the
// About-this-solid card, not in this list.
const FAMILY_ORDER = [
    'Platonic solid',
    'Archimedean solid',
    'Catalan solid',
    'Johnson solid',
];

/** Plural of a category name: "Platonic solid" -> "Platonic solids". */
function pluralizeCategory(category) {
    // -hedron -> -hedra, so "deltahedron" doesn't come out as "deltahedrons".
    const plural = category.endsWith('hedron')
        ? category.replace(/hedron$/, 'hedra')
        : category + 's';
    return plural.charAt(0).toUpperCase() + plural.slice(1);
}

/**
 * Which family a grid belongs to, for grouping purposes.
 *
 * A known family wins, so the groups come out in FAMILY_ORDER. Failing that we
 * fall back to the grid's first category, so a family added to the data shows
 * up as its own group straight away rather than being silently lumped in with
 * everything else -- and a grid with no categories at all still lands somewhere.
 *
 * @param {Object} grid - a catalogue entry
 * @returns {string} the category to group under
 */
function gridFamily(grid) {
    const categories = grid.categories || [];
    return FAMILY_ORDER.find(family => categories.includes(family))
        || categories[0]
        || 'Other';
}

/**
 * Groups grids by family, for a picker that shows the taxonomy as it goes.
 *
 * Seeing "Platonic solids" and "Archimedean solids" as headings, every time you
 * choose a puzzle, teaches the families with no prose and nothing to dismiss.
 *
 * Order: the known families first, in FAMILY_ORDER; then anything else
 * alphabetically, so a new category has a predictable home. Within a group,
 * catalogue (progression) order is kept, which means ascending size.
 *
 * @param {Array<Object>} grids - catalogue entries, e.g. from playableGrids
 * @returns {Array<{family: string, label: string, grids: Array<Object>}>}
 *     label is the plural form, ready for an optgroup heading
 */
export function groupGridsByFamily(grids) {
    const groups = new Map();
    for (const grid of grids) {
        const family = gridFamily(grid);
        if (!groups.has(family)) groups.set(family, []);
        groups.get(family).push(grid);
    }

    const rank = family => {
        const known = FAMILY_ORDER.indexOf(family);
        // Unknown categories sort after all known families, among themselves
        // alphabetically (handled by the tie-break below).
        return known < 0 ? FAMILY_ORDER.length : known;
    };
    return [...groups.keys()]
        .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
        .map(family => ({family, label: pluralizeCategory(family),
                         grids: groups.get(family)}));
}

/**
 * The grids worth offering the player: those that actually have puzzles.
 *
 * A grid can be in the catalogue with none -- its data/<id>-puzzles.json
 * missing, empty, or not generated yet -- and there is nothing to do on such a
 * grid, so it doesn't belong in the polyhedron picker. nextPuzzleLocation skips
 * the same grids when advancing, so the picker and the Next button agree on
 * what exists.
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @param {string|null} alwaysInclude - a grid file stem to keep regardless.
 *     Pass the currently loaded grid, so the picker can never name a different
 *     polyhedron than the one on screen. Belt and braces today: loading a
 *     puzzleless grid with an explicit ?grid= fails before the UI is built (a
 *     missing puzzle file 404s; an empty puzzles array trips "puzzle index out
 *     of range"), so there is no such grid to keep. It matters the moment that
 *     path is made to fail gracefully.
 * @returns {Array<Object>} catalogue entries, in catalogue (progression) order
 */
export function playableGrids(catalogue, alwaysInclude = null) {
    return catalogue.grids.filter(
        grid => grid.numPuzzles > 0 || grid.file === alwaysInclude);
}

/**
 * Finds the puzzle that follows the given one in progression order.
 *
 * Advances within the current grid while it has more puzzles, then moves to
 * the next grid in catalogue order that has any puzzles (skipping grids whose
 * puzzle file is missing or empty).
 *
 * @param {Object} catalogue - the parsed data/grids.json
 * @param {string} currentFile - the current grid's file stem (e.g. 'cube')
 * @param {number} currentPuzzleNumber - 1-based, as in the ?puzzle= parameter
 * @returns {{file: string, puzzle: number}|null} where to go next (puzzle is
 *     1-based), or null if there is no next puzzle: either this is the last
 *     puzzle in the catalogue, or currentFile isn't in the catalogue at all
 *     (so we can't say what follows it).
 */
export function nextPuzzleLocation(catalogue, currentFile, currentPuzzleNumber) {
    const grids = catalogue.grids;
    const index = grids.findIndex(grid => grid.file === currentFile);
    if (index < 0) return null;

    // More puzzles on this grid?
    if (currentPuzzleNumber < grids[index].numPuzzles) {
        return { file: currentFile, puzzle: currentPuzzleNumber + 1 };
    }

    // Otherwise the first puzzle of the next grid that has any.
    for (let i = index + 1; i < grids.length; i++) {
        if (grids[i].numPuzzles > 0) {
            return { file: grids[i].file, puzzle: 1 };
        }
    }

    return null; // End of the catalogue.
}

/** The in-flight or completed fetch, so the catalogue is loaded once. */
let cataloguePromise = null;

/**
 * Loads data/grids.json (regenerate it with util/build_catalogue.py when data/
 * changes). Shared by everything that needs the catalogue -- the pickers and the
 * About-this-solid card -- hence the cached promise: whoever asks second gets
 * the first one's result, even if it hasn't arrived yet.
 *
 * cache: 'no-cache' forces a conditional request rather than trusting a cached
 * copy. Static servers (including python -m http.server) send no Cache-Control
 * for data files, so browsers guess a freshness lifetime and can serve a stale
 * catalogue for a long time -- and because this fetch happens after page load,
 * even a hard reload doesn't necessarily bypass it. The server answers 304 when
 * nothing changed, so this stays cheap.
 *
 * @returns {Promise<Object>} the parsed catalogue
 */
export function loadCatalogue() {
    if (cataloguePromise === null) {
        cataloguePromise = fetch('data/grids.json', {cache: 'no-cache'})
            .then(response => {
                if (!response.ok) {
                    throw new Error(
                        `Failed to load data/grids.json: ${response.statusText}`);
                }
                return response.json();
            });
    }
    return cataloguePromise;
}
