/**
 * Where the About card sends a player who wants to know more.
 *
 * Two sources, chosen for what each does best, and deliberately not Wikipedia:
 *
 *  - Visual Polyhedra (dmccooey.com) for the individual solid: a page per
 *    polyhedron with an interactive model you can spin, plus its vital
 *    statistics -- the natural next step from "I just solved this thing".
 *  - George Hart's Virtual Polyhedra (georgehart.com) for the families. These
 *    are tutorial pages with real prose and exercises, which is what someone
 *    meeting the word "Archimedean" for the first time actually needs; his
 *    per-solid links are raw .wrl model files, so they're no use here.
 *  - Plus Magazine (Cambridge's Millennium Mathematics Project) for Euler's
 *    formula: authoritative and written for a general reader.
 *
 * Every URL these produce for the current 26 grids was checked (all HTTP 200)
 * on 2026-08-04. Per-solid pages follow a rule, with a table for the handful of
 * exceptions; the categories are a table, there being no rule to have.
 *
 * A category with no entry is fine and means "no link": the card leaves the word
 * plain rather than sending anyone somewhere unhelpful.
 *
 * ADDING A POLYHEDRON: its link is derived from its name, so it appears by
 * itself -- but nothing has checked that the page exists. Confirm with
 *
 *     npm run test:links
 *
 * which fetches every link the catalogue produces. It's skipped by the everyday
 * suite, which shouldn't need the network. If a link 404s, add an entry to
 * SOLID_PAGE_EXCEPTIONS.
 */

const VISUAL_POLYHEDRA = 'https://dmccooey.com/polyhedra/';
const VIRTUAL_POLYHEDRA = 'https://www.georgehart.com/virtual-polyhedra/';

/**
 * gridId -> page name, for the solids the rule below gets wrong.
 *
 * Only the chiral ones so far: Visual Polyhedra gives them SEPARATE laevo and
 * dextro pages and no plain one (SnubCube.html is a 404). These point at the
 * laevo page, and the card claims nothing about which hand our model is -- the
 * two are mirror images, so the page teaches the same solid either way.
 *
 * Keyed by gridId, which is not always the data file's stem: the cube's file is
 * cube.json but its gridId is 'C'.
 */
const SOLID_PAGE_EXCEPTIONS = {
    sC: 'LsnubCube',
    sD: 'LsnubDodecahedron',
};

/**
 * The page name Visual Polyhedra uses for a solid, derived from its name.
 *
 * Their convention is the plain English name in PascalCase with the spaces
 * removed: "Truncated icosahedron" -> TruncatedIcosahedron, "Elongated square
 * gyrobicupola" -> ElongatedSquareGyrobicupola. Our Johnson names carry a
 * bracketed catalogue number ("Square pyramid (J1)") which isn't part of it.
 *
 * This holds for 24 of the 26 grids; the other two are in the exception table
 * above. A grid added later therefore gets a link for free -- but an unverified
 * one, so spot-check it (see the note at the top of this file).
 *
 * @param {string} gridName - e.g. 'Gyroelongated square pyramid (J10)'
 * @returns {string} e.g. 'GyroelongatedSquarePyramid'
 */
function derivePageName(gridName) {
    return gridName
        // Drop a trailing Johnson number, and anything else parenthesized.
        .replace(/\s*\([^)]*\)\s*$/, '')
        .trim()
        .split(/[\s-]+/)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join('')
        // Their filenames are letters and digits only, so an apostrophe or a
        // stray punctuation mark in a name mustn't reach the URL.
        .replace(/[^A-Za-z0-9]/g, '');
}

/**
 * Category -> its background page at Virtual Polyhedra.
 *
 * Not every category has one worth linking. 'parallelohedron' and 'chiral
 * polyhedron' are missing on purpose: Hart's glossary defines chirality but has
 * no per-term anchors to link to, and the good parallelohedron write-ups are
 * either Wikipedia or terse reference entries. Better a plain word than a
 * disappointing link; add them here when a good page turns up.
 */
const CATEGORY_PAGES = {
    'Platonic solid': 'platonic-info.html',
    'Archimedean solid': 'archimedean-info.html',
    'Johnson solid': 'johnson-info.html',
    'deltahedron': 'deltahedra-info.html',
    'quasiregular polyhedron': 'quasi-regular-info.html',
};

/** Categories we have deliberately decided not to link (see above). */
export const UNLINKED_CATEGORIES = ['parallelohedron', 'chiral polyhedron'];

/**
 * The page about one particular polyhedron.
 * @param {string} gridId - e.g. 'aC', used to look up the exceptions
 * @param {string} gridName - e.g. 'Cuboctahedron', which the rest derive from
 * @returns {string|null} a URL, or null without a name to work from
 */
export function solidLink(gridId, gridName) {
    const page = SOLID_PAGE_EXCEPTIONS[gridId]
        || (gridName ? derivePageName(gridName) : null);
    return page ? VISUAL_POLYHEDRA + page + '.html' : null;
}

/**
 * The page about a family or property of polyhedra.
 * @param {string} category - e.g. 'Archimedean solid', as in the catalogue
 * @returns {string|null} a URL, or null if we have none for this category
 */
export function categoryLink(category) {
    const page = CATEGORY_PAGES[category];
    return page ? VIRTUAL_POLYHEDRA + page : null;
}

/** Euler's formula, explained for a general reader. */
export const EULER_FORMULA_LINK = 'https://plus.maths.org/eulers-polyhedron-formula';
