// The chapters of the demonstration.
//
// Each one answers a question in order: what is a credential, who is in this world, how
// is a certificate signed, what does a recipient check, what does the CMC decide, where
// does the uncertainty come from, what breaks it, and what would any of this change.

import { api } from './api.js';
import { renderGraph } from './graph.js';
import {
  badge,
  callout,
  clear,
  el,
  jsonView,
  keyValues,
  num,
  panel,
  percent,
  prose,
  retrievalSummary,
  sliderRow,
  stat,
  stepTree,
  table,
  verdictBanner,
} from './ui.js';

const CREDENTIAL_LABELS = {
  'bipm-recognition': 'BIPM recognition of national metrology institutes',
  'ilac-recognition': 'ILAC recognition of accreditation bodies',
  'sas-recognition': 'Accreditation body recognition of laboratories',
  'metas-calibration': 'Calibration certificate METAS-2026-0417',
  'callab-calibration': 'Calibration certificate AC-2026-1182',
  'testlab-report': 'Test report HTS-2026-3391',
  'cab-conformity': 'Certificate of conformity CPC-2026-0055',
};

const MAIN_CREDENTIALS = Object.keys(CREDENTIAL_LABELS);

// ---------------------------------------------------------------- chapter 0

function triangle() {
  const ns = 'http://www.w3.org/2000/svg';
  const make = (tag, attrs, children) => {
    const node = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, String(v));
    for (const c of [].concat(children || [])) node.append(c.nodeType ? c : document.createTextNode(String(c)));
    return node;
  };
  const box = (x, y, role, sub) =>
    make('g', {}, [
      make('rect', { class: 't-node', x, y, width: 150, height: 44, rx: 6 }),
      make('text', { class: 't-role', x: x + 12, y: y + 20 }, role),
      make('text', { class: 't-sub', x: x + 12, y: y + 34 }, sub),
    ]);

  return make('svg', { class: 'triangle', viewBox: '0 0 560 210', role: 'img', 'aria-label': 'Issuer, holder and verifier' }, [
    box(10, 20, 'Issuer', 'the institute or laboratory'),
    box(400, 20, 'Verifier', 'whoever has to believe it'),
    box(205, 145, 'Holder', 'the customer, who keeps it'),
    make('path', { class: 't-line', d: 'M 160 42 L 400 42' }),
    make('path', { class: 't-line', d: 'M 85 64 L 250 145' }),
    make('path', { class: 't-line', d: 'M 355 145 L 470 64' }),
    make('text', { class: 't-arrow', x: 208, y: 36 }, 'publishes its key, once'),
    make('text', { class: 't-arrow', x: 60, y: 118 }, 'issues the certificate'),
    make('text', { class: 't-arrow', x: 372, y: 118 }, 'presents it'),
  ]);
}

async function chapterOrientation(context) {
  const fragment = document.createDocumentFragment();

  fragment.append(
    prose([
      'A <strong>verifiable credential</strong> is a document with a digital signature over it, made with a key that its issuer publishes at a stable identifier. That is nearly the whole idea. Anyone who receives the document can check the signature without contacting the issuer, without an account, and without a prior relationship.',
      'Three parties appear in every description of it. The <strong>issuer</strong> makes the document. The <strong>holder</strong> keeps it and presents it when needed. The <strong>verifier</strong> receives it and decides whether to believe it. In this domain those are usually a calibration laboratory, its customer, and whoever the customer has to satisfy.',
    ])
  );
  fragment.append(triangle());

  fragment.append(
    prose([
      'Signatures alone answer only one question: has this document been altered since it was made. They leave the harder question untouched, which is whether the party who made it had any standing to. A perfectly valid signature by an organisation nobody has heard of proves only that the organisation exists.',
      'That is the gap the W3C <strong>Recognized Entities</strong> specification addresses. A recognising authority issues a credential listing the entities it recognises and what each is recognised to do. A document carries a pointer to the list it claims to appear in, and a verifier follows those pointers upward until it reaches an identifier it already trusts.',
      'The quality infrastructure already works exactly this way. It just does it on paper, and the checking is done by people.',
    ])
  );

  fragment.append(
    panel(
      'The specification and this domain, side by side',
      'The mapping is close enough that almost nothing had to be invented',
      table(
        ['Recognized Entities', 'Quality infrastructure'],
        [
          ['Root of trust', 'BIPM under the CIPM MRA; ILAC under the ILAC MRA'],
          ['RecognizedEntityCredential', 'CIPM MRA participation; ISO/IEC 17025 accreditation'],
          ['RecognizedAction with an outputValidation schema', 'The declared CMC or the granted accreditation scope'],
          ['Leaf credential', 'Calibration certificate, test report, certificate of conformity'],
          ['recognizedIn, followed upward by the verifier', 'The recognition path a recipient checks by hand today'],
          ['Section 2.4, Product Conformity', 'A certificate of conformity meeting a market surveillance authority at a border'],
        ]
      )
    )
  );

  fragment.append(
    callout([
      'Two things in this demonstration go beyond the specification, because metrology needs them and general credential systems have no equivalent.',
      '<strong>The CMC decides the logo.</strong> An institute may apply the CIPM MRA logo only to work covered by a capability it has published. Here that is a machine-checkable claim rather than an image, and the recipient adjudicates it.',
      '<strong>The uncertainty travels with its budget.</strong> Each certificate states what it inherited from the one above it, so a recipient can check that the arithmetic holds and that nothing was quietly improved along the way.',
    ])
  );

  const stats = el('div', { class: 'stat-row', style: 'margin-top: 26px;' }, [
    stat(context.world.graph.nodes.length, 'organisations'),
    stat(context.world.credentials.length, 'signed credentials'),
    stat(context.world.documentCount, 'documents published'),
    stat(context.world.tamperCases.length, 'ways to break it'),
  ]);
  fragment.append(stats);

  return fragment;
}

// ---------------------------------------------------------------- chapter 1

async function chapterGraph(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'Ten organisations, and one supply chain running through them. A national metrology institute calibrates a laboratory&rsquo;s transfer standard; the laboratory calibrates a testing laboratory&rsquo;s multimeter; the testing laboratory measures a kettle; a certification body certifies the kettle; the manufacturer presents that certificate at a border.',
      'Click any organisation to see the identifier it signs with and what it has issued. Click any edge to read the credential behind it.',
    ])
  );

  const detail = panel('Select an organisation or an edge', 'Everything below is fetched from the running server', el('p', { class: 'muted', text: 'Nothing selected yet.' }));
  const graphHolder = el('div', {});

  const draw = (selectedNode, highlightEdges) => {
    clear(graphHolder).append(
      renderGraph(context.world.graph, {
        selectedNode,
        highlightEdges,
        onSelectNode: async (did) => {
          draw(did, []);
          const data = await api.actor(did);
          clear(detail).append(
            el('div', { class: 'panel__head' }, [
              el('h3', { class: 'panel__title', text: data.actor.legalName }),
              data.actor.isTrustAnchor ? badge('anchor', 'trust anchor') : null,
            ]),
            keyValues([
              ['Identifier', data.actor.id],
              ['Role', data.actor.role],
              ['Country', data.actor.country || 'international'],
              ['What it does', data.actor.description],
              ['What it issues', data.actor.issues || 'nothing; it receives and verifies'],
              ['Public key', el('span', { class: 'hash', text: data.actor.publicKeyMultibase })],
            ]),
            el('h3', { text: 'DID document' }),
            el('p', { class: 'muted', text: 'This is all an identifier resolves to: a key, what the key may be used for, and where to ask about the holder.' }),
            jsonView(data.didDocument, context.inspect),
            data.issued.length
              ? el('div', {}, [
                  el('h3', { text: 'Credentials it has issued' }),
                  el(
                    'div',
                    { class: 'chips' },
                    data.issued.map((item) =>
                      el('button', { class: 'chip', text: item.title, onclick: () => context.inspect(item.id) })
                    )
                  ),
                ])
              : null
          );
          detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        },
        onSelectEdge: async (edge) => {
          draw(selectedNode, [edge.credential]);
          const data = await api.credential(edge.credential);
          clear(detail).append(
            el('div', { class: 'panel__head' }, [
              el('h3', { class: 'panel__title', text: CREDENTIAL_LABELS[edge.credential] || edge.credential }),
              badge('neutral', edge.kind),
            ]),
            keyValues([
              ['From', edge.source],
              ['To', edge.target],
              ['Meaning', edge.kind === 'recognition' ? `recognised to ${edge.label}` : edge.label],
              ['Document', edge.credentialId],
            ]),
            jsonView(data.credential, context.inspect, { tall: true })
          );
          detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        },
      })
    );
  };

  draw(null, []);
  fragment.append(graphHolder, detail);
  return fragment;
}

// ---------------------------------------------------------------- chapter 2

async function chapterIssuing(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'A signature is made over bytes, and a JSON document does not have a single set of bytes: the same certificate can be written with different spacing, different member order, or different ways of writing the same number. So before anything is hashed, the document is put into a <strong>canonical form</strong>, and that is what gets signed. This is why a certificate can be reformatted on its way to a verifier without breaking.',
      'Two things are hashed separately and signed together: the document without its proof, and the proof configuration without its signature. Hashing the configuration too is what stops anyone editing the stated purpose, the key or the time after the fact.',
    ])
  );

  const holder = el('div', {});
  const picker = el(
    'div',
    { class: 'chips' },
    MAIN_CREDENTIALS.map((name) =>
      el('button', {
        class: 'chip',
        text: CREDENTIAL_LABELS[name],
        'aria-pressed': name === 'metas-calibration',
        onclick: (event) => {
          picker.querySelectorAll('.chip').forEach((chip) => chip.setAttribute('aria-pressed', 'false'));
          event.target.setAttribute('aria-pressed', 'true');
          show(name);
        },
      })
    )
  );

  async function show(name) {
    clear(holder).append(el('p', { class: 'spinner', text: 'Signing…' }));
    const data = await api.credential(name);
    const trace = data.trace;
    clear(holder).append(
      panel('1. The claims, before anything cryptographic happens', 'The document as its issuer assembled it', jsonView(
        Object.fromEntries(Object.entries(data.credential).filter(([key]) => key !== 'proof')),
        context.inspect,
        { tall: true }
      )),
      panel(
        '2. The canonical form',
        'RFC 8785: members sorted, no whitespace, numbers written one way only',
        el('pre', { class: 'code', text: wrap(trace.canonicalDocument, 110) })
      ),
      panel('3. What is hashed and signed', 'Two SHA-256 digests, concatenated, then signed with ECDSA over P-256', [
        keyValues([
          ['Digest of the document', el('span', { class: 'hash', text: trace.documentHash })],
          ['Digest of the proof configuration', el('span', { class: 'hash', text: trace.proofConfigHash })],
          ['The 64 bytes actually signed', el('span', { class: 'hash', text: trace.signingInput })],
          ['Resulting signature', el('span', { class: 'hash', text: trace.proofValue })],
        ]),
        el('p', { class: 'muted', style: 'margin-top: 12px;', text: 'Signing here is deterministic, per RFC 6979. Identical input always produces an identical signature, so any change in the signature is caused by a change in the document rather than by a fresh random number.' }),
      ]),
      panel('4. The finished credential', 'The proof configuration, plus the signature it covers', jsonView(data.credential.proof, context.inspect))
    );
  }

  fragment.append(picker, holder);
  await show('metas-calibration');
  return fragment;
}

function wrap(text, width) {
  const lines = [];
  for (let index = 0; index < text.length; index += width) lines.push(text.slice(index, index + width));
  return lines.join('\n');
}

// ---------------------------------------------------------------- chapter 3

async function chapterVerification(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'This is the demonstration proper. A market surveillance authority in an importing country receives a certificate of conformity. It has no relationship with the certification body, the testing laboratory, the calibration laboratory or the institute. It trusts two identifiers in the world: the BIPM and ILAC.',
      'It runs eleven checks. Four are generic, one walks the recognition chain, and six are about whether the metrology holds up. Expand any step to see what it decided.',
    ])
  );

  const state = { name: 'cab-conformity', when: context.world.demoNow.slice(0, 10), staple: false, maxDepth: 5, trustBoth: true };
  const output = el('div', {});

  const controls = el('div', { class: 'controls' }, [
    el('label', { class: 'field' }, [
      el('span', { text: 'Document to check' }),
      el(
        'select',
        {
          onchange: (event) => {
            state.name = event.target.value;
            run();
          },
        },
        MAIN_CREDENTIALS.map((name) =>
          el('option', { value: name, selected: name === state.name, text: CREDENTIAL_LABELS[name] })
        )
      ),
    ]),
    el('label', { class: 'field' }, [
      el('span', { text: 'Verified on' }),
      el('input', {
        type: 'date',
        value: state.when,
        onchange: (event) => {
          state.when = event.target.value;
          run();
        },
      }),
    ]),
    el('label', { class: 'field' }, [
      el('span', { text: 'Recognition depth limit' }),
      el('input', {
        type: 'number',
        min: 0,
        max: 10,
        value: state.maxDepth,
        style: 'width: 72px',
        onchange: (event) => {
          state.maxDepth = Number(event.target.value);
          run();
        },
      }),
    ]),
    el('button', {
      class: 'action',
      'aria-pressed': String(state.staple),
      text: 'Holder staples the recognition credentials',
      onclick: (event) => {
        state.staple = !state.staple;
        event.target.setAttribute('aria-pressed', String(state.staple));
        run();
      },
    }),
    el('button', {
      class: 'action',
      'aria-pressed': String(!state.trustBoth),
      text: 'Trust nobody',
      onclick: (event) => {
        state.trustBoth = !state.trustBoth;
        event.target.setAttribute('aria-pressed', String(!state.trustBoth));
        run();
      },
    }),
  ]);

  async function run() {
    clear(output).append(el('p', { class: 'spinner', text: 'Verifying…' }));
    const report = await api.verify({
      name: state.name,
      when: `${state.when}T12:00:00Z`,
      staple: state.staple,
      max_depth: state.maxDepth,
      trusted: state.trustBoth ? null : [],
    });
    clear(output).append(
      verdictBanner(report),
      retrievalSummary(report.fetches),
      el('p', {
        class: 'muted',
        text: state.staple
          ? 'The holder bundled the recognition credentials with the presentation, so the verifier read them from the presentation instead of going out for them. In a real deployment that is the difference between a border check that needs connectivity and one that does not.'
          : 'The verifier fetched everything itself. Toggle stapling above to see the same chain served from the presentation.',
      }),
      panel('What the verifier checked', 'Steps that passed are collapsed; open one to see inside', stepTree(report.steps, 0)),
      panel('What the verifier had to fetch', 'In the order it asked for them', el(
        'div',
        { class: 'json' },
        report.fetches
          .map((fetch, index) => `${String(index + 1).padStart(2, ' ')}. ${fetch.found ? '  ' : '!!'} ${fetch.source.padEnd(10)} ${fetch.url}`)
          .join('\n')
      ))
    );
  }

  fragment.append(controls, output);
  await run();
  return fragment;
}

// ---------------------------------------------------------------- chapter 4

async function chapterScope(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'A national metrology institute may put the CIPM MRA logo on a calibration certificate only when the calibration falls inside a capability it has published in the key comparison database. The published entry gives a measurand, a range, the conditions, and the <strong>smallest</strong> Expanded Uncertainty the institute can achieve.',
      'That last one is the part that catches people out. The capability is a floor, not a ceiling. A certificate claiming a <em>larger</em> uncertainty is comfortably inside scope. A certificate claiming a <em>smaller</em> one is claiming to have done better than the institute has ever demonstrated, and is outside it.',
      'Move the sliders. The verdict, and with it the legitimacy of the logo, is decided from the published entry rather than from anybody&rsquo;s judgement.',
    ])
  );

  const state = { value: 1.0e4, relative: 1.131e-7 };
  const readout = el('div', {});

  const valueSlider = sliderRow({
    label: 'Measured resistance',
    min: 0,
    max: 7,
    step: 0.02,
    value: Math.log10(state.value),
    format: (raw) => `${num(Math.pow(10, raw), 6)} Ω`,
    onInput: (raw) => {
      state.value = Math.pow(10, raw);
      update();
    },
  });

  const uncertaintySlider = sliderRow({
    label: 'Claimed U, relative (k = 2)',
    min: -8.3,
    max: -3,
    step: 0.02,
    value: Math.log10(state.relative),
    format: (raw) => `${num(Math.pow(10, raw) * 1e6, 3)} µΩ/Ω`,
    onInput: (raw) => {
      state.relative = Math.pow(10, raw);
      update();
    },
  });

  async function update() {
    const result = await api.scope({
      cmc: 'CH-EM-0042',
      value: state.value,
      expanded_uncertainty: state.relative * state.value,
      coverage_factor: 2.0,
    });

    const inScope = result.withinScope;
    clear(readout).append(
      el('div', { class: `verdict verdict--${inScope ? 'pass' : 'fail'}` }, [
        el('div', { class: 'verdict__mark', text: inScope ? '✓' : '✗' }),
        el('div', { class: 'verdict__text' }, [
          el('strong', { text: inScope ? 'Inside CMC CH-EM-0042 — the CIPM MRA logo is justified' : 'Outside CMC CH-EM-0042 — the CIPM MRA logo may not be used' }),
          el('span', {
            text: inScope
              ? 'The calibration is covered by a published, peer-reviewed capability, so its international recognition follows.'
              : 'The calibration may still be perfectly sound. What is not supported is the claim of international recognition that the logo makes.',
          }),
        ]),
      ]),
      keyValues([
        ['Claimed', `U = ${num(state.relative * state.value)} Ω at ${num(state.value, 6)} Ω, k = 2`],
        ['Smallest covered at this level', `${num(result.uncertaintyFloor)} Ω`],
        ['Published floor', result.floorDescription],
      ]),
      table(
        ['', 'Condition', 'What was compared'],
        result.verdict.checks.map((check) => [
          badge(check.passed ? 'pass' : 'fail'),
          check.title,
          check.detail,
        ])
      )
    );
  }

  const entry = context.world.cmcEntries.find((item) => item.identifier === 'CH-EM-0042');

  fragment.append(
    el('div', { class: 'split split--wide' }, [
      el('div', {}, [panel('Adjust the claim', 'Both axes are logarithmic', [valueSlider, uncertaintySlider]), readout]),
      panel('The published entry', 'Served from the registry, exactly as the verifier fetched it', jsonView(entry, context.inspect, { tall: true })),
    ]),
    callout([
      'The schema attached to the recognition can express the measurand, the unit and the range, because those are constants. It cannot express this uncertainty floor, which varies with the measured level. So the schema catches gross errors offline and the signed registry entry decides the rest. Both checks appear in the pipeline, and watching the schema pass while the registry check fails is the clearest way to see why one does not replace the other.',
    ])
  );

  await update();
  return fragment;
}

// ---------------------------------------------------------------- chapter 5

async function chapterTraceability(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'Metrological traceability is an unbroken chain of calibrations back to a realisation of the unit, each with a stated uncertainty. The credential chain has exactly the same shape, and each certificate inherits its parent&rsquo;s result as the first line of its own budget.',
      'Because the budget travels inside the credential, a recipient can check two things no signature could tell it: that the stated uncertainty really is the quadrature sum of the contributions offered for it, and that the inherited line matches what the parent certificate actually reports.',
    ])
  );

  const [metas, callab] = await Promise.all([api.credential('metas-calibration'), api.credential('callab-calibration')]);

  const levels = [
    { name: 'SI definition of the ohm', relative: 0, note: 'exact by definition' },
    { name: 'METAS national standard, certificate METAS-2026-0417', relative: metas.measurement.relativeExpandedUncertainty, note: metas.measurement.reported },
    { name: 'Alpine Calibration, certificate AC-2026-1182', relative: callab.measurement.relativeExpandedUncertainty, note: callab.measurement.reported },
    { name: 'Insulation resistance measured in the test report', relative: 0.4 / 12.4, note: '12.4 ± 0.4 MΩ (k = 2)' },
  ];
  const worst = Math.max(...levels.map((level) => level.relative));

  fragment.append(
    panel(
      'Expanded uncertainty down the chain',
      'Relative U at k = 2. Each step inherits everything above it and can only add',
      table(
        ['Level', 'Relative U (k = 2)', '', 'As reported'],
        levels.map((level) => [
          level.name,
          { numeric: true, value: level.relative ? `${num(level.relative * 1e6, 4)} µΩ/Ω` : '0' },
          el('div', { class: 'bar__track' }, el('div', {
            class: 'bar',
            style: `width: ${Math.max(1, (Math.log10(level.relative * 1e6 + 1) / Math.log10(worst * 1e6 + 1)) * 100)}%`,
          })),
          level.note,
        ])
      )
    )
  );

  for (const [label, data] of [
    ['METAS-2026-0417, at the national institute', metas],
    ['AC-2026-1182, at the accredited laboratory', callab],
  ]) {
    fragment.append(
      panel(
        `Uncertainty budget: ${label}`,
        `Combined u = ${num(data.measurement.standardUncertainty)} Ω, giving ${data.measurement.reported}`,
        table(
          ['Quantity', 'Value', 'u', 'Distribution', 'c', 'u × c', 'Index'],
          data.measurement.budget.map((line) => [
            line.source ? el('span', {}, [line.label, el('div', { class: 'muted', text: `from ${line.source}` })]) : line.label,
            { numeric: true, value: num(line.value, 8) },
            { numeric: true, value: num(line.standardUncertainty, 3) },
            line.distribution,
            { numeric: true, value: num(line.sensitivityCoefficient, 4) },
            { numeric: true, value: num(line.uncertaintyContribution, 3) },
            { numeric: true, value: percent(line.index) },
          ])
        )
      )
    );
  }

  const live = el('div', {});
  const state = {
    parent_expanded_uncertainty: metas.measurement.expandedUncertainty,
    ratio_uncertainty: 2.6e-6,
    drift_half_width: 5.0e-4,
    temperature_half_width: 2.0e-4,
  };

  async function recompute() {
    const result = await api.uncertainty(state);
    clear(live).append(
      el('div', { class: `verdict verdict--${result.withinAccreditation ? 'pass' : 'fail'}` }, [
        el('div', { class: 'verdict__mark', text: result.withinAccreditation ? '✓' : '✗' }),
        el('div', { class: 'verdict__text' }, [
          el('strong', { text: result.reported }),
          el('span', {
            text: result.withinAccreditation
              ? `Relative U = ${num(result.relativeExpandedUncertainty * 1e6, 4)} µΩ/Ω, inside accreditation SCS 0123 (best capability ${num(result.bestMeasurementCapability, 3)} Ω at this level)`
              : `Relative U = ${num(result.relativeExpandedUncertainty * 1e6, 4)} µΩ/Ω, better than accreditation SCS 0123 permits (${num(result.bestMeasurementCapability, 3)} Ω at this level)`,
          }),
        ]),
      ]),
      table(
        ['Quantity', 'u', 'c', 'u × c', 'Index'],
        result.budget.map((line) => [
          line.label,
          { numeric: true, value: num(line.standardUncertainty, 3) },
          { numeric: true, value: num(line.sensitivityCoefficient, 4) },
          { numeric: true, value: num(line.uncertaintyContribution, 3) },
          { numeric: true, value: percent(line.index) },
        ])
      )
    );
  }

  fragment.append(
    panel('Recompute the laboratory budget', 'Propagated with metas_unclib, which keeps track of where each uncertainty came from', [
      sliderRow({
        label: 'U inherited from the institute',
        min: -5,
        max: -1,
        step: 0.02,
        value: Math.log10(state.parent_expanded_uncertainty),
        format: (raw) => `${num(Math.pow(10, raw), 3)} Ω`,
        onInput: (raw) => {
          state.parent_expanded_uncertainty = Math.pow(10, raw);
          recompute();
        },
      }),
      sliderRow({
        label: 'u of the bridge ratio',
        min: -8,
        max: -4,
        step: 0.02,
        value: Math.log10(state.ratio_uncertainty),
        format: (raw) => `${num(Math.pow(10, raw), 3)}`,
        onInput: (raw) => {
          state.ratio_uncertainty = Math.pow(10, raw);
          recompute();
        },
      }),
      sliderRow({
        label: 'Drift interval, half-width',
        min: -5,
        max: -2,
        step: 0.02,
        value: Math.log10(state.drift_half_width),
        format: (raw) => `${num(Math.pow(10, raw), 3)} Ω`,
        onInput: (raw) => {
          state.drift_half_width = Math.pow(10, raw);
          recompute();
        },
      }),
      live,
    ]),
    callout([
      'Try dragging the inherited uncertainty far down. The budget still adds up, the certificate would still be validly signed, and the laboratory would still be genuinely accredited — but the result becomes better than its accreditation allows, and the inherited line stops matching the certificate it names. Those are the last two checks in the pipeline, and they are the only things that would notice.',
    ])
  );

  await recompute();
  return fragment;
}

// ---------------------------------------------------------------- chapter 6

const GROUP_LABELS = {
  forgery: 'Forgery — the cryptography catches these',
  standing: 'Standing — the organisation was not entitled to issue it',
  metrological: 'Metrology — everything verifies and the claim is still wrong',
};

const GROUP_NOTES = {
  forgery: 'Any Verifiable Credentials library would reject all of these. They are the easy half.',
  standing:
    'Signatures say nothing about whether an accreditation has lapsed, been suspended, or never covered this activity. Recognition chains and status lists do.',
  metrological:
    'Every signature verifies, every organisation is in good standing, and the document is still wrong. A system that checked only the cryptography would accept every one of these.',
};

async function chapterBreakIt(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'A demonstration where everything always passes teaches very little. Each case below is a specific thing that can go wrong, and each names in advance the single check that is supposed to notice it.',
      'The third group is the one worth dwelling on. In every case there, the signature is valid, the issuer is genuinely recognised, and the document is inside its validity period.',
    ])
  );

  const output = el('div', {});

  for (const group of ['forgery', 'standing', 'metrological']) {
    const cases = context.world.tamperCases.filter((item) => item.group === group);
    fragment.append(
      panel(
        GROUP_LABELS[group],
        null,
        [
          el('p', { class: 'muted', style: 'margin-top:-4px', text: GROUP_NOTES[group] }),
          el(
            'div',
            { class: 'chips' },
            cases.map((item) =>
              el('button', {
                class: 'chip',
                text: item.title,
                onclick: () => run(item.key),
              })
            )
          ),
        ]
      )
    );
  }

  async function run(key) {
    clear(output).append(el('p', { class: 'spinner', text: 'Applying the change and re-verifying…' }));
    const result = await api.tamper(key);
    const caught = result.caughtByExpectedStep;
    clear(output).append(
      panel(result.case.title, GROUP_LABELS[result.case.group], [
        prose([result.case.description]),
        keyValues([
          ['Expected to be caught by', el('code', { text: result.case.expectedStep })],
          ['Actually failed at', el('code', { text: result.failedSteps.join(', ') || 'nothing' })],
          ['Outcome', badge(caught ? 'pass' : 'fail', caught ? 'caught as expected' : 'not caught')],
        ]),
        callout([result.case.catches]),
        verdictBanner(result.report),
        stepTree(result.report.steps, 0),
      ])
    );
    output.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  fragment.append(output);
  return fragment;
}

// ---------------------------------------------------------------- chapter 7

async function chapterImplications() {
  const fragment = document.createDocumentFragment();

  fragment.append(
    prose([
      'The demonstration is a prototype and proves nothing about deployability. But it does make some things concrete enough to argue about, which is what it was for.',
    ])
  );

  fragment.append(
    panel('What actually becomes different', null, prose([
      '<strong>The recipient checks, not the issuer.</strong> Today a laboratory receiving a certificate that carries the CIPM MRA logo either takes the logo on trust or opens the KCDB and compares by eye. Here the comparison is made by whoever received the document, at the moment they received it, from the signed registry entry.',
      '<strong>Scope becomes enforceable rather than declaratory.</strong> An accreditation scope and a CMC both already state exactly what is covered. Making them machine-readable turns them from something published into something checked.',
      '<strong>Suspension takes effect immediately, everywhere.</strong> When an accreditation is suspended, every certificate already issued under it becomes unverifiable at the next check, without any of them being recalled or reissued.',
      '<strong>Traceability stops being an assertion.</strong> A test report that says its equipment was calibrated can be made to prove it, by content digest, all the way down to a national standard.',
      '<strong>Border clearance without correspondence.</strong> This is the case the Recognized Entities specification puts in section 2.4, and it works here: an authority holding two trusted identifiers reaches a verdict on a document from an organisation it has never dealt with.',
    ]))
  );

  fragment.append(
    panel('What a real deployment would need, and does not have yet', null, prose([
      '<strong>Governance of the identifiers.</strong> Someone has to decide what the BIPM&rsquo;s identifier is, who controls it, how it is rotated, and what happens when a key is compromised. This is a governance problem wearing a technical costume, and it is the hard part.',
      '<strong>The KCDB as a signed registry.</strong> The CMC data already exists and is already peer reviewed. What is missing is publication in a form that carries a signature and a stable content digest.',
      '<strong>Long-term validation.</strong> Calibration certificates are kept for decades and signatures do not age well. Anything real needs timestamping and an archival strategy from the start, not added later.',
      '<strong>Alignment with the DCC.</strong> The certificate payloads here are deliberately simplified for legibility. The obvious path is not to invent a format but to carry a PTB/DKD Digital Calibration Certificate as the credential subject, so the credential layer adds recognition and revocation to a payload the community has already agreed on.',
      '<strong>Selective disclosure.</strong> A calibration certificate names a customer and an instrument. A testing laboratory may need to prove its equipment is traceable and in scope without disclosing the certificate. That is what SD-JWT or BBS signatures are for, and none of it is implemented here.',
      '<strong>Relationship to eIDAS 2.0 and the EU Digital Identity Wallet.</strong> Organisational credentials are arriving in European regulation on their own schedule. Whatever the quality infrastructure does should meet that rather than run beside it.',
    ]))
  );

  fragment.append(
    panel('Honest open questions', null, prose([
      'Is a decentralised recognition chain actually better than each MRA simply publishing one signed list? For a hierarchy this shallow, possibly not, and the answer should be argued rather than assumed.',
      'Who verifies, in practice? The value depends entirely on the checking happening somewhere it does not happen today. If nobody runs the verifier, nothing has been gained.',
      'What does a failed check mean institutionally? The pipeline can say a certificate is outside a published CMC. It cannot say whether that is an error, a typo, or a capability that was updated last week and not yet published.',
      'How do these credentials relate to the certificates that remain legally authoritative? For a long time both will exist, and which one governs is a legal question, not a technical one.',
    ]))
  );

  fragment.append(
    el('p', {
      class: 'footnote',
      text:
        'Built as an exploration, not a proposal. Every organisation, identifier, certificate, capability and key in this demonstration is fictional; the identifiers use the .example domain reserved by RFC 2606, and the signing keys are derived from a seed published in the source tree.',
    })
  );

  return fragment;
}

// ----------------------------------------------------------------

export const CHAPTERS = [
  {
    id: 'orientation',
    title: 'What a verifiable credential is',
    eyebrow: 'Start here',
    lede: 'Written for someone who has not met verifiable credentials before, and who does know what a calibration certificate is.',
    render: chapterOrientation,
  },
  {
    id: 'graph',
    title: 'The quality infrastructure as a trust graph',
    eyebrow: 'The world',
    lede: 'Ten organisations, two international anchors, and one supply chain running from a national standard to a kettle at a border.',
    render: chapterGraph,
  },
  {
    id: 'issuing',
    title: 'Issuing a calibration certificate',
    eyebrow: 'How signing works',
    lede: 'From the claims an institute wants to make, through canonicalization and hashing, to the signature itself. Every intermediate value shown.',
    render: chapterIssuing,
  },
  {
    id: 'verification',
    title: 'Verification and recognition discovery',
    eyebrow: 'What a recipient checks',
    lede: 'A market surveillance authority that trusts two identifiers, meeting a certificate from an organisation it has never heard of.',
    render: chapterVerification,
  },
  {
    id: 'scope',
    title: 'The CMC decides the logo',
    eyebrow: 'Scope enforcement',
    lede: 'Whether a calibration may carry the CIPM MRA logo, adjudicated from the published capability rather than taken on trust.',
    render: chapterScope,
  },
  {
    id: 'traceability',
    title: 'Traceability and uncertainty',
    eyebrow: 'Where the numbers come from',
    lede: 'The credential chain and the traceability chain are the same chain. The uncertainty grows measurably along it.',
    render: chapterTraceability,
  },
  {
    id: 'break',
    title: 'Break it',
    eyebrow: 'Failure modes',
    lede: 'Eleven ways this can go wrong, and the one check that catches each. The interesting ones pass every cryptographic test.',
    render: chapterBreakIt,
  },
  {
    id: 'implications',
    title: 'What this would mean in practice',
    eyebrow: 'The argument',
    lede: 'What genuinely changes, what a real deployment would need, and what remains an open question.',
    render: chapterImplications,
  },
];
