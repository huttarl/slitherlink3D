/**
 * Tests for js/settings.js -- the player's settings across page loads.
 *
 * Node has no localStorage, so these install a fake one on globalThis. That is
 * exactly the arrangement settings.js is written for: it looks the storage up
 * per call rather than at import, so it can find one here and find nothing in
 * the headless tests that don't install it.
 *
 * The cases that matter are the hostile ones. Storage outlives the code and is
 * writable by anything else on the origin, so what comes back out of it is
 * input, not state: junk must leave the defaults standing rather than break the
 * page.
 *
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';

import { loadSettings, saveSetting } from '../settings.js';
import { SETTINGS_DEFAULTS } from '../constants.js';

const STORAGE_KEY = 'slitherlink3D.settings';

/** A localStorage stand-in, optionally one that throws like a blocked browser. */
function fakeStorage({failOnWrite = false, failOnRead = false} = {}) {
    const items = new Map();
    return {
        items,
        getItem(key) {
            if (failOnRead) throw new Error('storage blocked');
            return items.has(key) ? items.get(key) : null;
        },
        setItem(key, value) {
            if (failOnWrite) throw new Error('quota exceeded');
            items.set(key, String(value));
        },
    };
}

/** What the fake is holding, parsed. */
function stored(storage) {
    return JSON.parse(storage.items.get(STORAGE_KEY));
}

let saved;

beforeEach(() => {
    saved = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
});

afterEach(() => {
    if (saved) {
        Object.defineProperty(globalThis, 'localStorage', saved);
    } else {
        delete globalThis.localStorage;
    }
});

/** Installs a fake as globalThis.localStorage and returns it. */
function install(storage) {
    Object.defineProperty(globalThis, 'localStorage',
                          {value: storage, configurable: true, writable: true});
    return storage;
}

describe('loadSettings', () => {
    test('gives the defaults when nothing is stored', () => {
        install(fakeStorage());
        assert.deepStrictEqual(loadSettings(), SETTINGS_DEFAULTS);
    });

    test('gives the defaults when there is no storage at all', () => {
        // The headless case, and the file:// case: no localStorage on the page.
        delete globalThis.localStorage;
        assert.deepStrictEqual(loadSettings(), SETTINGS_DEFAULTS);
    });

    test('returns a fresh object, not SETTINGS_DEFAULTS itself', () => {
        // Callers treat the result as theirs; handing back the constant would
        // let one of them quietly redefine the defaults for everyone.
        install(fakeStorage());
        const settings = loadSettings();
        settings.autoTidy = 'clobbered';
        assert.strictEqual(SETTINGS_DEFAULTS.autoTidy, false);
    });

    test('a stored value overrides its default', () => {
        const storage = install(fakeStorage());
        storage.setItem(STORAGE_KEY, JSON.stringify({autoTidy: true}));
        assert.strictEqual(loadSettings().autoTidy, true);
    });

    test('settings not stored keep their defaults', () => {
        const storage = install(fakeStorage());
        storage.setItem(STORAGE_KEY, JSON.stringify({autoTidy: true}));
        assert.strictEqual(loadSettings().highlightRuleViolations,
                           SETTINGS_DEFAULTS.highlightRuleViolations);
    });

    test('an unknown key is ignored', () => {
        // A setting we have since renamed or dropped, or a neighbor's data.
        const storage = install(fakeStorage());
        storage.setItem(STORAGE_KEY, JSON.stringify({soundOn: false}));
        const settings = loadSettings();
        assert.ok(!('soundOn' in settings));
        assert.deepStrictEqual(settings, SETTINGS_DEFAULTS);
    });

    test('a value of the wrong type is ignored', () => {
        // A setting whose shape changed, or corrupted storage.
        const storage = install(fakeStorage());
        storage.setItem(STORAGE_KEY, JSON.stringify({autoTidy: 'yes please'}));
        assert.strictEqual(loadSettings().autoTidy, false);
    });

    test('unparseable storage leaves the defaults standing', () => {
        const storage = install(fakeStorage());
        storage.setItem(STORAGE_KEY, 'not json at all');
        assert.deepStrictEqual(loadSettings(), SETTINGS_DEFAULTS);
    });

    test('stored JSON that is not an object leaves the defaults standing', () => {
        const storage = install(fakeStorage());
        for (const junk of ['null', '42', '"a string"', '[1, 2, 3]']) {
            storage.setItem(STORAGE_KEY, junk);
            assert.deepStrictEqual(loadSettings(), SETTINGS_DEFAULTS,
                                   `stored ${junk} should give the defaults`);
        }
    });

    test('a read that throws leaves the defaults standing', () => {
        install(fakeStorage({failOnRead: true}));
        assert.deepStrictEqual(loadSettings(), SETTINGS_DEFAULTS);
    });
});

describe('saveSetting', () => {
    test('stores a value, which loadSettings then reports', () => {
        install(fakeStorage());
        saveSetting('autoTidy', true);
        assert.strictEqual(loadSettings().autoTidy, true);
    });

    test('stores ONLY the settings actually changed', () => {
        // The point: writing the whole merged object would freeze today's
        // defaults into every visitor's storage, so a later change to a default
        // would reach only people who had never visited before.
        const storage = install(fakeStorage());
        saveSetting('autoTidy', true);
        assert.deepStrictEqual(stored(storage), {autoTidy: true});
    });

    test('keeps settings stored earlier', () => {
        const storage = install(fakeStorage());
        saveSetting('autoTidy', true);
        saveSetting('highlightRuleViolations', false);
        assert.deepStrictEqual(stored(storage),
                               {autoTidy: true, highlightRuleViolations: false});
    });

    test('storing a setting again replaces it', () => {
        const storage = install(fakeStorage());
        saveSetting('autoTidy', true);
        saveSetting('autoTidy', false);
        assert.deepStrictEqual(stored(storage), {autoTidy: false});
    });

    test('refuses an unknown setting', () => {
        const storage = install(fakeStorage());
        saveSetting('notASetting', true);
        assert.strictEqual(storage.items.has(STORAGE_KEY), false);
    });

    test('a write that throws is survivable', () => {
        // Quota, private browsing, site data blocked. The setting still applies
        // to the page in front of the player; it just isn't remembered.
        install(fakeStorage({failOnWrite: true}));
        assert.doesNotThrow(() => saveSetting('autoTidy', true));
    });

    test('no storage at all is survivable', () => {
        delete globalThis.localStorage;
        assert.doesNotThrow(() => saveSetting('autoTidy', true));
    });
});

describe('SETTINGS_DEFAULTS', () => {
    test('holds no debug toggles', () => {
        // Show IDs and Show Solution are transient developer state, and a
        // persisted "Show Solution" would hand over the answer to every puzzle
        // the player opened afterwards.
        for (const key of ['showIDs', 'showSolution']) {
            assert.ok(!(key in SETTINGS_DEFAULTS), `${key} must not be stored`);
        }
    });

    test('every default is a plain boolean, string or number', () => {
        // loadSettings validates by typeof, which cannot tell one object shape
        // from another -- so a setting whose value is an object or array would
        // be accepted from storage unchecked. Keep them scalar, or teach
        // loadSettings to validate properly first.
        for (const [key, value] of Object.entries(SETTINGS_DEFAULTS)) {
            assert.ok(['boolean', 'string', 'number'].includes(typeof value),
                      `setting '${key}' should be a scalar, not ${typeof value}`);
        }
    });
});
