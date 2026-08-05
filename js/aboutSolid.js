/**
 * "About this solid": a few facts about the polyhedron the player is on.
 *
 * The aim is gentle: someone who came for the puzzle may leave knowing that
 * these shapes have families and reasons for existing. So it is strictly
 * opt-in and never in the way -- behind an ⓘ in the drawer, and below the Next
 * button on the celebration overlay (see ideas/learning-about-polys.md).
 *
 * Two places, one card: the drawer serves the player who gets curious
 * mid-puzzle, or who never finishes a 32-face grid; the celebration serves the
 * one who has just spent twenty minutes with the shape and earned the interest.
 *
 * Everything shown is either read off the loaded grid or is one line of
 * catalogue data. Nothing here needs hand-written prose, which is what makes it
 * work for every solid added later.
 */
import {loadCatalogue} from "./catalogue.js";
import {describeFaceCensus, describeVertexConfiguration, faceCensus,
        vertexConfiguration, vertexConfigurationNotation} from "./solidFacts.js";

// The families whose definition requires every vertex to be alike (up to a
// symmetry of the whole solid). A solid outside them that nevertheless has the
// same arrangement at every vertex is the interesting case; see buildAboutCard.
const UNIFORM_VERTEX_FAMILIES = ['Platonic solid', 'Archimedean solid'];

/**
 * Builds the card and wires the drawer's ⓘ toggle. Safe to call before the
 * catalogue has loaded; it awaits it itself.
 *
 * @param {GameState} gameState
 */
export async function initAboutSolid(gameState) {
    const puzzleGrid = gameState.getPuzzleGrid();

    // The categories are the one thing that isn't in the grid, so a catalogue
    // that fails to load costs us that line and nothing else.
    // Matched on the LOADED grid's own id, not the ?grid= parameter: those
    // disagree when a bad or removed grid was asked for and createGameState fell
    // back to another one, and the card must describe what's on screen.
    let categories = [];
    try {
        const catalogue = await loadCatalogue();
        const entry = catalogue.grids.find(grid => grid.gridId === puzzleGrid.gridId
                                                  || grid.file === puzzleGrid.gridId);
        if (entry) categories = entry.categories || [];
    } catch (err) {
        console.warn('About this solid: no catalogue, so no categories:', err);
    }

    const facts = collectFacts(puzzleGrid, categories);

    // The drawer's copy, behind the ⓘ.
    const panelHost = document.getElementById('aboutSolid');
    panelHost.replaceChildren(buildAboutCard(facts, {withName: false}));
    const toggle = document.getElementById('aboutSolidToggle');
    toggle.addEventListener('click', () => {
        const nowHidden = panelHost.classList.toggle('hidden');
        toggle.setAttribute('aria-expanded', String(!nowHidden));
    });

    // The celebration's copy, built now so it's ready whenever the player
    // solves the puzzle. It names the solid: it sits below the Next button,
    // away from the sentence that would otherwise have said which solid.
    document.getElementById('overlayAboutSolid')
        .replaceChildren(buildAboutCard(facts, {withName: true}));
}

/**
 * Gathers what the card shows.
 *
 * Counts come from the loaded grid rather than the catalogue, so the card can
 * never disagree with the solid on screen (and still works if data/grids.json
 * is stale).
 *
 * @param {PuzzleGrid} puzzleGrid
 * @param {string[]} categories - from the catalogue entry
 */
function collectFacts(puzzleGrid, categories) {
    return {
        name: puzzleGrid.gridName,
        categories,
        // The families defined BY every vertex being alike. Used to spot the
        // solids that manage the same arrangement at every vertex without
        // being in one -- see buildAboutCard.
        inUniformFamily: categories.some(
            category => UNIFORM_VERTEX_FAMILIES.includes(category)),
        vertices: puzzleGrid.vertices.size,
        edges: puzzleGrid.edges.size,
        faces: puzzleGrid.faces.size,
        faceCensus: describeFaceCensus(faceCensus(puzzleGrid)),
        // null unless every vertex is alike -- see vertexConfiguration.
        vertexConfig: vertexConfiguration(puzzleGrid),
    };
}

/**
 * The card itself, as a fragment (built per host: one DOM node can't be in two
 * places).
 *
 * @param {Object} facts - from collectFacts
 * @param {{withName: boolean}} options
 * @returns {DocumentFragment}
 */
function buildAboutCard(facts, {withName}) {
    const card = document.createDocumentFragment();

    /** Adds one line, with optional extra styling. */
    const line = (text, className) => {
        const div = document.createElement('div');
        div.textContent = text;
        if (className) div.className = className;
        card.appendChild(div);
        return div;
    };

    if (withName) line(facts.name, 'about-name');
    if (facts.categories.length > 0) {
        line(facts.categories.join(' · '), 'about-categories');
    }
    line(`${facts.vertices} vertices, ${facts.edges} edges, `
         + `${facts.faces} faces (${facts.faceCensus})`);

    // Euler's formula. Different arithmetic on every solid, the same answer
    // every time: the cheapest way to hand someone a theorem to notice for
    // themselves. (Minus signs, not hyphens.)
    line(`${facts.vertices} − ${facts.edges} + ${facts.faces} = `
         + `${facts.vertices - facts.edges + facts.faces} (Euler's Formula)`,
         'about-euler');

    if (facts.vertexConfig) {
        // Only when every vertex has the same arrangement, which is most of
        // what the Platonic and Archimedean definitions turn on -- so saying it
        // teaches the definition without stating one. Most Johnson solids have
        // vertices of several kinds, and simply get no such line.
        line(`Same at every vertex: `
             + `${describeVertexConfiguration(facts.vertexConfig)} `
             + `(${vertexConfigurationNotation(facts.vertexConfig)})`);

        if (facts.categories.length > 0 && !facts.inUniformFamily) {
            // ...and here is the catch, which is far more interesting than the
            // rule: matching vertices are NOT sufficient. In the data as it
            // stands only the elongated square gyrobicupola (J37) reaches this
            // line -- it has the rhombicuboctahedron's 3.4.4.4 at all 24
            // vertices, and even the same V, E and F -- but the test is computed
            // rather than a name, so any other such solid gets it too.
            line('Matching vertices aren\'t enough to make a solid Archimedean, '
                 + 'though: that also needs a symmetry of the whole solid '
                 + 'carrying any vertex to any other, and this one hasn\'t got '
                 + 'it.', 'about-note');
        }
    }


    return card;
}
