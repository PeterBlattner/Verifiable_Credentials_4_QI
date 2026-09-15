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
// It needs jsdom, which is deliberately not a dependency of the application: nothing that
// ships needs npm, and that should stay true. The manifest beside this file is committed
// so that ci.yml installs the same version you do -- it reaches no wheel, no image and no
// page:
//
//   cd tools && npm ci && cd ..
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
// A fourth was added for the same reason, and it is the subtlest of them: this harness
// used to wait a fixed 1400 ms after changing the hash and then read the page, which a
// cold server outruns. It now waits for the page to settle, and reports reaching the
// deadline instead of reading the page anyway. page-settled.mjs holds that logic and the
// reasoning behind it, because chapter-snapshot.mjs needs exactly the same thing.
//
// A fifth was added after this harness watched a control disappear and said nothing. A
// panel in chapter 11 offers one chip per register so a reader can fetch both documents
// and compare the same free string in each; the accreditation scope stopped publishing
// that string at the top level, the selector went on looking there, and the second chip
// was never created. "2 controls, all responded" became "1 control, all responded", which
// is true and is not the point. Every guard above asks whether what is on the page works.
// None of them asks whether it is all still there.
//
// So MINIMUM_CONTROLS records what each chapter had when it was last known good, and a
// chapter that renders fewer than that fails. It only fires on a decrease, which is the
// failure mode: adding a control is normal and raising the floor afterwards is a one-line
// edit with the reason in the diff. Chapters with none record zero and are exempt.
//
// VCQI_SETTLE is gone with the delays it configured; VCQI_READY_TIMEOUT and
// VCQI_CLICK_TIMEOUT are deadlines.

//: What counts as a control. Buttons, and the transparent hit paths that make the graph's
//: edges clickable -- which are not buttons, are the primary interaction of chapter 2, and
//: went unexercised by this harness for its whole existence. `onSelectEdge` could have
//: been broken in any release and nothing here would have said a word.
//:
//: Be clear about what including them proves. This dispatches a click on the element
//: directly, so it exercises the wiring: that an edge exists, carries a handler, and that
//: the handler changes the page. It says nothing about whether a pointer could ever have
//: landed there, because `dispatchEvent` does not hit-test and jsdom does not lay the
//: diagram out. The width of the target, the dash gaps and the cursor are all things only
//: a real browser can answer, which is how they stayed wrong for so long.
const CONTROLS = 'button, .edge-hit';

// Resolved at run time so the module can come from beside this file or from wherever
// the operator already has it.
const { JSDOM } = await import(process.env.VCQI_JSDOM || 'jsdom');
const { servedModules } = await import(new URL('served-modules.mjs', import.meta.url));
const { instrumentFetch, pageState, READY_TIMEOUT, CLICK_TIMEOUT } = await import(
  new URL('page-settled.mjs', import.meta.url)
);

const BASE = process.env.VCQI_BASE || 'http://127.0.0.1:8000';

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

// Before app.js is imported, because that is what installs the code that fetches.
const pending = instrumentFetch(BASE);

const consoleErrors = [];
console.error = (...args) => consoleErrors.push(args.map(String).join(' '));

const contentMissing = [];
const unsettled = [];
const shrunk = [];

//: The number of controls each chapter had when it was last known good. A floor, not an
//: expectation: chapters grow, and only a decrease means something went missing. Raise a
//: number here in the same commit that adds the control, so the diff says why.
const MINIMUM_CONTROLS = {
  cautions: 0,
  orientation: 0,
  keys: 8,
  graph: 20,
  issuing: 17,
  verification: 2,
  scope: 0,
  traceability: 9,
  tamper: 9,
  break: 23,
  implications: 0,
  infrastructure: 16,
  harmonisation: 2,
  exchange: 5,
};

// The bytes the server sends, not the ones on disk: see served-modules.mjs for
// the failure that distinction let through.
const modules = await servedModules(BASE);
const { CHAPTERS } = await import(new URL('chapters.js', modules));
await import(new URL('app.js', modules));

const stage = document.getElementById('stage');
const page = pageState({ document, stage, pending });
let inert = 0;
const broken = [];

if (!(await page.ready())) {
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

  if (!(await page.showing(index))) {
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

  const total = stage.querySelectorAll(CONTROLS).length;
  const floor = MINIMUM_CONTROLS[chapter.id];
  if (floor !== undefined && total < floor) {
    shrunk.push(`${chapter.id}: ${total} controls, expected at least ${floor}`);
    console.log(`${chapter.id.padEnd(14)} LOST CONTROLS — ${total} of at least ${floor}`);
  }

  const dead = [];

  for (let index = 0; index < total; index += 1) {
    // Re-query each time: a click can rebuild the panel its button lived in.
    const button = [...stage.querySelectorAll(CONTROLS)][index];
    if (!button) continue;
    if (button.getAttribute('aria-pressed') === 'true') continue;

    // An edge carries no text of its own; its <title> is the sibling that names it.
    const title = button.parentNode && button.parentNode.querySelector('title');
    const label = ((button.textContent || title?.textContent || '').trim() || 'edge').slice(0, 40);
    const before = stage.textContent;
    button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));

    // Returns the moment it changes, so a responsive control costs milliseconds rather
    // than a fixed wait. Only a control that really does nothing spends the deadline,
    // which is the right way round: the slow path is the one that found a bug.
    const responded = await page.changedFrom(before);

    // Then let whatever it started finish, so a slow control is not blamed on the button
    // clicked after it.
    await page.idle(CLICK_TIMEOUT);
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
if (shrunk.length) failures.push(`${shrunk.length} chapter(s) lost controls`);
if (unsettled.length) failures.push(`${unsettled.length} chapter(s) did not settle`);
if (consoleErrors.length) failures.push(`${consoleErrors.length} console error(s)`);

console.log('');
console.log(failures.length ? `FAILED: ${failures.join(', ')}` : 'EVERY CONTROL RESPONDS');
process.exit(failures.length ? 1 : 0);
