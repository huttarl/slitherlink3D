/**
 * Every module in js/ parses and its imports resolve.
 *
 * Cheap, but it catches a whole class of mistake the rest of the suite is blind
 * to. Most modules are never imported by a test -- clueRenderer, celebration,
 * ui, scene -- so until now a syntax error or a bad import in one of them showed
 * up only in the browser, as a blank page and a console message. ES modules are
 * linked before any code runs, so importing a module also proves:
 *
 *   - it parses;
 *   - every path it imports from exists;
 *   - every NAME it imports actually exists in the module it comes from -- a
 *     misspelled named import is a link-time error, not a runtime one.
 *
 * What it can't prove is that anything WORKS, and it isn't meant to. It replaces
 * the ad-hoc `node --check` pass that was being run by hand after touching a
 * module the tests don't reach.
 *
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const JS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');

/**
 * Modules that must NOT be imported here, with the reason.
 *
 * main.js is the browser entry point: it calls main() as it loads, which reaches
 * straight for document and throws in Node. Its import graph is still covered,
 * since everything it pulls in is checked below on its own account.
 */
const SKIP = new Map([
    ['main.js', 'entry point: runs main() on load, which needs a DOM'],
]);

/** Every module file in js/, excluding the vendored three/ subdirectory (a
 *  readdir of js/ lists that as a directory, not as .js files). */
function moduleFiles() {
    return readdirSync(JS_DIR).filter(name => name.endsWith('.js')).sort();
}

describe('every module in js/ loads', () => {
    test('there are modules to check, and this test can see them', () => {
        // Guards against the check silently passing because the glob broke.
        const files = moduleFiles();
        assert.ok(files.length > 20,
            `expected the app's modules, found ${files.length}`);
        assert.ok(files.includes('constants.js'), 'js/constants.js not found');
    });

    for (const name of moduleFiles()) {
        const reason = SKIP.get(name);
        test(name, {skip: reason}, async () => {
            const module = await import(`../${name}`);
            // Don't interpolate `module` into a message: a module namespace
            // object throws on String() -- the spec gives it no prototype and a
            // @@toPrimitive of undefined -- so a failure message mentioning it
            // would replace the real error with "Cannot convert object to
            // primitive value".
            assert.ok(module, `${name} imported as something falsy`);
            assert.ok(Object.keys(module).length > 0,
                `${name} exports nothing -- is that intended?`);
        });
    }
});
