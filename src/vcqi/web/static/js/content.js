// Reading the chapter prose that lives in content/chapters/*.md.
//
// A render function asks for its text by name:
//
//   const t = context.text('orientation');
//   fragment.append(t.prose('what-it-is'));
//   fragment.append(panel(t.text('mapping.title'), t.text('mapping.hint'), t.block('mapping.rows')));
//
// Two accessors rather than one, because ui.js needs both forms. `prose`, `callout` and
// `block` hand HTML to innerHTML; `text` returns a plain string, which is what `panel`
// wants because it sets its title with textContent. Serving both from the server means
// neither is derived in the browser.
//
// No accessor here raises, and none returns empty. A key that no content file defines
// renders a marked-up complaint in the exact position the prose belonged, so a typo
// costs one paragraph and is impossible to miss, while the chapter's panels, structure
// and controls all still work. app.js still catches genuine render errors; content
// misses no longer reach it.

import { el } from './ui.js';

/** What a missing block renders as. Loud on purpose: silence would be worse. */
function missing(chapterId, key) {
  console.warn(`content: no block '${key}' in chapter '${chapterId}'`);
  return `<mark class="content-missing">[missing content: ${chapterId}/${key}]</mark>`;
}

/** Escape a value interpolated into a block, so a computed number cannot inject markup. */
function escapeValue(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Bind an accessor to one chapter's blocks.
 *
 * @param {object} payload  what GET /api/content returned
 * @param {string} chapterId  the chapter, as it appears in CHAPTERS
 */
export function chapterText(payload, chapterId) {
  const blocks = (payload && payload.chapters && payload.chapters[chapterId]) || {};

  const html = (key) => (blocks[key] ? blocks[key].html : missing(chapterId, key));

  // The plain form comes from the server too, rather than being scraped out of the HTML
  // here. A block used as a panel title should contain no markup at all, and a test
  // asserts that; this just reports whatever it was given.
  const text = (key) =>
    blocks[key] ? blocks[key].text : `[missing content: ${chapterId}/${key}]`;

  /** Substitute {name} placeholders, escaping the values. */
  const fill = (key, values) =>
    html(key).replace(/\{([a-z][a-z0-9_]*)\}/gi, (whole, name) =>
      Object.prototype.hasOwnProperty.call(values || {}, name)
        ? escapeValue(values[name])
        : whole
    );

  return {
    html,
    text,
    fill,
    kind: (key) => (blocks[key] ? blocks[key].kind : 'missing'),
    has: (key) => Object.prototype.hasOwnProperty.call(blocks, key),
    keys: () => Object.keys(blocks),

    /** A block of prose, styled as the chapters' body text. */
    prose: (key) => el('div', { class: 'prose', html: html(key) }),

    /** A block set aside from the flow, for an aside or a caveat. */
    callout: (key) => el('div', { class: 'callout', html: html(key) }),

    /** A table or a list, for dropping inside a panel. */
    block: (key) => el('div', { class: 'content-block', html: html(key) }),

    /** Prose with {name} placeholders filled in from computed values. */
    proseFill: (key, values) => el('div', { class: 'prose', html: fill(key, values) }),
  };
}
