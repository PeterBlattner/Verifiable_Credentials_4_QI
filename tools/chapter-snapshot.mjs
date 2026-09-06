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

const { JSDOM } = await import(process.env.VCQI_JSDOM || 'jsdom');
const { servedModules } = await import(new URL('served-modules.mjs', import.meta.url));

const BASE = process.env.VCQI_BASE || 'http://127.0.0.1:8000';
const SETTLE = Number(process.env.VCQI_SETTLE || 1200);

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

const realFetch = global.fetch;
global.fetch = (input, init) =>
  realFetch(String(input).startsWith('http') ? input : BASE + input, init);

// Keep render failures visible: a chapter that throws renders an error banner, which
// would otherwise show up in the diff as a puzzling few lines rather than as a problem.
const consoleErrors = [];
console.error = (...args) => consoleErrors.push(args.map(String).join(' '));

const settle = (ms = SETTLE) => new Promise((resolve) => setTimeout(resolve, ms));

// The bytes the server sends, not the ones on disk: see served-modules.mjs for
// the failure that distinction let through.
const modules = await servedModules(BASE);
const { CHAPTERS } = await import(new URL('chapters.js', modules));
await import(new URL('app.js', modules));
await settle(1600);

const stage = document.getElementById('stage');

// Whitespace is not content here. Indentation in a markdown file becomes different
// whitespace between tags than a JavaScript template literal did, and that difference
// carries no meaning for a reader.
const normalise = (value) => value.replace(/\s+/g, ' ').trim();

for (const chapter of CHAPTERS) {
  if (wanted.size && !wanted.has(chapter.id)) continue;

  dom.window.location.hash = chapter.id;
  await settle(1500);

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
  process.exit(1);
}
