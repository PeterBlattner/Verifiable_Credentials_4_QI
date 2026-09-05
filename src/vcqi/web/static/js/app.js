// Bootstrap: fetch the world once, build the chapter rail, and render on navigation.
//
// The chapter is kept in the URL fragment so a particular part of the demonstration can
// be linked to directly, which matters when the point of it is to be shown to people.

import { api } from './api.js';
import { CHAPTERS } from './chapters.js';
import { clear, el, jsonView, panel } from './ui.js';

const stage = document.getElementById('stage');
const nav = document.getElementById('rail-nav');

let world = null;
let inspector = null;

/** Fetch any published document and show it, exactly as the verifier would. */
async function inspect(url) {
  if (!inspector) return;
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
          el('span', { text: chapter.title }),
        ])
      )
    );
  });
}

async function show(id) {
  const chapter = CHAPTERS.find((item) => item.id === id) || CHAPTERS[0];
  buildRail(chapter.id);

  clear(stage).append(
    el('header', {}, [
      el('p', { class: 'chapter__eyebrow', text: chapter.eyebrow }),
      el('h1', { class: 'chapter__title', text: chapter.title }),
      el('p', { class: 'chapter__lede', text: chapter.lede }),
    ]),
    el('p', { class: 'spinner', text: 'Loading…' })
  );

  inspector = panel(null, null, el('p', { class: 'muted', text: 'Click any address in a document above to fetch it, the way the verifier does.' }));

  try {
    const body = await chapter.render({ world, api, inspect });
    stage.lastChild.remove();
    stage.append(body);
    if (['graph', 'issuing', 'verification', 'scope'].includes(chapter.id)) {
      stage.append(el('h3', { text: 'Follow a reference' }), inspector);
    }
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
    world = await api.world();
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
