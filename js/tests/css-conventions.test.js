/**
 * Conventions the page's CSS has to hold to, checked by reading main.html.
 *
 * These are here because layout bugs are invisible to the rest of the suite:
 * jsdom has no layout engine, so getBoundingClientRect returns zeros and
 * nothing about position or size can be asserted. A real browser can check it
 * (see js/tests/mobile/), but that needs Playwright installed; these rules cost
 * nothing and catch the specific mistakes this project has already made.
 *
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const HTML = readFileSync(join(REPO_ROOT, 'main.html'), 'utf8');

/** The contents of every <style> element, concatenated. */
function styleSheets(html) {
    return [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)]
        .map(m => m[1]).join('\n');
}

/**
 * Every rule in the page's stylesheets, as {selector, body} -- flat, so nested
 * at-rules (media queries) contribute their inner rules and nothing else. Good
 * enough for spot-checking conventions; this is not a CSS parser.
 */
function cssRules(html) {
    const css = styleSheets(html).replace(/\/\*[\s\S]*?\*\//g, '');  // strip comments
    const rules = [];
    for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
        const selector = m[1].trim().replace(/\s+/g, ' ');
        if (selector.startsWith('@')) continue;   // at-rule preamble, not a rule
        rules.push({selector, body: m[2]});
    }
    return rules;
}

/** Inline style="..." attributes, with a little context for the message. */
function inlineStyles(html) {
    return [...html.matchAll(/<(\w+)[^>]*\bstyle="([^"]*)"/g)]
        .map(m => ({tag: m[1], body: m[2]}));
}

const declares = (body, property) =>
    new RegExp(`(^|;|\\s)${property}\\s*:`, 'i').test(body);

describe('CSS conventions in main.html', () => {
    test('nothing is bottom-anchored with position: absolute', () => {
        // The bug this encodes: the check-result toast was position: absolute
        // inside #canvas-container, which is 100vh tall. On a phone 100vh is
        // the LARGE viewport -- it includes the band behind the browser's
        // toolbars -- so the toast came to rest ~110px below the visible area
        // and tapping "Check solution" seemed to do nothing. On desktop 100vh
        // is the whole window, so it looked right everywhere we tested.
        //
        // Bottom-anchored overlays must be position: fixed, which anchors to
        // the viewport instead. (Top-anchored absolute elements are fine: the
        // top of the layout viewport is the top of the screen.) Horizontal
        // anchoring is unaffected -- toolbars take vertical space, not width.
        const offenders = cssRules(HTML)
            .filter(r => /position\s*:\s*absolute/i.test(r.body)
                         && declares(r.body, 'bottom'))
            .map(r => r.selector);
        assert.deepStrictEqual(offenders, [],
            `Bottom-anchored with position: absolute: ${offenders.join(', ')}. `
            + 'Use position: fixed, or the element can land below the visible '
            + 'area on a phone, where 100vh exceeds the screen height.');
    });

    test('no inline style is bottom-anchored with position: absolute', () => {
        const offenders = inlineStyles(HTML)
            .filter(s => /position\s*:\s*absolute/i.test(s.body)
                         && declares(s.body, 'bottom'))
            .map(s => `<${s.tag} style="${s.body}">`);
        assert.deepStrictEqual(offenders, [], offenders.join('; '));
    });

    test('a 100vh height is paired with a 100dvh fallback', () => {
        // Same root cause from the other side: 100vh is the large viewport on a
        // phone, so a container sized that way extends past the screen. Declare
        // 100vh first (for browsers without dvh), then 100dvh to override.
        const offenders = cssRules(HTML)
            .filter(r => /height\s*:\s*100vh/i.test(r.body)
                         && !/height\s*:\s*100dvh/i.test(r.body))
            .map(r => r.selector);
        assert.deepStrictEqual(offenders, [],
            `Sets height: 100vh with no 100dvh companion: ${offenders.join(', ')}.`);
    });

    test('the checks above actually see the stylesheet', () => {
        // A regex suite that silently matches nothing would pass forever.
        const rules = cssRules(HTML);
        assert.ok(rules.length > 20,
            `Only found ${rules.length} CSS rules; the parsing above is broken.`);
        assert.ok(rules.some(r => r.selector === '#checkToast'),
            'Did not find the #checkToast rule, so these checks prove nothing.');
        assert.ok(rules.some(r => /position\s*:\s*fixed/i.test(r.body)),
            'Found no position: fixed rule at all; parsing is suspect.');
    });
});
