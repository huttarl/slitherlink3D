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
import {CELEBRATION_TUNE, SETTINGS_DEFAULTS} from './constants.js';
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
 * The gain node the current play's notes all route through, or null when no
 * tune has been started. One node per play, so stopCelebrationTune can fade
 * the whole phrase at once -- the notes are fire-and-forget oscillators, so
 * there is nothing else to get hold of once they are scheduled.
 *
 * @type {?GainNode}
 */
let currentPlay = null;

/**
 * Whether sound is wanted at all -- the player's setting, which ui.js writes
 * here from the checkbox (the same arrangement PuzzleGrid's flags use, so this
 * module needs no import from the settings or UI layers).
 *
 * Held rather than read from storage per play, deliberately: under file:// there
 * is no storage to read, and a player who muted would go on hearing the tune.
 * Starts at the default, so a page whose wiring never runs still behaves.
 *
 * @type {boolean}
 */
let soundEnabled = SETTINGS_DEFAULTS.soundOn;

/**
 * Turns sound on or off. Switching it OFF silences anything already playing:
 * a mute that waits for the current tune to finish is not a mute.
 *
 * @param {boolean} on
 */
export function setSoundEnabled(on) {
    soundEnabled = on;
    if (!on) stopCelebrationTune();
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
 * @param {GainNode} out - where the note plays into
 */
function scheduleNote(ctx, hz, startAt, seconds, out) {
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

    oscillator.connect(envelope).connect(out);
    oscillator.start(startAt);
    oscillator.stop(startAt + seconds);
}

/**
 * Fades the playing tune out over a moment, for when the player skips or breaks
 * off the celebration -- a tune that plays on is the audio version of the stale
 * "Congratulations". A short ramp rather than silence at once, which clicks
 * (see scheduleNote on why every edge in a waveform needs an envelope). The
 * notes' oscillators still stop themselves on their original schedule; they are
 * merely inaudible from here on. Safe to call when nothing is playing.
 */
export function stopCelebrationTune() {
    if (!currentPlay || !audio) return;
    debug('celebration tune: faded out early');
    const now = audio.currentTime;
    // The master gain is a constant 1 (the shaping is per note), so the ramp
    // can anchor there rather than needing the current computed value.
    currentPlay.gain.setValueAtTime(1, now);
    currentPlay.gain.exponentialRampToValueAtTime(0.0001, now + 0.15);
    currentPlay = null;
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
    if (!soundEnabled) {
        debug('celebration tune: skipped, sound is off');
        return;
    }
    const ctx = context();
    if (!ctx) return;
    // A context created before the first gesture starts out suspended; a solve is
    // always reached through one, so this resolves immediately in practice.
    if (ctx.state === 'suspended') ctx.resume();

    debug(`celebration tune: playing (context ${ctx.state})`);
    const {notes, noteSeconds, holdSeconds} = CELEBRATION_TUNE;
    // Everything routes through one master gain so the play can be faded as a
    // whole (see stopCelebrationTune). Made fresh per play and left for the
    // garbage collector once its notes end; only the envelopes do any shaping.
    const master = ctx.createGain();
    master.gain.value = 1;
    master.connect(ctx.destination);
    currentPlay = master;

    let at = ctx.currentTime;
    for (let i = 0; i < notes.length; i++) {
        const semitones = SEMITONES[notes[i]]; // number of semitones away from C
        if (semitones === undefined) {
            debug(`celebration tune: no such note '${notes[i]}'`);
            continue;
        }
        // The last note is held, which is what makes the phrase end rather than
        // merely stop.
        const seconds = (i === notes.length - 1) ? holdSeconds : noteSeconds;
        scheduleNote(ctx, TONIC_HZ * Math.pow(2, semitones / 12), at, seconds,
                     master);
        at += seconds;
    }
}
