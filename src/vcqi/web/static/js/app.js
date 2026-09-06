// Bootstrap: fetch the world once, build the chapter rail, and render on navigation.
//
// The chapter is kept in the URL fragment so a particular part of the demonstration can
// be linked to directly, which matters when the point of it is to be shown to people.

import { api } from './api.js';
import { CHAPTERS } from './chapters.js';
import { chapterText } from './content.js';
import { clear, el, jsonView, panel } from './ui.js';

const stage = document.getElementById('stage');
const nav = document.getElementById('rail-nav');

let world = null;
let content = null;
let inspector = null;
let inspectorHeading = null;

/** Fetch any published document and show it, exactly as the verifier would. */
async function inspect(url) {
  if (!inspector) return;
  // The inspector puts itself on the page the first time a chapter actually asks for a
  // document. It used to be appended only for a hardcoded list of chapter ids, so a
  // chapter that was not on the list could fetch a document perfectly well and render it
  // into a node that was never in the page: the click worked and nothing happened.
  if (!inspector.isConnected) {
    stage.append(inspectorHeading, inspector);
  }
  clear(inspector).append(el('p', { class: 'spinner', text: `Fetching ${url}…` }));
  try {
    const data = await api.document(url);
    clear(inspector).append(
      el('div', { class: 'panel__head' }, [
        el('h3', { class: 'panel__title', text: url }),
        el('p', { class: 'panel__hint', text: data.kind }),
      ]),
      jsonView(data.document, inspect, { tall: true })
    );
  } catch (error) {
    clear(inspector).append(
      el('div', { class: 'panel__head' }, [el('h3', { class: 'panel__title', text: url })]),
      el('p', { class: 'muted', text: String(error.message) })
    );
  }
  inspector.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// A chapter's title, eyebrow and lede come from its content file once it has one, and
// from the CHAPTERS descriptor until then. The migration runs a chapter at a time, so
// both states are normal and neither is a fallback for a failure.
function heading(t, chapter, field) {
  return t.has(field) ? t.text(field) : chapter[field];
}

function buildRail(activeId) {
  clear(nav);
  CHAPTERS.forEach((chapter, index) => {
    nav.append(
      el(
        'li',
        {},
        el('button', {
          class: 'rail__link',
          'aria-current': String(chapter.id === activeId),
          onclick: () => {
            window.location.hash = chapter.id;
          },
        }, [
          el('span', { class: 'rail__num', text: String(index) }),
          el('span', { text: heading(chapterText(content, chapter.id), chapter, 'title') }),
        ])
      )
    );
  });
}

async function show(id) {
  const chapter = CHAPTERS.find((item) => item.id === id) || CHAPTERS[0];
  const t = chapterText(content, chapter.id);
  buildRail(chapter.id);

  clear(stage).append(
    el('header', {}, [
      el('p', { class: 'chapter__eyebrow', text: heading(t, chapter, 'eyebrow') }),
      el('h1', { class: 'chapter__title', text: heading(t, chapter, 'title') }),
      el('p', { class: 'chapter__lede', text: heading(t, chapter, 'lede') }),
    ]),
    el('p', { class: 'spinner', text: 'Loading…' })
  );

  inspector = panel(null, null, el('p', { class: 'muted', text: 'Click any address in a document above to fetch it, the way the verifier does.' }));
  inspectorHeading = el('h3', { text: 'Follow a reference' });

  try {
    const body = await chapter.render({
      world,
      api,
      inspect,
      text: (chapterId) => chapterText(content, chapterId),
    });
    stage.lastChild.remove();
    stage.append(body);
  } catch (error) {
    stage.lastChild.remove();
    stage.append(
      el('div', { class: 'verdict verdict--fail' }, [
        el('div', { class: 'verdict__mark', text: '!' }),
        el('div', { class: 'verdict__text' }, [
          el('strong', { text: 'This chapter failed to render' }),
          el('span', { text: String(error.message) }),
        ]),
      ])
    );
    // Surface it properly too, so the browser console has the stack.
    console.error(error);
  }

  window.scrollTo({ top: 0 });
}

async function start() {
  try {
    // In parallel: the content is a separate document from the world and neither waits
    // on the other.
    [world, content] = await Promise.all([api.world(), api.content()]);
  } catch (error) {
    clear(stage).append(
      el('div', { class: 'verdict verdict--fail' }, [
        el('div', { class: 'verdict__mark', text: '!' }),
        el('div', { class: 'verdict__text' }, [
          el('strong', { text: 'Could not reach the demonstration server' }),
          el('span', { text: String(error.message) }),
        ]),
      ])
    );
    return;
  }

  window.addEventListener('hashchange', () => show(window.location.hash.slice(1)));
  await show(window.location.hash.slice(1));
}

start();
