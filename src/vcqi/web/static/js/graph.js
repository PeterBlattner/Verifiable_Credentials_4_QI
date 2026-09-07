// The quality infrastructure drawn as a graph.
//
// Two kinds of edge run through it and they mean opposite things, which is why they are
// drawn differently and why the legend insists on the distinction.
//
// A recognition edge runs downward and says "this body vouches that that one may do
// something". A verifier follows these upward, from a document it has been handed
// towards an anchor it already trusts.
//
// An issuance edge runs sideways and downward and says "this organisation gave that one
// a document". Traceability runs back along these, from a test result down to a national
// standard.
//
// Positions are fixed rather than computed. The hierarchy is the message, and a force
// layout would rearrange it every time the page loads.

import { el } from './ui.js';

const SVG_NS = 'http://www.w3.org/2000/svg';

const BOX = { width: 170, height: 48 };

// Five rows, three columns of anchor. Reading down a column follows one arrangement;
// reading across a row is a level of the hierarchy. The legal-metrology column is on the
// right because its two long edges -- OIML recognising a laboratory that SAS also
// accredits, and that laboratory's report travelling to the Issuing Authority -- have to
// cross the diagram, and they read better crossing into the middle than out of it.
//
// A node with no entry here is skipped and every edge touching it dropped, both without
// a word. `test_every_node_has_a_position_in_the_diagram` exists so that cannot happen
// quietly.
const POSITIONS = {
  'did:web:bipm.example': { x: 40, y: 24 },
  'did:web:global-aci.example': { x: 400, y: 24 },
  'did:web:oiml.example': { x: 820, y: 24 },
  'did:web:metas.example': { x: 20, y: 146 },
  'did:web:ptb.example': { x: 200, y: 146 },
  'did:web:sas.example': { x: 400, y: 146 },
  'did:web:callab.example': { x: 110, y: 268 },
  'did:web:testlab.example': { x: 370, y: 268 },
  'did:web:cab.example': { x: 630, y: 268 },
  'did:web:manufacturer.example': { x: 500, y: 390 },
  'did:web:legal-ia.example': { x: 820, y: 390 },
  'did:web:meterworks.example': { x: 820, y: 512 },
  'did:web:surveillance.example': { x: 1010, y: 512 },
};

function svg(tag, attrs, children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, String(value));
  }
  for (const child of [].concat(children || [])) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function centre(did) {
  const position = POSITIONS[did] || { x: 0, y: 0 };
  return { x: position.x + BOX.width / 2, y: position.y + BOX.height / 2 };
}

/** Meet each box on the side that faces the other end, so lines stop at the edge. */
function anchorPoint(from, to) {
  const start = centre(from);
  const end = centre(to);
  const halfWidth = BOX.width / 2;
  const halfHeight = BOX.height / 2;

  const dx = end.x - start.x;
  const dy = end.y - start.y;

  if (Math.abs(dy) * halfWidth > Math.abs(dx) * halfHeight) {
    return { x: start.x + (dx * halfHeight) / Math.abs(dy || 1), y: start.y + Math.sign(dy) * halfHeight };
  }
  return { x: start.x + Math.sign(dx) * halfWidth, y: start.y + (dy * halfWidth) / Math.abs(dx || 1) };
}

function edgePath(edge) {
  const start = anchorPoint(edge.source, edge.target);
  const end = anchorPoint(edge.target, edge.source);
  const midY = (start.y + end.y) / 2;
  // A vertical-first curve keeps the hierarchy legible where several edges leave the
  // same body for children spread across the row below.
  return `M ${start.x} ${start.y} C ${start.x} ${midY}, ${end.x} ${midY}, ${end.x} ${end.y}`;
}

function marker(id, cssClass) {
  return svg(
    'marker',
    { id, viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' },
    svg('path', { d: 'M 0 0 L 8 4 L 0 8 z', class: cssClass })
  );
}

/**
 * Draw the graph.
 *
 * @param {object} graph Nodes and edges from the world endpoint.
 * @param {object} options Callbacks and the current selection.
 * @returns {HTMLElement} The graph with its legend.
 */
export function renderGraph(graph, options) {
  const settings = options || {};
  const highlight = new Set(settings.highlightEdges || []);
  const selected = settings.selectedNode;

  const edges = graph.edges.filter((edge) => POSITIONS[edge.source] && POSITIONS[edge.target]);

  // `branch` narrows the diagram to one arrangement. Everything outside it is dimmed
  // rather than removed: the point of drawing three arrangements together is that a
  // document can rest on two of them at once, and hiding the others would hide exactly
  // that. A node keeps full strength if any of its branches is the selected one, which
  // is how the laboratory recognised twice stays lit in either view.
  const branch = settings.branch || null;
  const inBranch = (branches) =>
    !branch || (Array.isArray(branches) ? branches.includes(branch) : branches === branch);

  const defs = svg('defs', {}, [
    marker('arrow-recognition', 'edge--recognition'),
    marker('arrow-issuance', 'edge--issuance'),
    marker('arrow-presentation', 'edge--presentation'),
    marker('arrow-active', 'edge--active'),
  ]);
  // Markers inherit no stroke, so give each arrowhead its own fill.
  defs.querySelectorAll('path').forEach((path) => {
    const kind = path.getAttribute('class').replace('edge--', '');
    const fill = {
      recognition: 'var(--anchor)',
      issuance: 'var(--ink-faint)',
      presentation: 'var(--accent)',
      active: 'var(--accent)',
    }[kind];
    path.setAttribute('fill', fill);
    path.removeAttribute('class');
  });

  const edgeLayer = svg('g', { class: 'edges' });
  for (const edge of edges) {
    const active = highlight.has(edge.credential);
    const kind = active ? 'active' : edge.kind;
    const dimmed = !inBranch(edge.branch);
    const path = svg('path', {
      d: edgePath(edge),
      class: `edge edge--${edge.kind}${active ? ' edge--active' : ''}${dimmed ? ' edge--dimmed' : ''}`,
      'marker-end': `url(#arrow-${kind})`,
      style: 'cursor: pointer',
      onclick: () => settings.onSelectEdge && settings.onSelectEdge(edge),
    });
    path.append(svg('title', {}, `${edge.label} — ${edge.credentialId}`));
    edgeLayer.append(path);
  }

  const nodeLayer = svg('g', { class: 'nodes' });
  for (const node of graph.nodes) {
    const position = POSITIONS[node.id];
    if (!position) continue;
    const classes = ['node'];
    if (node.isTrustAnchor) classes.push('node--anchor');
    if (node.id === selected) classes.push('node--selected');
    if (!inBranch(node.branches)) classes.push('node--dimmed');

    const group = svg(
      'g',
      {
        class: classes.join(' '),
        style: 'cursor: pointer',
        onclick: () => settings.onSelectNode && settings.onSelectNode(node.id),
      },
      [
        svg('rect', { class: 'node__box', x: position.x, y: position.y, width: BOX.width, height: BOX.height, rx: 6 }),
        svg('text', { class: 'node__name', x: position.x + 12, y: position.y + 21 }, node.name),
        svg('text', { class: 'node__role', x: position.x + 12, y: position.y + 36 }, node.role),
      ]
    );
    group.append(svg('title', {}, `${node.legalName}\n${node.id}`));
    nodeLayer.append(group);
  }

  const canvas = svg(
    'svg',
    { class: 'graph', viewBox: '0 0 1200 580', role: 'img', 'aria-label': 'Trust graph of the demonstration' },
    [defs, edgeLayer, nodeLayer]
  );

  return el('div', { class: 'graph-wrap' }, [
    canvas,
    el('div', { class: 'legend' }, [
      legendKey('var(--anchor)', 'solid', 'recognition: who vouches for whom'),
      legendKey('var(--ink-faint)', 'dashed', 'issuance: who gave whom a document'),
      legendKey('var(--accent)', 'dotted', 'presentation at the border'),
      el('span', { class: 'legend__key' }, [
        el('span', {
          class: 'legend__swatch',
          style: 'border-top-color: var(--anchor); border-top-width: 3px;',
        }),
        'boxes outlined in blue are the trust anchors, one per arrangement',
      ]),
    ]),
  ]);
}

function legendKey(colour, style, label) {
  return el('span', { class: 'legend__key' }, [
    el('span', { class: 'legend__swatch', style: `border-top-color: ${colour}; border-top-style: ${style};` }),
    label,
  ]);
}

export const graphPositions = POSITIONS;
