/**
 * The little tune that plays when a puzzle is solved.
 *
 * Synthesized rather than loaded: the phrase is a dozen notes of a scale, so an
 * audio file would be a download and a decode for something the Web Audio API
 * can make from three oscillator parameters. Nothing to fetch, nothing to cache,
 * and the tune is editable in js/constants.js as letters.
 *
 * On autoplay policy: browsers refuse to start audio until the user has
 * interacted with the page, which is why this is safe to call here and would not
 * be from a timer on page load. A solve always arrives through a click or a
 * keypress on "Check solution", so the gesture has always happened.
 */
import {CELEBRATION_TUNE} from './constants.js';
import {debug} from './debug.js';

/** Middle C, the tune's tonic. */
const TONIC_HZ = 261.6255653005986;

/**
 * Semitones from the tonic for each letter the tune may use.
 *
 * A and B are NEGATIVE -- the A and B below middle C, not above it. That is what
 * makes "C B A B C" a dip below the tonic and back, and it is the whole reason
 * the phrase sounds like it has come home at the end.
 */
const SEMITONES = {C: 0, D: 2, E: 4, F: 5, G: 7, A: -3, B: -1};

/**
 * The shared AudioContext, made on first use.
 *
 * One for the page, not one per solve: browsers cap how many a document may
 * have (Chrome has long allowed about six), so a fresh context each time would
 * eventually fail silently on a player working through a lot of puzzles.
 *
 * @type {?AudioContext}
 */
let audio = null;

/** The context, or null if this browser has no Web Audio at all. */
function context() {
    if (audio) return audio;
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return null;
    audio = new AudioCtor();
    return audio;
}

/**
 * Schedules one note.
 *
 * The envelope is the point of the gain node: an oscillator switched on and off
 * at full amplitude clicks, because the waveform jumps from silence to mid-cycle.
 * A few milliseconds of attack and a decay to near-silence remove both clicks.
 * The decay is exponential because loudness is perceived that way -- a linear
 * fade sounds like it stops abruptly at the end.
 *
 * @param {AudioContext} ctx
 * @param {number} hz
 * @param {number} startAt - context time to begin
 * @param {number} seconds - how long the note lasts
 */
function scheduleNote(ctx, hz, startAt, seconds) {
    const oscillator = ctx.createOscillator();
    oscillator.type = CELEBRATION_TUNE.waveform;
    oscillator.frequency.value = hz;

    const envelope = ctx.createGain();
    const attack = Math.min(0.006, seconds / 4);
    envelope.gain.setValueAtTime(0.0001, startAt);
    envelope.gain.linearRampToValueAtTime(CELEBRATION_TUNE.peakGain,
                                          startAt + attack);
    // Not to 0: exponentialRampToValueAtTime cannot reach zero, and asking it to
    // is an error in some browsers.
    envelope.gain.exponentialRampToValueAtTime(0.0001, startAt + seconds);

    oscillator.connect(envelope).connect(ctx.destination);
    oscillator.start(startAt);
    oscillator.stop(startAt + seconds);
}

/**
 * Plays the celebration tune, starting now. Returns silently if the browser has
 * no Web Audio, or if a letter in the tune isn't one this knows.
 *
 * Fire and forget: every note is scheduled up front against the audio clock, so
 * the phrase keeps perfect time regardless of what the render loop is doing --
 * which a chain of setTimeouts would not.
 */
export function playCelebrationTune() {
    const ctx = context();
    if (!ctx) return;
    // A context created before the first gesture starts out suspended; a solve is
    // always reached through one, so this resolves immediately in practice.
    if (ctx.state === 'suspended') ctx.resume();

    const {notes, noteSeconds, holdSeconds} = CELEBRATION_TUNE;
    let at = ctx.currentTime;
    for (let i = 0; i < notes.length; i++) {
        const semitones = SEMITONES[notes[i]];
        if (semitones === undefined) {
            debug(`celebration tune: no such note '${notes[i]}'`);
            continue;
        }
        // The last note is held, which is what makes the phrase end rather than
        // merely stop.
        const seconds = (i === notes.length - 1) ? holdSeconds : noteSeconds;
        scheduleNote(ctx, TONIC_HZ * Math.pow(2, semitones / 12), at, seconds);
        at += seconds;
    }
}
