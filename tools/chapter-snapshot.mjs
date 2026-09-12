// Print what every chapter renders, so that moving prose out of code can be proved not
// to have changed it.
//
// Extracting 119 string literals from a 1799-line file is mechanical work, and
// mechanical work on that scale invites the paste error that reads perfectly well. A
// reviewer cannot catch a sentence that lost a word, and neither can the Python suite,
// which tests what the server computes rather than what the page says.
//
// So: capture a baseline before migrating a chapter, migrate it, capture again, diff.
// An empty diff is the claim. Because the world is deterministic -- RFC 6979 signing, a
// fixed instant, a published seed -- most chapters compare byte for byte.
//
// Same jsdom arrangement as ui-clicks.mjs, and the same reasoning about why jsdom is not
// a dependency of this project. Install it beside this file:
//
//   cd tools && npm install jsdom && cd ..
//   uv run vc-demo &
//   node tools/chapter-snapshot.mjs > /tmp/before.txt
//   ...migrate a chapter...
//   node tools/chapter-snapshot.mjs > /tmp/after.txt
//   diff /tmp/before.txt /tmp/after.txt
//
// Pass chapter ids to limit it: `node tools/chapter-snapshot.mjs orientation keys`.
//
// --text compares textContent instead of innerHTML. Use it when a chapter's markup is
// expected to change but its words are not, which is exactly the case when a literal
// table becomes a markdown one: the words are identical and the element order is not.
//
// Nothing here waits for a duration. It used to wait a fixed 1500 ms after changing the
// hash and then read the stage, which is enough against a warm server and not against a
// cold one -- ui-clicks.mjs was caught doing exactly that, reading one chapter's controls
// while the previous chapter was still on the page. The consequence is worse here than
// there. This tool's claim is that an empty diff proves the words did not change, and a
// sample taken mid-render captures the spinner or the chapter before it. That does not
// merely fail: it puts a difference in the baseline that has nothing to do with the
// migration being checked, or hides one that has.
//
// So the waiting is conditional, on the two things `show()` in app.js makes observable:
// `buildRail()` marks the active chapter synchronously when a render starts, and the
// `.spinner` it appends is removed when that render settles, on both the success and the
// error path. Add an idle network and a page is finished. A chapter that does not reach
// that state within the deadline is *not* snapshotted -- it is marked in the output and
// the run exits non-zero, because a missing chapter in a diff is honest and a wrongly
// sampled one is not.
//
// The same primitives are in ui-clicks.mjs, which is deliberate: these two tools already
// duplicate the jsdom arrangement, the globals and the fetch wrapper, and the header
// above says so. Correct one and correct the other.

const { JSDOM } = await import(process.env.VCQI_JSDOM || 'jsdom');
const { servedModules } = await import(new URL('served-modules.mjs', import.meta.url));

const BASE = process.env.VCQI_BASE || 'http://127.0.0.1:8000';

// A deadline, not a delay. Reaching it is a failure, not a cue to read the page anyway.
const READY_TIMEOUT = Number(process.env.VCQI_READY_TIMEOUT || 20000);
const POLL = 25;

const args = process.argv.slice(2);
const textOnly = args.includes('--text');
const wanted = new Set(args.filter((value) => !value.startsWith('--')));

const dom = new JSDOM(
  '<!doctype html><html><body><nav><ul id="rail-nav"></ul></nav><main id="stage"></main></body></html>',
  { url: `${BASE}/`, pretendToBeVisual: true }
);

global.window = dom.window;
global.document = dom.window.document;
global.Node = dom.window.Node;
global.Element = dom.window.Element;

dom.window.Element.prototype.scrollIntoView = function scrollIntoView() {};
dom.window.scrollTo = function scrollTo() {};

// Wrapped to resolve relative URLs against the server, and to know whether the page is
// still waiting on one. A snapshot taken with a request outstanding is a snapshot of a
// page that has not finished being itself.
const realFetch = global.fetch;
let inFlight = 0;
global.fetch = (input, init) => {
  inFlight += 1;
  let request;
  try {
    request = realFetch(String(input).startsWith('http') ? input : BASE + input, init);
  } catch (error) {
    inFlight -= 1;
    throw error;
  }
  return request.finally(() => {
    inFlight -= 1;
  });
};

// Keep render failures visible: a chapter that throws renders an error banner, which
// would otherwise show up in the diff as a puzzling few lines rather than as a problem.
const consoleErrors = [];
console.error = (...args) => consoleErrors.push(args.map(String).join(' '));

const unsettled = [];

const tick = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Wait for a condition to hold, polling until a deadline.
 *
 * @param {() => boolean} condition What the caller is waiting for.
 * @param {number} timeout How long to allow, in milliseconds.
 * @returns {Promise<boolean>} True if it held, false if the deadline passed.
 */
async function waitUntil(condition, timeout) {
  const deadline = Date.now() + timeout;
  for (;;) {
    if (condition()) return true;
    if (Date.now() >= deadline) return false;
    await tick(POLL);
  }
}

// The bytes the server sends, not the ones on disk: see served-modules.mjs for
// the failure that distinction let through.
const modules = await servedModules(BASE);
const { CHAPTERS } = await import(new URL('chapters.js', modules));
await import(new URL('app.js', modules));

const stage = document.getElementById('stage');

/** @returns {boolean} Whether the page has finished whatever it was doing. */
const quiet = () => inFlight === 0 && !stage.querySelector('.spinner');

/**
 * Which chapter the application believes it is showing.
 *
 * Set by `buildRail()` at the top of `show()`, before the chapter body exists, so it
 * says navigation has *started* where the spinner says it has finished. Both are needed:
 * between the hash changing and `show()` running there is a window in which the previous
 * chapter is on the stage and no spinner exists yet, and that window is what a fixed
 * delay lands in.
 *
 * @returns {number} Index into CHAPTERS, or -1 before the rail is built.
 */
const activeChapter = () =>
  [...document.querySelectorAll('#rail-nav .rail__link')].findIndex(
    (link) => link.getAttribute('aria-current') === 'true'
  );

if (!(await waitUntil(() => activeChapter() >= 0 && quiet(), READY_TIMEOUT))) {
  console.log(`===== the application never became ready within ${READY_TIMEOUT} ms =====`);
  process.exit(1);
}

// Whitespace is not content here. Indentation in a markdown file becomes different
// whitespace between tags than a JavaScript template literal did, and that difference
// carries no meaning for a reader.
const normalise = (value) => value.replace(/\s+/g, ' ').trim();

for (const [index, chapter] of CHAPTERS.entries()) {
  if (wanted.size && !wanted.has(chapter.id)) continue;

  dom.window.location.hash = chapter.id;

  // Both halves in one condition, so neither can be satisfied by the other: the rail has
  // to name *this* chapter, and the page has to have stopped working on it.
  if (!(await waitUntil(() => activeChapter() === index && quiet(), READY_TIMEOUT))) {
    unsettled.push(chapter.id);
    console.log(`===== ${chapter.id} =====`);
    console.log(`DID NOT SETTLE within ${READY_TIMEOUT} ms — not captured`);
    console.log('');
    continue;
  }

  const body = textOnly ? stage.textContent : stage.innerHTML;
  // One block per chapter, wrapped at a width that makes a diff readable rather than
  // reporting that one enormous line changed.
  const wrapped = normalise(body).replace(/(.{100})/g, '$1\n');
  console.log(`===== ${chapter.id} =====`);
  console.log(wrapped);
  console.log('');
}

if (consoleErrors.length) {
  console.log('===== console.error during rendering =====');
  for (const line of consoleErrors) console.log(line);
}

// A chapter that was not captured has to end the run non-zero as well. Left at zero, the
// marker above would sit in a baseline and the next diff would compare it against a real
// capture, reporting a change in prose that nobody made.
if (consoleErrors.length || unsettled.length) {
  if (unsettled.length) {
    console.log(`===== ${unsettled.length} chapter(s) did not settle: ${unsettled.join(' ')} =====`);
  }
  process.exit(1);
}
