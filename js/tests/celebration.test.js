/**
 * Tests for the celebration's timing constants.
 *
 * Not the animation itself -- that needs a scene and a render loop, and the
 * Playwright suite watches the dialog arrive at the end of it. What is worth
 * pinning here is the arithmetic BETWEEN the constants, because the loop's swell
 * and the tune are deliberately separate (the visual has to stand alone when the
 * browser blocks audio) and nothing else would notice them drifting apart.
 *
 * Run with: node --test js/tests   (or: npm test)
 */
import { test, describe } from 'node:test';
import assert from 'node:assert';

import { CELEBRATION_TIMING, CELEBRATION_TUNE } from '../constants.js';

/** How long one cycle of the tune lasts: the phrase, at the note length. */
function cycleSeconds() {
    return CELEBRATION_TUNE.phrase.length * CELEBRATION_TUNE.noteSeconds;
}

describe('the tune', () => {
    test('is its phrase repeated, then the held tonic', () => {
        const {phrase, repeats, notes} = CELEBRATION_TUNE;
        assert.strictEqual(notes.length, phrase.length * repeats + 1);
        for (let repeat = 0; repeat < repeats; repeat++) {
            assert.deepStrictEqual(
                notes.slice(repeat * phrase.length, (repeat + 1) * phrase.length),
                phrase, `repeat ${repeat + 1} is not the phrase`);
        }
        // The held note ends the phrase by coming home to the tonic; playing it
        // is what celebrationSound.js treats specially as the last note.
        assert.strictEqual(notes[notes.length - 1], 'C');
    });

    test('every note is one celebrationSound knows', () => {
        // The synth skips a letter it has no semitone for, so a typo would be a
        // silent gap rather than an error. SEMITONES is private to that module,
        // so this pins the alphabet it accepts.
        for (const note of CELEBRATION_TUNE.notes) {
            assert.match(note, /^[CDEFGAB]$/, `unplayable note '${note}'`);
        }
    });
});

describe('the loop swell', () => {
    test('runs one swell per cycle of the tune', () => {
        // The point of the test: a single swell against two cycles left the loop
        // still while the music carried on, which read as the animation stopping
        // early. These two numbers live in different constants, so keep them
        // equal here rather than trusting a comment.
        assert.strictEqual(CELEBRATION_TIMING.swellCycles,
                           CELEBRATION_TUNE.repeats);
        assert.ok(Math.abs(CELEBRATION_TIMING.swellSeconds - cycleSeconds())
                  < 1e-9,
            `one swell is ${CELEBRATION_TIMING.swellSeconds}s but a cycle of the `
            + `tune is ${cycleSeconds()}s`);
    });

    test('the swelling is over before the dialog covers it', () => {
        // Beat 1 has to finish while it can still be seen; the dialog sits over
        // the middle of the board.
        const swelling = CELEBRATION_TIMING.swellSeconds
                         * CELEBRATION_TIMING.swellCycles;
        assert.ok(swelling < CELEBRATION_TIMING.dialogSeconds,
            `swelling runs ${swelling}s, dialog opens at `
            + `${CELEBRATION_TIMING.dialogSeconds}s`);
    });

    test('the partition colours arrive while the loop is still pulsing', () => {
        // They should overlap: the loop lighting up and the surface colouring in
        // are one event, and a gap between them would read as two.
        assert.ok(CELEBRATION_TIMING.partitionStartSeconds
                  < CELEBRATION_TIMING.swellSeconds
                    * CELEBRATION_TIMING.swellCycles);
    });
});
