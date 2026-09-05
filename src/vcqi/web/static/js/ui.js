// Shared rendering helpers.
//
// The two that carry most of the weight are the JSON viewer, which makes every
// reference inside a credential clickable so a reader can follow a chain by hand, and
// the step tree, which renders a verification report as the nested sequence of
// decisions it actually is.

export function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === 'class') node.className = value;
    else if (name === 'text') node.textContent = value;
    else if (name === 'html') node.innerHTML = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? '' : String(value));
  }
  for (const child of [].concat(children || [])) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

/** Format a number the way a metrologist reads one, without losing information. */
export function num(value, digits) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  const magnitude = Math.abs(value);
  if (magnitude !== 0 && (magnitude < 1e-4 || magnitude >= 1e6)) {
    return value.toExponential(digits === undefined ? 4 : digits);
  }
  const text = value.toPrecision(digits === undefined ? 8 : digits);
  // Only trim zeros that sit after a decimal point. Trimming them from an integer such
  // as 100000 would turn it into 1.
  return text.includes('.') ? text.replace(/\.?0+$/, '') : text;
}

export function percent(fraction) {
  return `${(fraction * 100).toFixed(fraction < 0.001 ? 3 : 1)} %`;
}

export function badge(status, label) {
  const known = ['pass', 'fail', 'warn', 'skip', 'anchor', 'neutral'];
  const kind = known.includes(status) ? status : 'neutral';
  const text = label || { pass: 'pass', fail: 'fail', warn: 'note', skip: 'not run' }[status] || status;
  return el('span', { class: `badge badge--${kind}`, text });
}

export function panel(title, hint, children) {
  return el('section', { class: 'panel' }, [
    title
      ? el('div', { class: 'panel__head' }, [
          el('h3', { class: 'panel__title', text: title }),
          hint ? el('p', { class: 'panel__hint', text: hint }) : null,
        ])
      : null,
    ...[].concat(children || []),
  ]);
}

export function callout(paragraphs) {
  return el(
    'div',
    { class: 'callout' },
    [].concat(paragraphs).map((text) => el('p', { html: text }))
  );
}

export function prose(paragraphs) {
  return el(
    'div',
    { class: 'prose' },
    [].concat(paragraphs).map((text) => el('p', { html: text }))
  );
}

/** A definition list, used wherever the interface shows a handful of named values. */
export function keyValues(pairs) {
  const list = el('dl', { class: 'kv' });
  for (const [term, value] of pairs) {
    if (value === null || value === undefined) continue;
    list.append(el('dt', { text: term }));
    list.append(value.nodeType ? el('dd', {}, value) : el('dd', { text: String(value) }));
  }
  return list;
}

export function table(headers, rows) {
  return el('table', { class: 'data' }, [
    el('thead', {}, el('tr', {}, headers.map((h) => el('th', { text: h })))),
    el(
      'tbody',
      {},
      rows.map((row) =>
        el(
          'tr',
          {},
          row.map((cell) =>
            cell && cell.numeric
              ? el('td', { class: 'num' }, cell.node || String(cell.value))
              : el('td', {}, cell && cell.nodeType ? cell : String(cell === null || cell === undefined ? '' : cell))
          )
        )
      )
    ),
  ]);
}

const LINKABLE = /^(https:\/\/|did:web:)/;

/**
 * Render JSON with syntax colouring, turning every address into a link.
 *
 * Making the references clickable is the point. A credential that says it was issued
 * under CMC CH-EM-0042 is only as good as the reader's ability to go and look at
 * CH-EM-0042, and the same is true for the verifier.
 */
export function jsonView(value, onFollow, options) {
  const pre = el('pre', { class: `json${options && options.tall ? ' json--tall' : ''}` });
  render(value, 0, pre, onFollow);
  return pre;
}

function span(cls, text) {
  return el('span', { class: cls, text });
}

function render(value, depth, out, onFollow) {
  const pad = '  '.repeat(depth);
  const padInner = '  '.repeat(depth + 1);

  if (value === null) return out.append(span('tok-lit', 'null'));
  if (typeof value === 'boolean') return out.append(span('tok-lit', String(value)));
  if (typeof value === 'number') return out.append(span('tok-num', formatJsonNumber(value)));
  if (typeof value === 'string') {
    if (LINKABLE.test(value) && onFollow) {
      const link = span('tok-str tok-link', JSON.stringify(value));
      link.addEventListener('click', () => onFollow(value));
      link.title = `Fetch ${value}`;
      return out.append(link);
    }
    return out.append(span('tok-str', JSON.stringify(value)));
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return out.append(document.createTextNode('[]'));
    out.append(document.createTextNode('[\n'));
    value.forEach((item, index) => {
      out.append(document.createTextNode(padInner));
      render(item, depth + 1, out, onFollow);
      out.append(document.createTextNode(index < value.length - 1 ? ',\n' : '\n'));
    });
    return out.append(document.createTextNode(`${pad}]`));
  }

  const entries = Object.entries(value);
  if (entries.length === 0) return out.append(document.createTextNode('{}'));
  out.append(document.createTextNode('{\n'));
  entries.forEach(([name, item], index) => {
    out.append(document.createTextNode(padInner));
    out.append(span('tok-key', JSON.stringify(name)));
    out.append(document.createTextNode(': '));
    render(item, depth + 1, out, onFollow);
    out.append(document.createTextNode(index < entries.length - 1 ? ',\n' : '\n'));
  });
  return out.append(document.createTextNode(`${pad}}`));
}

function formatJsonNumber(value) {
  // String() in JavaScript is ECMAScript Number::toString, which is exactly the number
  // representation RFC 8785 mandates. So what the reader sees here is character for
  // character what went into the hash.
  return String(value);
}

/** Render a verification report as an expandable tree of decisions. */
export function stepTree(steps, depth) {
  const list = el('ul', { class: 'steps' });
  for (const step of steps) {
    const children = step.children && step.children.length
      ? stepTree(step.children, (depth || 0) + 1)
      : null;

    const head = el('div', { class: 'step__head' }, [
      el('div', {}, [badge(step.status), el('div', { class: 'step__id', text: step.id })]),
      el('div', {}, [
        el('p', { class: 'step__title', text: step.title }),
        el('p', { class: 'step__detail', text: step.detail }),
      ]),
    ]);

    const item = el('li', { class: 'step' }, [head]);
    if (children) {
      const wrap = el('div', { class: 'step__children' }, children);
      // Passing branches start collapsed so that a failure is the thing you see.
      const collapsed = step.status === 'pass' && (depth || 0) === 0;
      wrap.hidden = collapsed;
      head.addEventListener('click', () => {
        wrap.hidden = !wrap.hidden;
      });
      head.title = 'Show or hide the checks inside this step';
      item.append(wrap);
    }
    list.append(item);
  }
  return list;
}

export function verdictBanner(report) {
  const verified = report.outcome === 'verified';
  const failures = report.failureSummary || [];
  return el('div', { class: `verdict verdict--${verified ? 'pass' : 'fail'}` }, [
    el('div', { class: 'verdict__mark', text: verified ? '✓' : '✗' }),
    el('div', { class: 'verdict__text' }, [
      el('strong', {
        text: verified
          ? 'Accepted: every check passed'
          : `Rejected: ${failures.length} check${failures.length === 1 ? '' : 's'} failed`,
      }),
      el('span', {
        text: verified
          ? `${report.credentialType} from ${report.issuer}, verified as at ${report.verifiedAt}`
          : failures.map((failure) => failure.detail).join(' · '),
      }),
    ]),
  ]);
}

export function retrievalSummary(fetches) {
  const presented = fetches.filter((f) => f.source === 'presented').length;
  const missing = fetches.filter((f) => !f.found).length;
  return el('div', { class: 'stat-row' }, [
    stat(fetches.length, 'documents retrieved'),
    presented ? stat(presented, 'supplied by the holder') : null,
    missing ? stat(missing, 'not found') : null,
  ]);
}

export function stat(value, label) {
  return el('div', {}, [
    el('div', { class: 'stat__value', text: String(value) }),
    el('div', { class: 'stat__label', text: label }),
  ]);
}

export function sliderRow(config) {
  const output = el('span', { class: 'slider-row__value', text: config.format(config.value) });
  const input = el('input', {
    type: 'range',
    min: config.min,
    max: config.max,
    step: config.step,
    value: config.value,
    oninput: (event) => {
      const raw = Number(event.target.value);
      output.textContent = config.format(raw);
      config.onInput(raw);
    },
  });
  return el('div', { class: 'slider-row' }, [
    el('span', { class: 'slider-row__label', text: config.label }),
    input,
    output,
  ]);
}
