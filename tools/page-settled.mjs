// When a chapter has finished rendering, and how both jsdom harnesses agree about it.
//
// `ui-clicks.mjs` and `chapter-snapshot.mjs` both drive the real application in jsdom,
// and both used to wait a fixed number of milliseconds after changing the hash and then
// read the page. Against a warm server that is plenty. Against a cold one the first
// content fetches outrun it and the harness reads the stage while the *previous* chapter
// is still on it.
//
// That was caught in `ui-clicks.mjs`, once, as `FAILED: 4 inert control(s)` with chapter
// 11's fourteen controls counted against chapter 12 and chapter 11 credited with none.
// It could as easily have gone the other way and reported a clean run for a page it never
// looked at. In `chapter-snapshot.mjs` the same race captures the spinner instead of the
// chapter, which puts a difference into a baseline that nobody made -- or hides one that
// somebody did.
//
// The conditions were always there to be read. In `show()` in app.js:
//
//   - `buildRail()` marks the active chapter **synchronously**, when a render starts.
//   - The `.spinner` it appends is removed when that render settles, on the success path
//     and the error path both.
//
// Both halves are needed and neither will do alone. The spinner alone is satisfied in the
// window between the hash changing and `show()` running, when the previous chapter is on
// the stage and no spinner exists yet -- which is exactly where a fixed delay lands. The
// rail alone is satisfied the instant a render starts, before there is anything to read.
//
// An idle network is the third part, which is why the fetch wrapper lives here too: a
// counter of requests in flight is what separates "the page did not change" from "the
// page has not changed yet".
//
// Nothing here waits for a duration. Every wait is for a condition with a deadline, and
// every caller treats reaching that deadline as a result to report rather than a cue to
// read the page anyway. Raising a timeout cannot make a wrong answer right; it can only
// make a slow one possible.

const POLL = 25;

/** Deadline for a chapter to start and finish rendering. */
export const READY_TIMEOUT = Number(process.env.VCQI_READY_TIMEOUT || 20000);

/** Deadline for the page to respond to a click before the control is called inert. */
export const CLICK_TIMEOUT = Number(process.env.VCQI_CLICK_TIMEOUT || 5000);

const tick = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Wait for a condition to hold, polling until a deadline.
 *
 * @param {() => boolean} condition What the caller is waiting for.
 * @param {number} timeout How long to allow, in milliseconds.
 * @returns {Promise<boolean>} True if it held, false if the deadline passed.
 */
export async function waitUntil(condition, timeout) {
  const deadline = Date.now() + timeout;
  for (;;) {
    if (condition()) return true;
    if (Date.now() >= deadline) return false;
    await tick(POLL);
  }
}

/**
 * Wrap `fetch` so relative URLs reach the server and in-flight requests can be counted.
 *
 * Call this before importing app.js, which is what installs the code that fetches.
 *
 * @param {string} base Origin to resolve relative URLs against.
 * @returns {() => number} How many requests are outstanding right now.
 */
export function instrumentFetch(base) {
  const realFetch = globalThis.fetch;
  let inFlight = 0;

  globalThis.fetch = (input, init) => {
    inFlight += 1;
    let request;
    try {
      request = realFetch(String(input).startsWith('http') ? input : base + input, init);
    } catch (error) {
      // A synchronous throw never reaches the `finally` below, and a counter that only
      // goes up would leave every later wait believing the page is still busy.
      inFlight -= 1;
      throw error;
    }
    return request.finally(() => {
      inFlight -= 1;
    });
  };

  return () => inFlight;
}

/**
 * Build the predicates and waits that describe one running application.
 *
 * @param {object} options
 * @param {Document} options.document The jsdom document.
 * @param {Element} options.stage The `#stage` element the application renders into.
 * @param {() => number} options.pending From :func:`instrumentFetch`.
 * @returns {object} Predicates `quiet` and `activeChapter`, and the waits built on them.
 */
export function pageState({ document, stage, pending }) {
  /** @returns {boolean} Whether the page has finished whatever it was doing. */
  const quiet = () => pending() === 0 && !stage.querySelector('.spinner');

  /** @returns {number} Index of the chapter the rail says is active, or -1. */
  const activeChapter = () =>
    [...document.querySelectorAll('#rail-nav .rail__link')].findIndex(
      (link) => link.getAttribute('aria-current') === 'true'
    );

  return {
    quiet,
    activeChapter,

    /** The application has booted and shown something. */
    ready: (timeout = READY_TIMEOUT) =>
      waitUntil(() => activeChapter() >= 0 && quiet(), timeout),

    /** The chapter at `index` is the one on the stage, and it has finished arriving. */
    showing: (index, timeout = READY_TIMEOUT) =>
      waitUntil(() => activeChapter() === index && quiet(), timeout),

    /** Nothing is outstanding. Used to let one control finish before the next is tried. */
    idle: (timeout = READY_TIMEOUT) => waitUntil(quiet, timeout),

    /** The stage text differs from `before`. Returns as soon as it does. */
    changedFrom: (before, timeout = CLICK_TIMEOUT) =>
      waitUntil(() => stage.textContent !== before, timeout),
  };
}
