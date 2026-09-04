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

const POSITIONS = {
  // International layer. Three of these four are trust anchors and the fourth, OIML, is
  // deliberately not: it confers technical recognition and no legal force at all.
  'did:web:bipm.example': { x: 40, y: 20 },
  'did:web:global-aci.example': { x: 400, y: 20 },
  'did:web:oiml.example': { x: 760, y: 20 },
  'did:web:legislator.example': { x: 1040, y: 20 },

  // National layer. METAS appears once and holds two roles, which is why two edges of
  // different kinds arrive at it from opposite ends of the row above.
  'did:web:metas.example': { x: 30, y: 148 },
  'did:web:ptb.example': { x: 240, y: 148 },
  'did:web:sas.example': { x: 470, y: 148 },

  // Bodies that assess, calibrate or verify.
  'did:web:callab.example': { x: 30, y: 276 },
  'did:web:testlab.example': { x: 250, y: 276 },
  'did:web:cab.example': { x: 470, y: 276 },
  'did:web:verifybody.example': { x: 800, y: 276 },

  // Whoever holds the documents, and whoever has to believe them.
  'did:web:manufacturer.example': { x: 250, y: 404 },
  'did:web:retailer.example': { x: 660, y: 404 },
  'did:web:surveillance.example': { x: 960, y: 404 },
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

  // A branch filter hides nodes as well as edges, so that isolating one pillar leaves
  // the organisations of the others out rather than stranded and unconnected.
  const branches = settings.branches || null;
  const visible = (branch) => !branches || branches.has(branch);

  const nodes = graph.nodes.filter((node) => visible(node.branch));
  const shown = new Set(nodes.map((node) => node.id));
  const edges = graph.edges.filter(
    (edge) =>
      POSITIONS[edge.source] &&
      POSITIONS[edge.target] &&
      shown.has(edge.source) &&
      shown.has(edge.target)
  );

  const defs = svg('defs', {}, [
    marker('arrow-recognition', 'edge--recognition'),
    marker('arrow-issuance', 'edge--issuance'),
    marker('arrow-presentation', 'edge--presentation'),
    marker('arrow-authority', 'edge--authority'),
    marker('arrow-active', 'edge--active'),
  ]);
  // Markers inherit no stroke, so give each arrowhead its own fill.
  defs.querySelectorAll('path').forEach((path) => {
    const kind = path.getAttribute('class').replace('edge--', '');
    const fill = {
      recognition: 'var(--anchor)',
      issuance: 'var(--ink-faint)',
      presentation: 'var(--accent)',
      authority: 'var(--legal)',
      active: 'var(--accent)',
    }[kind];
    path.setAttribute('fill', fill);
    path.removeAttribute('class');
  });

  const edgeLayer = svg('g', { class: 'edges' });
  for (const edge of edges) {
    const active = highlight.has(edge.credential);
    const kind = active ? 'active' : edge.kind;
    const path = svg('path', {
      d: edgePath(edge),
      class: `edge edge--${edge.kind}${active ? ' edge--active' : ''}`,
      'marker-end': `url(#arrow-${kind})`,
      style: 'cursor: pointer',
      onclick: () => settings.onSelectEdge && settings.onSelectEdge(edge),
    });
    path.append(svg('title', {}, `${edge.label} — ${edge.credentialId}`));
    edgeLayer.append(path);
  }

  const nodeLayer = svg('g', { class: 'nodes' });
  for (const node of nodes) {
    const position = POSITIONS[node.id];
    if (!position) continue;
    const classes = ['node'];
    if (node.isTrustAnchor) classes.push('node--anchor');
    if (node.id === selected) classes.push('node--selected');

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
    { class: 'graph', viewBox: '0 0 1240 490', role: 'img', 'aria-label': 'Trust graph of the demonstration' },
    [defs, edgeLayer, nodeLayer]
  );

  return el('div', { class: 'graph-wrap' }, [
    canvas,
    el('div', { class: 'legend' }, [
      legendKey('var(--anchor)', 'solid', 'recognition: who vouches for whom'),
      legendKey('var(--legal)', 'solid', 'legal authority: where legal force comes from'),
      legendKey('var(--ink-faint)', 'dashed', 'issuance: who gave whom a document'),
      legendKey('var(--accent)', 'dotted', 'presentation'),
      el('span', { class: 'legend__key' }, [
        el('span', {
          class: 'legend__swatch',
          style: 'border-top-color: var(--anchor); border-top-width: 3px;',
        }),
        'outlined boxes are trust anchors. OIML is not one: it confers technical recognition, never legal force',
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
