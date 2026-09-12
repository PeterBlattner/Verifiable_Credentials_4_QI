// Click every control on every chapter and report any that do nothing.
//
// This exists because of a bug the Python suite could not have found. The document
// inspector was appended to the page only for a hardcoded list of chapter ids, so a
// chapter that was not on the list could fetch a document perfectly well and render it
// into a node that had never been put in the page. Every request succeeded, every test
// passed, and seven buttons in chapter 7 did nothing at all.
//
// Rendering a chapter is not the same as using one, so this drives the real application
// in a real DOM: load it, navigate, click, and check that the page actually changed.
//
// It needs jsdom, which is deliberately not a dependency of this project: nothing that
// ships needs npm, and that should stay true. Install it beside this file, where node
// will find it without anything being added to the project:
//
//   cd tools && npm install jsdom && cd ..
//   uv run vc-demo &
//   node tools/ui-clicks.mjs
//
// tools/node_modules is gitignored. If you would rather keep it out of the repository
// altogether, install jsdom anywhere and point at it instead, since ESM does not consult
// NODE_PATH:
//
//   VCQI_JSDOM=file:///somewhere/node_modules/jsdom/lib/api.js node tools/ui-clicks.mjs
//
// A button that is already the selected option is skipped rather than clicked: choosing
// the tab you are already on is meant to change nothing, and counting that as a failure
// would train everyone to ignore the output.
//
// Three things make this fail, and the second and third were added after it reported
// success on a demonstrably broken page: an inert control, a chapter that did not render
// at all, and anything written to console.error. The middle one is the trap -- a chapter
// that throws has no buttons, so "0 controls, all responded" was true and meaningless.
//
// A fourth was added for the same reason, and it is the subtlest of them. This harness
// used to wait a fixed 1400 ms after changing the hash and then read the page. Against a
// warm server that is plenty; against a cold one the first content fetches outrun it, and
// the harness reads the stage while the *previous* chapter is still on it. Observed once
// as `FAILED: 4 inert control(s)` with chapter 11's fourteen controls counted against
// chapter 12 and chapter 11 credited with none -- and the failure could just as easily
// have gone the other way and reported a clean run for a page it never looked at.
//
// So nothing here waits for a duration any more. It waits for a condition and gives up
// after a deadline, and giving up is itself reported rather than passed over. The two
// conditions come from `show()` in app.js: `buildRail()` marks the active chapter
// synchronously when a render starts, and the `.spinner` it appends is removed when that
// render settles, on both the success and the error path. Add an idle network and that is
// "this page is finished" stated exactly rather than estimated.
//
// VCQI_SETTLE is gone with the delays it configured. VCQI_READY_TIMEOUT and
// VCQI_CLICK_TIMEOUT are deadlines, and raising them cannot make a wrong result right --
// only a slow one possible.

// Resolved at run time so the module can come from beside this file or from wherever
// the operator already has it.
const { JSDOM } = await import(process.env.VCQI_JSDOM || 'jsdom');
const { servedModules } = await import(new URL('served-modules.mjs', import.meta.url));

const BASE = process.env.VCQI_BASE || 'http://127.0.0.1:8000';

// Deadlines, not delays. Reaching one is a failure, not a cue to carry on and look.
const READY_TIMEOUT = Number(process.env.VCQI_READY_TIMEOUT || 20000);
const CLICK_TIMEOUT = Number(process.env.VCQI_CLICK_TIMEOUT || 5000);
const POLL = 25;

const dom = new JSDOM(
  '<!doctype html><html><body><nav><ul id="rail-nav"></ul></nav><main id="stage"></main></body></html>',
  { url: `${BASE}/`, pretendToBeVisual: true }
);

global.window = dom.window;
global.document = dom.window.document;
global.Node = dom.window.Node;
global.Element = dom.window.Element;

// jsdom implements no layout, so scrolling is a no-op here.
dom.window.Element.prototype.scrollIntoView = function scrollIntoView() {};
dom.window.scrollTo = function scrollTo() {};

// Wrapped for two reasons: to resolve relative URLs against the server, and to know
// whether the page is still waiting on it. Without the second, "the stage did not change"
// cannot be told apart from "the stage has not changed yet".
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

const consoleErrors = [];
console.error = (...args) => consoleErrors.push(args.map(String).join(' '));

const contentMissing = [];
const unsettled = [];

const tick = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Wait for a condition to hold, polling until a deadline.
 *
 * @param {() => boolean} condition What the caller is waiting for.
 * @param {number} timeout How long to allow, in milliseconds.
 * @returns {Promise<boolean>} True if it held, false if the deadline passed. Every
 *   caller treats false as a result to report rather than one to ignore, which is the
 *   whole difference between this and the fixed delays it replaced.
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
let inert = 0;
const broken = [];

/** @returns {boolean} Whether the page has finished whatever it was doing. */
const quiet = () => inFlight === 0 && !stage.querySelector('.spinner');

/**
 * Which chapter the application believes it is showing.
 *
 * `buildRail()` sets this at the top of `show()`, before the chapter body exists, so it
 * answers "has navigation started" where the spinner answers "has it finished". Waiting
 * on the second alone passes instantly while the previous chapter is still on the stage,
 * which is exactly the bug this replaced.
 *
 * @returns {number} Index into CHAPTERS, or -1 before the rail is built.
 */
const activeChapter = () =>
  [...document.querySelectorAll('#rail-nav .rail__link')].findIndex(
    (link) => link.getAttribute('aria-current') === 'true'
  );

if (!(await waitUntil(() => activeChapter() >= 0 && quiet(), READY_TIMEOUT))) {
  console.log(`the application did not finish loading within ${READY_TIMEOUT} ms`);
  console.log('');
  console.log('FAILED: the application never became ready');
  process.exit(1);
}

for (const [index, chapter] of CHAPTERS.entries()) {
  // Assigning the hash fires hashchange on its own. Dispatching one as well renders the
  // chapter twice concurrently and produces duplicated controls, which looks exactly
  // like a product bug and is not one.
  dom.window.location.hash = chapter.id;

  // Both halves, and in one condition so neither can be satisfied by the other: the rail
  // has to name *this* chapter, and the page has to have stopped working on it.
  if (!(await waitUntil(() => activeChapter() === index && quiet(), READY_TIMEOUT))) {
    unsettled.push(`${chapter.id}: still rendering after ${READY_TIMEOUT} ms`);
    console.log(`${chapter.id.padEnd(14)} DID NOT SETTLE — not inspected, rather than inspected wrongly`);
    continue;
  }

  // Did the chapter render at all? That has to be asked separately, and the reason is
  // worth recording. A chapter that throws renders an error banner and no controls, so
  // "0 controls, all responded" is vacuously true — and this harness reported exactly
  // that while chapter 0 was showing "context.text is not a function" in a browser.
  // Counting dead buttons cannot notice a chapter that has none.
  if (stage.textContent.includes('This chapter failed to render')) {
    const reason = ((stage.querySelector('.verdict__text span') || {}).textContent || '').trim();
    broken.push(`${chapter.id}: ${reason}`);
    console.log(`${chapter.id.padEnd(14)} FAILED TO RENDER — ${reason}`);
    continue;
  }

  // A prose-only chapter has no controls at all, so "0 controls, all responded" is now
  // a legitimate result rather than the vacuous one this harness was written to catch.
  // What can still go wrong on such a chapter is a content key that no markdown file
  // defines, which content.js renders as a marker and reports through console.warn --
  // not console.error, so nothing below would notice it.
  const missing = [...stage.querySelectorAll('.content-missing')].map((node) =>
    (node.textContent || '').trim()
  );
  if (missing.length) {
    contentMissing.push(`${chapter.id}: ${missing.join(' ')}`);
    console.log(`${chapter.id.padEnd(14)} MISSING CONTENT — ${missing.join(' ')}`);
  }

  const total = stage.querySelectorAll('button').length;
  const dead = [];

  for (let index = 0; index < total; index += 1) {
    // Re-query each time: a click can rebuild the panel its button lived in.
    const button = [...stage.querySelectorAll('button')][index];
    if (!button) continue;
    if (button.getAttribute('aria-pressed') === 'true') continue;

    const label = (button.textContent || '').trim().slice(0, 40);
    const before = stage.textContent;
    button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));

    // Returns the moment it changes, so a responsive control costs milliseconds rather
    // than a fixed wait. Only a control that really does nothing spends the deadline,
    // which is the right way round: the slow path is the one that found a bug.
    const responded = await waitUntil(() => stage.textContent !== before, CLICK_TIMEOUT);

    // Then let whatever it started finish, so a slow control is not blamed on the button
    // clicked after it.
    await waitUntil(quiet, CLICK_TIMEOUT);
    if (!responded) dead.push(label);
  }

  inert += dead.length;
  console.log(
    `${chapter.id.padEnd(14)} ${String(total).padStart(2)} controls  ` +
      (dead.length ? `${dead.length} inert: ${dead.join(' | ')}` : 'all responded')
  );
}

if (consoleErrors.length) {
  console.log('');
  console.log('console.error output during interaction:');
  for (const line of consoleErrors.slice(0, 8)) console.log('  ' + line);
}

// Console errors and unrendered chapters count as failure. They were printed and then
// ignored, which is how a broken chapter came out of here as a clean exit: app.js logs
// the error and puts a banner on the page, and neither of those is an inert button.
const failures = [];
if (inert) failures.push(`${inert} inert control(s)`);
if (contentMissing.length) failures.push(`${contentMissing.length} chapter(s) missing content`);
if (broken.length) failures.push(`${broken.length} chapter(s) failed to render`);
if (unsettled.length) failures.push(`${unsettled.length} chapter(s) did not settle`);
if (consoleErrors.length) failures.push(`${consoleErrors.length} console error(s)`);

console.log('');
console.log(failures.length ? `FAILED: ${failures.join(', ')}` : 'EVERY CONTROL RESPONDS');
process.exit(failures.length ? 1 : 0);
