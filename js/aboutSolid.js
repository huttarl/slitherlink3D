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
import {describeFaceCensus, describeVertexConfiguration, faceCensus, faceNamer,
        vertexConfiguration, vertexConfigurationNotation} from "./solidFacts.js";
import {categoryLink, ENDURING_ERROR_LINK, EULER_FORMULA_LINK,
        solidLink} from "./polyhedronLinks.js";

// Categories whose definition requires every vertex to be alike up to a symmetry
// of the whole solid -- vertex-transitive, in a word. A solid outside them that
// nevertheless has the same arrangement at every vertex is the interesting case;
// see buildAboutCard.
//
// Not only families: the uniform prisms and antiprisms are vertex-transitive
// too, and they are filed under "Miscellaneous" for want of a classical family.
// Leaving them out told the player that a pentagonal antiprism lacks a symmetry
// carrying any vertex to any other, which is false -- it has D(5d).
const VERTEX_TRANSITIVE_CATEGORIES = ['Platonic solid', 'Archimedean solid',
                                      'prism', 'antiprism'];

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
    panelHost.replaceChildren(buildAboutCard(facts));
    const toggle = document.getElementById('aboutSolidToggle');
    toggle.addEventListener('click', () => {
        const nowHidden = panelHost.classList.toggle('hidden');
        toggle.setAttribute('aria-expanded', String(!nowHidden));
    });

    // The celebration's copy, built now so it's ready whenever the player
    // solves the puzzle.
    document.getElementById('overlayAboutSolid')
        .replaceChildren(buildAboutCard(facts));
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
    // Measured once: both the census line and the vertex line read from it.
    const census = faceCensus(puzzleGrid);
    return {
        name: puzzleGrid.gridName,
        gridId: puzzleGrid.gridId,
        categories,
        // The categories that come with vertex-transitivity. Used to spot the
        // solids that manage the same arrangement at every vertex without
        // being in one -- see buildAboutCard.
        inUniformFamily: categories.some(
            category => VERTEX_TRANSITIVE_CATEGORIES.includes(category)),
        vertices: puzzleGrid.vertices.size,
        edges: puzzleGrid.edges.size,
        faces: puzzleGrid.faces.size,
        faceCensus: describeFaceCensus(census),
        // How to name a face of a given size ON THIS SOLID, so the vertex line
        // below can say "square" where the census measured squares and "rhombus"
        // where it measured rhombi -- a cycle of side counts can't tell them
        // apart by itself.
        nameFor: faceNamer(census),
        // null unless every vertex is alike -- see vertexConfiguration.
        vertexConfig: vertexConfiguration(puzzleGrid),
    };
}

/**
 * A link out to somewhere worth reading, or plain text if we have nowhere good
 * to send them (see polyhedronLinks.js -- an unmapped solid or category is a
 * deliberate "no link", not an oversight).
 *
 * New tab, since the player is mid-puzzle and navigating away would lose the
 * board. rel=noopener as always for target=_blank.
 *
 * @param {string} text
 * @param {string|null} href
 * @returns {Node} an <a>, or a bare text node
 */
function linkOrText(text, href) {
    if (!href) return document.createTextNode(text);
    const anchor = document.createElement('a');
    anchor.textContent = text;
    anchor.href = href;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    return anchor;
}

/**
 * The card itself, as a fragment (built per host: one DOM node can't be in two
 * places).
 *
 * @param {Object} facts - from collectFacts
 * @returns {DocumentFragment}
 */
function buildAboutCard(facts) {
    const card = document.createDocumentFragment();

    /**
     * Adds one line, with optional extra styling. Parts may be strings or
     * nodes, so a line can mix plain text with links; strings are appended as
     * text nodes and never as markup.
     */
    const line = (parts, className) => {
        const div = document.createElement('div');
        for (const part of [].concat(parts)) {
            div.append(part);
        }
        if (className) div.className = className;
        card.appendChild(div);
        return div;
    };

    /** A styled run of inline content, so two of them can share a line. */
    const span = (className, ...parts) => {
        const element = document.createElement('span');
        element.className = className;
        element.append(...parts);
        return element;
    };

    // Heading: the solid, then what it is --
    //     Cuboctahedron — Archimedean solid · quasiregular polyhedron
    // The name links to this solid's own page (an interactive model and its
    // statistics), and each family or property to its own background page. Shown
    // in the drawer as well as the celebration, even though the picker just
    // above already names the solid: the line is here to be the way out to
    // those pages.
    const heading = [span('about-name',
                          linkOrText(facts.name,
                                     solidLink(facts.gridId, facts.name)))];
    if (facts.categories.length > 0) {
        // Interleave the separators rather than joining, the parts being nodes.
        const categories = [];
        for (const category of facts.categories) {
            if (categories.length > 0) categories.push(' · ');
            categories.push(linkOrText(category, categoryLink(category)));
        }
        heading.push(' — ', span('about-categories', ...categories));
    }
    line(heading);

    line(`${facts.vertices} vertices, ${facts.edges} edges, `
         + `${facts.faces} faces (${facts.faceCensus})`);

    // Euler's formula. Different arithmetic on every solid, the same answer
    // every time: the cheapest way to hand someone a theorem to notice for
    // themselves. (Minus signs, not hyphens.)
    line([`${facts.vertices} − ${facts.edges} + ${facts.faces} = `
          + `${facts.vertices - facts.edges + facts.faces} (`,
          linkOrText("Euler's Formula", EULER_FORMULA_LINK),
          ')'],
         'about-euler');

    if (facts.vertexConfig) {
        // Only when every vertex has the same arrangement, which is most of
        // what the Platonic and Archimedean definitions turn on -- so saying it
        // teaches the definition without stating one. Most Johnson solids have
        // vertices of several kinds, and simply get no such line.
        line(`Same at every vertex: `
             + `${describeVertexConfiguration(facts.vertexConfig, facts.nameFor)} `
             + `(${vertexConfigurationNotation(facts.vertexConfig)})`);

        if (facts.categories.length > 0 && !facts.inUniformFamily) {
            // ...and here is the catch, which is far more interesting than the
            // rule: matching vertices are NOT sufficient. In the data as it
            // stands only the elongated square gyrobicupola (J37) reaches this
            // line -- it has the rhombicuboctahedron's 3.4.4.4 at all 24
            // vertices, and even the same V, E and F -- but the test is computed
            // rather than a name, so any other such solid gets it too.
            // Former message (too verbose):
            // line('Matching vertices aren\'t enough to make a solid Archimedean, '
            //      + 'though: that also needs a symmetry of the whole solid '
            //      + 'carrying any vertex to any other, and this one hasn\'t got '
            //      + 'it.', 'about-note');

            line(['\u2014 but not Archimedean. This shape has ',
                linkOrText('tripped mathematicians up', ENDURING_ERROR_LINK),
                ' for hundreds of years! '], 'about-note');
        }
    }


    return card;
}
