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
 * Every URL below was checked against those sites' own index pages on
 * 2026-08-04. Guessing them from names doesn't work -- see the chirality note.
 *
 * A missing entry is fine and means "no link": the card leaves the text plain
 * rather than sending anyone somewhere unhelpful. js/tests/polyhedronLinks.test.js
 * checks that every grid in the catalogue is covered, so a newly added
 * polyhedron can't quietly lose its link.
 */

const VISUAL_POLYHEDRA = 'https://dmccooey.com/polyhedra/';
const VIRTUAL_POLYHEDRA = 'https://www.georgehart.com/virtual-polyhedra/';

/**
 * gridId -> its page at Visual Polyhedra.
 *
 * Mostly the name in PascalCase, but not reliably: the chiral solids have
 * SEPARATE laevo and dextro pages and no plain one (SnubCube.html is a 404), so
 * those entries point at the laevo page and the card claims nothing about which
 * hand our model is. The two forms are mirror images, so the page teaches the
 * same solid either way.
 */
const SOLID_PAGES = {
    // Platonic. Keyed by gridId, which is NOT always the data file's stem: the
    // cube's file is cube.json but its gridId is 'C'.
    T: 'Tetrahedron',
    C: 'Cube',
    O: 'Octahedron',
    D: 'Dodecahedron',
    I: 'Icosahedron',
    // Archimedean
    tT: 'TruncatedTetrahedron',
    aC: 'Cuboctahedron',
    tC: 'TruncatedCube',
    tO: 'TruncatedOctahedron',
    eC: 'Rhombicuboctahedron',
    bC: 'TruncatedCuboctahedron',
    sC: 'LsnubCube',              // chiral; see above
    aD: 'Icosidodecahedron',
    tD: 'TruncatedDodecahedron',
    tI: 'TruncatedIcosahedron',
    eD: 'Rhombicosidodecahedron',
    sD: 'LsnubDodecahedron',      // chiral; see above
    bD: 'TruncatedIcosidodecahedron',
    // Johnson
    J1: 'SquarePyramid',
    J2: 'PentagonalPyramid',
    J3: 'TriangularCupola',
    J10: 'GyroelongatedSquarePyramid',
    J37: 'ElongatedSquareGyrobicupola',
    J47: 'GyroelongatedPentagonalCupolarotunda',
    J48: 'GyroelongatedPentagonalBirotunda',
    J75: 'TrigyrateRhombicosidodecahedron',
};

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
 * @param {string} gridId - e.g. 'aC'
 * @returns {string|null} a URL, or null if we have none for this grid
 */
export function solidLink(gridId) {
    const page = SOLID_PAGES[gridId];
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
