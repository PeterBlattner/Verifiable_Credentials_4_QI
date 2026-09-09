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
  'global-aci-recognition': 'Global ACI recognition of accreditation bodies',
  'sas-recognition': 'Accreditation body recognition of laboratories',
  'metas-calibration': 'Calibration certificate METAS-2026-0417',
  'callab-calibration': 'Calibration certificate AC-2026-1182',
  'metas-SR10K-0091': 'Calibration certificate METAS-2026-0418 (check standard A)',
  'metas-SR10K-0092': 'Calibration certificate METAS-2026-0419 (check standard B)',
  'testlab-report': 'Test report HTS-2026-3391',
  'cab-conformity': 'Certificate of conformity CPC-2026-0055',
  'oiml-ia-recognition': 'OIML recognition of Issuing Authorities',
  'oiml-tl-recognition': 'OIML recognition of Test Laboratories',
  'oiml-evaluation': 'OIML type evaluation report HTS-TE-2024-0114',
  'oiml-certificate': 'OIML certificate R46/2024-CH1-0037',
};

const MAIN_CREDENTIALS = Object.keys(CREDENTIAL_LABELS);

// ---------------------------------------------------------------- the cautions

// The cautions, and the reason they are the first thing rather than a footnote. This
// chapter reads nothing from `context.world`, so it renders even when the world payload
// is thin or the demonstration behind it is broken -- a caution that only appears once
// everything else works is a caution that fails when it is most needed. The banner in
// index.html covers the case where not even this has loaded.
async function chapterCautions(context) {
  // Prose: web/content/chapters/00-cautions.md
  const t = context.text('cautions');
  const fragment = document.createDocumentFragment();

  fragment.append(t.prose('where-this-came-from'));

  // Written out rather than looped over the five keys: tests/test_content.py checks that
  // every content key is a literal string a regex can find, because the coverage checks
  // in both directions depend on that. A template literal here would pass silently in
  // the browser and take the static checks with it.
  fragment.append(panel(t.text('nothing-validated.title'), null, t.prose('nothing-validated.body')));
  fragment.append(panel(t.text('no-institution.title'), null, t.prose('no-institution.body')));
  fragment.append(panel(t.text('spec-moving.title'), null, t.prose('spec-moving.body')));
  fragment.append(panel(t.text('no-warranty.title'), null, t.prose('no-warranty.body')));
  fragment.append(panel(t.text('no-permanence.title'), null, t.prose('no-permanence.body')));

  fragment.append(t.callout('correction'));

  return fragment;
}

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
  // Prose: web/content/chapters/01-orientation.md
  const t = context.text('orientation');
  const fragment = document.createDocumentFragment();

  fragment.append(t.prose('what-it-is'));
  fragment.append(triangle());
  fragment.append(t.prose('the-gap-signatures-leave'));

  fragment.append(
    panel(t.text('mapping.title'), t.text('mapping.hint'), t.block('mapping.rows'))
  );

  fragment.append(t.callout('beyond-the-spec'));

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

const ISSUE_MODES = [
  { key: 'honest', label: 'Sign as yourself' },
  { key: 'impersonate', label: 'Claim to be METAS' },
  { key: 'steal-key-id', label: 'Claim METAS and its key id' },
];

async function chapterKeys(context) {
  // Prose: web/content/chapters/02-keys.md
  const t = context.text('keys');
  const fragment = document.createDocumentFragment();
  const state = { key: null };

  fragment.append(t.prose('what-a-key-is'));

  // ---- 1. make a keypair ------------------------------------------------------
  const keyOutput = el('div', {});
  const passphrase = el('input', {
    type: 'text',
    value: 'a passphrase you would never use for real',
    style: 'min-width: 320px',
  });

  async function derive(body) {
    const previous = state.key ? state.key.publicKeyMultibase : null;
    clear(keyOutput).append(el('p', { class: 'spinner', text: 'Computing…' }));
    const data = await api.deriveKey(body);
    const repeated = previous !== null && previous === data.publicKeyMultibase;
    state.key = data;

    clear(keyOutput).append(
      repeated
        ? el('div', { class: 'verdict verdict--pass' }, [
            el('div', { class: 'verdict__mark', text: '=' }),
            el('div', { class: 'verdict__text' }, [
              el('strong', { text: t.text('same-key.title') }),
              el('span', { text: t.text('same-key.body') }),
            ]),
          ])
        : null,
      el('div', { class: 'callout' }, el('p', { text: data.note })),
      el('h3', { text: t.text('private-key.title') }),
      el('pre', { class: 'code', text: wrap(data.privateScalarHex, 64) }),
      el('p', {
        class: 'muted',
        text: `That is the whole secret: one number, 32 bytes, ${data.privateScalarDecimalDigits} digits in decimal. Anyone who has it can sign anything at all in your name.`,
      }),
      el('h3', { text: t.text('public-key.title') }),
      el('pre', {
        class: 'code',
        text:
          `  d = 0x${data.privateScalarHex.slice(0, 24)}…\n` +
          '        |\n' +
          '        |   Q = d x G      multiply the curve generator by d\n' +
          '        v\n' +
          `  x = 0x${data.publicPoint.x.slice(0, 24)}…\n` +
          `  y = 0x${data.publicPoint.y.slice(0, 24)}…`,
      }),
      t.proseFill('one-way', { curve: data.curve.name }),
      panel(
        t.text('encoding.title'),
        t.text('encoding.hint'),
        table(
          ['Step', 'Value', 'What it adds'],
          data.encodingLayers.map((layer) => [
            layer.step,
            el('span', { class: 'hash', text: layer.value.slice(0, 52) + (layer.value.length > 52 ? '…' : '') }),
            layer.note,
          ])
        )
      ),
      keyValues([
        ['Your identifier', el('span', { class: 'hash', text: data.didKey })],
        ['Its DID document', el('button', {
          class: 'chip',
          text: 'show it',
          onclick: (event) => {
            event.target.replaceWith(jsonView(data.didDocument, context.inspect));
          },
        })],
      ]),
      t.prose('did-key')
    );
  }

  fragment.append(
    panel(t.text('keypair.title'), t.text('keypair.hint'), [
      el('div', { class: 'controls' }, [
        el('label', { class: 'field' }, [el('span', { text: 'Passphrase' }), passphrase]),
        el('button', {
          class: 'action action--primary',
          text: 'Derive a key from it',
          onclick: () => derive({ passphrase: passphrase.value }),
        }),
        el('button', {
          class: 'action',
          text: 'Give me a random one instead',
          onclick: () => derive({ random: true }),
        }),
      ]),
      keyOutput,
    ]),
    t.callout('randomness')
  );

  // ---- 2. which half does what ------------------------------------------------
  fragment.append(
    el('h3', { text: t.text('halves.title') }),
    t.prose('halves'),
    table(
      ['', 'Signing — what credentials use', 'Encryption — a different job'],
      [
        [el('strong', { text: 'private key' }), el('strong', { text: 'signs' }), 'decrypts'],
        [el('strong', { text: 'public key' }), el('strong', { text: 'verifies' }), 'encrypts'],
        ['kept secret by', 'the issuer', 'the recipient'],
        ['what you get', 'authenticity and integrity', 'confidentiality'],
        ['who can read the document', el('strong', { text: 'anyone' }), 'only the holder of the private key'],
      ]
    ),
    t.callout('not-secret')
  );

  // ---- 3. sign, then break it -------------------------------------------------
  const message = el('input', { type: 'text', value: 'The 10 kilohm standard reads 10000.0012 ohm.', style: 'min-width: 380px' });
  const signOutput = el('div', {});

  async function signAndBreak() {
    if (!state.key) {
      clear(signOutput).append(el('p', { class: 'muted', text: t.text('make-a-key-first') }));
      return;
    }
    clear(signOutput).append(el('p', { class: 'spinner', text: 'Signing…' }));

    const scalar = state.key.privateScalarHex;
    const text = message.value;
    const signed = await api.signMessage({ private_scalar_hex: scalar, message: text });
    const other = await api.deriveKey({ passphrase: `${passphrase.value} but different` });

    const attempts = [
      ['the right key and the right message', text, signed.signature.multibase, state.key.publicKeyMultibase],
      ['a different public key', text, signed.signature.multibase, other.publicKeyMultibase],
      ['one character changed in the message', `${text} `, signed.signature.multibase, state.key.publicKeyMultibase],
      ['one character changed in the signature', text, flipLast(signed.signature.multibase), state.key.publicKeyMultibase],
    ];

    const rows = [];
    for (const [label, msg, sig, pub] of attempts) {
      const result = await api.verifySignature({
        message: msg,
        signature_multibase: sig,
        public_key_multibase: pub,
      });
      rows.push([badge(result.valid ? 'pass' : 'fail'), label, result.reason]);
    }

    clear(signOutput).append(
      keyValues([
        ['SHA-256 of the message', el('span', { class: 'hash', text: signed.digest })],
        ['r', el('span', { class: 'hash', text: signed.signature.r })],
        ['s', el('span', { class: 'hash', text: signed.signature.s })],
        ['as it travels', el('span', { class: 'hash', text: signed.signature.multibase })],
      ]),
      el('p', { class: 'muted', text: signed.note }),
      table(['', 'Verifying with…', 'What the verifier can say'], rows)
    );
  }

  fragment.append(
    panel(t.text('sign.title'), t.text('sign.hint'), [
      el('div', { class: 'controls' }, [
        el('label', { class: 'field' }, [el('span', { text: 'Message' }), message]),
        el('button', { class: 'action action--primary', text: 'Sign it, then try to break it', onclick: signAndBreak }),
      ]),
      signOutput,
    ])
  );

  // ---- 4. anyone can sign -----------------------------------------------------
  const issueOutput = el('div', {});

  async function attempt(mode) {
    if (!state.key) {
      clear(issueOutput).append(el('p', { class: 'muted', text: t.text('make-a-key-first') }));
      return;
    }
    clear(issueOutput).append(el('p', { class: 'spinner', text: 'Signing a certificate and verifying it…' }));
    const data = await api.issueAsReader({ private_scalar_hex: state.key.privateScalarHex, mode });

    clear(issueOutput).append(
      prose([data.modeDescription]),
      el('div', { class: 'stat-row' }, [
        stat(data.proof, 'proof'),
        stat(data.recognition, 'recognition'),
        stat(data.report.outcome, 'overall'),
      ]),
      verdictBanner(data.report),
      panel(t.text('checks.title'), t.text('checks.hint'), stepTree(data.report.steps, 0)),
      panel(t.text('signed.title'), null, jsonView(data.credential, context.inspect, { tall: true }))
    );
    issueOutput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  fragment.append(
    el('h3', { text: t.text('anyone.title') }),
    t.prose('anyone'),
    panel(t.text('try.title'), null, [
      el(
        'div',
        { class: 'chips' },
        ISSUE_MODES.map((mode) =>
          el('button', { class: 'chip', text: mode.label, onclick: () => attempt(mode.key) })
        )
      ),
      issueOutput,
    ]),
    t.callout('second-attempt')
  );

  // ---- 5. where the key lives, and what it may do -----------------------------
  const chainOutput = el('div', {});

  async function followChain() {
    clear(chainOutput).append(el('p', { class: 'spinner', text: 'Resolving…' }));
    const data = await api.credential('metas-calibration');
    const actor = await api.actor('did:web:metas.example');
    const method = data.credential.proof.verificationMethod;
    const controller = method.split('#')[0];
    const published = actor.didDocument.verificationMethod[0];

    clear(chainOutput).append(
      table(
        ['Step', 'Value'],
        [
          ['the proof names a key', el('span', { class: 'hash', text: method })],
          ['everything before the # is the controller', el('span', { class: 'hash', text: controller })],
          ['resolve that identifier', 'https://metas.example/.well-known/did.json'],
          ['the document lists the key', el('span', { class: 'hash', text: published.publicKeyMultibase })],
          ['decode it', '33 bytes: the compressed point, exactly as above'],
        ]
      ),
      t.prose('controller'),
      jsonView(actor.didDocument, context.inspect)
    );
  }

  fragment.append(
    el('h3', { text: t.text('how.title') }),
    panel(t.text('follow.title'), null, [
      el('button', { class: 'action', text: 'Follow the chain for METAS-2026-0417', onclick: followChain }),
      chainOutput,
    ])
  );

  // ---- and what happens when it leaks -----------------------------------------
  fragment.append(
    el('h3', { text: t.text('leaks.title') }),
    t.prose('leaks'),
    el('p', { class: 'footnote', text: t.text('footnote') })
  );

  await derive({ passphrase: passphrase.value });
  return fragment;
}

/** Change the last character of a multibase string, to break a signature by one digit. */
function flipLast(value) {
  const last = value.slice(-1);
  return value.slice(0, -1) + (last === '1' ? '2' : '1');
}

// ---------------------------------------------------------------- chapter 2

async function chapterGraph(context) {
  // Prose: web/content/chapters/03-graph.md
  const t = context.text('graph');
  const fragment = document.createDocumentFragment();
  fragment.append(t.prose('the-world'));

  const detail = panel(t.text('detail.title'), t.text('detail.hint'), el('p', { class: 'muted', text: t.text('nothing-selected') }));
  const graphHolder = el('div', {});
  const filterHolder = el('div', { class: 'controls' });
  const filterNote = el('p', { class: 'muted' });
  const state = { branch: null };

  // The chips come from the server's own list of arrangements, so adding a fourth would
  // need nothing here.
  const branches = context.world.graph.branches || [];
  const nodes = context.world.graph.nodes;
  const edges = context.world.graph.edges;

  // The filter dims rather than removes, which means it changes no text on the page --
  // and a control that changes nothing is indistinguishable from a broken one, both to
  // a reader and to tools/ui-clicks.mjs, which reported these three as inert. So the
  // selection says what it selected, and how much of the diagram that is.
  const describe = () => {
    if (!state.branch) {
      return `All three arrangements: ${nodes.length} organisations, ${edges.length} documents and recognitions.`;
    }
    const option = branches.find((item) => item.key === state.branch) || {};
    const inBranch = nodes.filter((node) => (node.branches || []).includes(state.branch));
    const shared = inBranch.filter((node) => (node.branches || []).length > 1);
    const edgeCount = edges.filter((edge) => edge.branch === state.branch).length;
    const names = shared.map((node) => node.name).join(', ');
    return (
      `${option.label}: ${inBranch.length} organisations and ${edgeCount} documents, ` +
      `the rest dimmed. ` +
      (shared.length
        ? `${names} also appear${shared.length === 1 ? 's' : ''} in another arrangement, which is where the branches join.`
        : 'Nothing here belongs to another arrangement.')
    );
  };

  const drawFilters = () => {
    clear(filterHolder).append(
      el('span', { class: 'muted', text: 'Arrangement' }),
      ...[{ key: null, label: 'All three' }, ...branches].map((option) =>
        el('button', {
          class: 'action',
          'aria-pressed': String(state.branch === option.key),
          text: option.label,
          onclick: () => {
            state.branch = option.key;
            drawFilters();
            draw(null, []);
          },
        })
      )
    );
    clear(filterNote).append(document.createTextNode(describe()));
  };

  const draw = (selectedNode, highlightEdges) => {
    clear(graphHolder).append(
      renderGraph(context.world.graph, {
        selectedNode,
        highlightEdges,
        branch: state.branch,
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
              [
                'Arrangements',
                (context.world.graph.nodes.find((node) => node.id === did) || {}).branches
                  ?.map((key) => (branches.find((option) => option.key === key) || {}).label || key)
                  .join(', ') || 'none',
              ],
              ['Public key', el('span', { class: 'hash', text: data.actor.publicKeyMultibase })],
            ]),
            el('h3', { text: t.text('did.title') }),
            el('p', { class: 'muted', text: t.text('did-resolves') }),
            jsonView(data.didDocument, context.inspect),
            data.issued.length
              ? el('div', {}, [
                  el('h3', { text: t.text('issued.title') }),
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

  drawFilters();
  draw(null, []);
  fragment.append(filterHolder, filterNote, graphHolder, detail);
  return fragment;
}

// ---------------------------------------------------------------- chapter 3

async function chapterIssuing(context) {
  // Prose: web/content/chapters/04-issuing.md
  const t = context.text('issuing');
  const fragment = document.createDocumentFragment();
  fragment.append(t.prose('canonicalization'));

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
      panel(`1. ${t.text('claims.title')}`, t.text('claims.hint'), jsonView(
        Object.fromEntries(Object.entries(data.credential).filter(([key]) => key !== 'proof')),
        context.inspect,
        { tall: true }
      )),
      panel(
        `2. ${t.text('canonical.title')}`,
        t.text('canonical.hint'),
        el('pre', { class: 'code', text: wrap(trace.canonicalDocument, 110) })
      ),
      panel(`3. ${t.text('hashing.title')}`, t.text('hashing.hint'), [
        keyValues([
          ['Digest of the document', el('span', { class: 'hash', text: trace.documentHash })],
          ['Digest of the proof configuration', el('span', { class: 'hash', text: trace.proofConfigHash })],
          ['The 64 bytes actually signed', el('span', { class: 'hash', text: trace.signingInput })],
          ['Resulting signature', el('span', { class: 'hash', text: trace.proofValue })],
        ]),
        el('p', { class: 'muted', style: 'margin-top: 12px;', text: t.text('deterministic') }),
      ]),
      panel(`4. ${t.text('finished.title')}`, t.text('finished.hint'), jsonView(data.credential.proof, context.inspect))
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

// ---------------------------------------------------------------- chapter 4

async function chapterVerification(context) {
  // Prose: web/content/chapters/05-verification.md
  const t = context.text('verification');
  const fragment = document.createDocumentFragment();
  fragment.append(t.prose('the-scenario'));

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
        text: state.staple ? t.text('stapled') : t.text('unstapled'),
      }),
      panel(t.text('steps.title'), t.text('steps.hint'), stepTree(report.steps, 0)),
      panel(t.text('fetches.title'), t.text('fetches.hint'), el(
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

// ---------------------------------------------------------------- chapter 5

async function chapterScope(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'A national metrology institute may put the CIPM MRA logo on a calibration certificate only when the calibration falls inside a capability it has published in the key comparison database. The published entry gives a measurand, a range, the conditions, and the <strong>smallest</strong> Expanded Uncertainty the institute can achieve.',
      'That last one is the part that catches people out. The capability is a floor, not a ceiling. A certificate claiming a <em>larger</em> uncertainty is comfortably inside scope. A certificate claiming a <em>smaller</em> one is claiming to have done better than the institute has ever demonstrated, and is outside it.',
      'Move the sliders. The verdict, and with it the legitimacy of the logo, is decided from the published entry rather than from anybody&rsquo;s judgement.',
      'The same machinery bounds the legal-metrology branch, and there the bound is a better one. An OIML Issuing Authority may certify a type only against a Recommendation it has been approved for, and a Recommendation is a numbered, edition-controlled document published by somebody else &mdash; not a declaration the organisation wrote about itself. Try <em>Certify a type against a Recommendation nobody approved</em> in chapter 8: the certificate is signed by a genuinely recognised body and rejected anyway, twice over, because the recognition names both the Recommendation and a schema built from it.',
      'What is still missing is that the schema is this project&rsquo;s reading of R 46 rather than R 46 speaking for itself. The OIML is working towards machine-readable Recommendations; until then, the bound is only as good as whoever transcribed it. That is the last item in chapter 11.',
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
      return update();
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
      return update();
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

// ---------------------------------------------------------------- chapter 6

/** Render the PTB/DKD DCC tab: the document, and what it does that the others do not. */
function dccTab(body, representations, context) {
  const dcc = representations.find((item) => item.format === 'PTB-DKD-DCC-XML');
  if (!dcc) {
    body.append(el('p', { class: 'muted', text: 'This certificate carries no PTB/DKD DCC.' }));
    return;
  }

  body.append(
    prose([
      'The <strong>PTB/DKD DCC</strong> is doing something different from the other three, and the difference is worth pausing on. Note the name, too: several things are called a PTB/DKD DCC, and this is the one the PTB and the DKD define.',
      'Classical, UncLib and GTC all describe a <em>result</em> — how good a number is, and what it rests on. A PTB/DKD DCC describes a <em>document</em>: who calibrated what, for whom, when, under which conditions, with which equipment, and what came out. It is a calibration certificate in a schema, not an uncertainty in a format.',
      `Inside it the quantity is written in <strong>D-SI</strong>, which is where the two levels meet. And D-SI's <code>si:expandedUnc</code> carries a value, an uncertainty, a coverage factor and a probability — that is the classical statement exactly, and it is not the dependency structure. So the two do not compete: a certificate wanting a standardised document <em>and</em> transmissible dependencies carries a PTB/DKD DCC and an UncLib block together, which is what this one does.`,
    ]),
    keyValues([
      ['Schema', `PTB/DKD DCC ${dcc.schemaVersion}, namespace https://ptb.de/dcc`],
      ['Quantities', `${dcc.quantityFormat}, namespace https://ptb.de/si`],
      ['Carried', 'content' in dcc ? 'inline in the credential' : `separately, at ${dcc.id}`],
      ['Digest', el('span', { class: 'hash', text: dcc.digestMultibase })],
    ]),
    panel(
      'How this certificate maps onto the schema',
      'our field on the left, the element it becomes on the right',
      table(
        ['This demonstration', 'PTB/DKD DCC'],
        [
          ['certificate number', 'dcc:administrativeData / dcc:coreData / dcc:uniqueIdentifier'],
          ['the calibrated instrument', 'dcc:administrativeData / dcc:items / dcc:item'],
          ['the issuing laboratory', 'dcc:administrativeData / dcc:calibrationLaboratory'],
          ['the owner', 'dcc:administrativeData / dcc:customer'],
          ['date of calibration', 'dcc:coreData / dcc:beginPerformanceDate'],
          ['conditions', 'dcc:measurementResult / dcc:influenceConditions'],
          ['the reference standard', 'dcc:measurementResult / dcc:measuringEquipments'],
          ['value and unit', 'si:real / si:value and si:unit'],
          ['U and k', 'si:expandedUnc / si:uncertainty and si:coverageFactor'],
        ]
      )
    ),
    callout([
      'One detail worth having been careful about: D-SI writes units the way siunitx does, as English names each preceded by a backslash. Ohm is <code>\\ohm</code>. Kilogram is <code>\\kilo\\gram</code> and <em>not</em> <code>\\kilogram</code>, because the prefix is a token of its own. The generator here refuses to emit a unit it has no mapping for, rather than guessing — a certificate that quietly states the wrong unit is worse than one that fails to be produced.',
    ]),
    el('h3', { text: 'The document' }),
    el('pre', { class: 'code json json--tall', text: dcc.content || `published separately at ${dcc.id}` }),
    callout([dcc.signatureNote])
  );
}

/** Show every fact the credential and the PTB/DKD DCC both state, and whether they agree. */
async function duplicationPanel(context, certificateName) {
  const data = await api.credential(certificateName);
  const report = await api.verify({ name: certificateName });

  const find = (id) => {
    const walk = (steps) => {
      for (const step of steps) {
        if (step.id === id) return step;
        const found = walk(step.children || []);
        if (found) return found;
      }
      return null;
    };
    return walk(report.steps);
  };

  const duplication = find('uncertainty.duplication');
  const agreement = find('uncertainty.agreement');

  const rows = (duplication && duplication.children ? duplication.children : []).map((child) => {
    const parts = child.detail.split(', PTB/DKD DCC says ');
    return [
      badge(child.status),
      child.title,
      el('span', { class: 'hash', text: (parts[0] || '').replace('credential says ', '') }),
      el('span', { class: 'hash', text: parts[1] || '' }),
    ];
  });

  return panel(
    'What is now said twice',
    'the cost of putting one standardised document inside another',
    [
      prose([
        'Wrapping a PTB/DKD DCC in a credential duplicates most of the certificate. That is not a flaw in either format — each was built to stand alone — but putting one inside the other makes the overlap unavoidable, and <strong>duplication permits disagreement</strong>. The signature stops anyone editing either copy after issue. It does nothing at all about an issuer writing them inconsistent in the first place.',
      ]),
      rows.length
        ? table(['', 'Fact', 'The credential says', 'The PTB/DKD DCC says'], rows)
        : el('p', { class: 'muted', text: 'No duplicated facts were compared.' }),
      agreement
        ? el('p', {
            class: 'muted',
            text: `And the measurement itself: ${agreement.detail}`,
          })
        : null,
      el('h3', { text: 'Including the signature' }),
      table(
        ['', 'The credential proof', 'ds:Signature in a PTB/DKD DCC'],
        [
          ['canonicalization', 'RFC 8785 over the credential', 'XML C14N over the document'],
          ['finding the key', 'resolve the issuer identifier', 'an X.509 certificate chain'],
          ['revocation', 'a status list', 'CRL or OCSP'],
          ['what it covers', 'the credential, including a digest of the PTB/DKD DCC', 'the PTB/DKD DCC alone'],
        ]
      ),
      callout([
        'A document carrying both can verify under one mechanism and fail under the other, and there is no natural rule for which wins. So this demonstration <strong>signs once</strong>: the credential proof covers the credential, the credential carries a digest of the PTB/DKD DCC bytes, and the <code>ds:Signature</code> slot stays empty. One trust path. That is a choice rather than an obligation.',
        'There are three honest ways to live with the rest of the redundancy, and only the first is built here. <strong>Duplicate and check</strong>, so every repeated fact becomes somewhere a mistake gets caught. <strong>Do not duplicate</strong>, by making the PTB/DKD DCC the credential subject and letting <code>issuer</code> and <code>validFrom</code> be views of it — cleanest, and probably what a real deployment settles on. Or <strong>declare precedence</strong>, saying which copy governs, which works and needs governance and is never read at the moment it is needed.',
      ]),
    ]
  );
}

/**
 * Show the same measurement in each way it can be handed to a customer.
 *
 * Three columns of the same certificate: what a paper certificate prints, what the
 * dependency representation carries, and what an independent implementation of the same
 * idea would carry. The point of putting them side by side is that all three describe
 * one measurement, and only the last two let the recipient do anything further with it.
 */
async function representationPanel(context, certificateName) {
  const data = await api.credential(certificateName);
  const result = data.credential.credentialSubject.calibration.results[0];
  const representations = result.uncertaintyRepresentations || [];
  const gtc = await api.gtc();

  const body = el('div', {});
  const tabs = [
    { key: 'classical', label: 'Classical' },
    { key: 'unclib', label: 'METAS UncLib' },
    { key: 'gtc', label: 'GTC' },
    { key: 'dcc', label: 'PTB/DKD DCC' },
  ];

  const bar = el(
    'div',
    { class: 'chips' },
    tabs.map((tab, index) =>
      el('button', {
        class: 'chip',
        text: tab.label,
        'aria-pressed': String(index === 0),
        onclick: () => {
          bar.querySelectorAll('.chip').forEach((chip, position) =>
            chip.setAttribute('aria-pressed', String(position === index))
          );
          show(tab.key);
        },
      })
    )
  );

  function show(kind) {
    clear(body);
    if (kind === 'classical') {
      const classical = representations.find((item) => item.type === 'ClassicalStatement');
      body.append(
        el('div', { class: 'stat__value', text: result.reported }),
        prose([
          'This is the whole of what a calibration certificate has stated for as long as calibration certificates have existed, and for most purposes it is enough. It tells you how good the number is.',
          'What it cannot tell you is anything about <em>where</em> the uncertainty came from. Two certificates reported this way are, as far as any recipient can determine, unrelated — even when both rest on the same reference standard in the same laboratory.',
        ]),
        classical ? keyValues([
          ['Value', `${classical.value} ${classical.unit}`],
          ['Standard Uncertainty u', classical.standardUncertainty],
          ['Expanded Uncertainty U', classical.expandedUncertainty],
          ['Coverage factor k', classical.coverageFactor],
        ]) : null
      );
      return;
    }

    if (kind === 'unclib') {
      const xml = representations.find((item) => item.format === 'METAS-UncLib-XML');
      const binary = representations.find((item) => item.format === 'METAS-UncLib-binary');
      if (!xml) {
        body.append(el('p', { class: 'muted', text: 'This certificate carries no dependency representation.' }));
        return;
      }
      body.append(
        prose([
          `The same result, transmitted with everything it depends on: ${xml.inputQuantityCount} input quantities, each with its own identifier, its distribution, and the sensitivity of the result to it.`,
          'The identifiers are what matter. They travel with the number, so an influence stays recognisable wherever it turns up again, and a recipient combining two results can tell that part of their uncertainty is one and the same thing.',
        ]),
        table(
          ['Identifier', 'Influence'],
          xml.inputQuantities.map((influence) => [
            el('span', { class: 'hash', text: influence.id }),
            influence.description,
          ])
        ),
        el('h3', { text: 'As transmitted' }),
        el('pre', { class: 'code json', text: xml.content || `published separately at ${xml.id}` }),
        binary
          ? panel(
              'The same thing, in binary',
              `${binary.byteCount} bytes against ${(xml.content || '').length} characters of XML`,
              [
                el('p', { class: 'muted', text: 'Published separately and referenced by digest, which is what the binary form is for: a result depending on thousands of influences, as an ordinary scattering-parameter measurement does, is not something to write out as XML.' }),
                el('button', {
                  class: 'action',
                  text: 'Fetch it as a customer would',
                  onclick: async (event) => {
                    const fetched = await api.uncertaintyData(binary.id);
                    event.target.replaceWith(
                      keyValues([
                        ['Address', binary.id],
                        ['Media type', fetched.mediaType],
                        ['Size', `${fetched.bytes} bytes`],
                        ['Digest recorded in the credential', el('span', { class: 'hash', text: binary.digestMultibase })],
                      ])
                    );
                  },
                }),
              ]
            )
          : null
      );
      return;
    }

    if (kind === 'dcc') {
      dccTab(body, representations, context);
      return;
    }

    const archive = representations.find((item) => item.format === 'GTC-archive-JSON');
    body.append(
      prose([
        'The <strong>GUM Tree Calculator</strong>, from the Measurement Standards Laboratory of New Zealand, arrives at the same design independently: elementary uncertain numbers carry UUID-based identifiers, and an archive of them serialises to JSON or XML against a published schema.',
        'Two implementations reaching the same conclusion is a better argument for the idea than one, and it is why the credential names a <em>format</em> rather than assuming a library. A certificate can carry either, or both, and a recipient uses whichever it can read.',
      ])
    );
    if (archive) {
      body.append(
        keyValues([['Format', archive.format], ['Specification', archive.specification]]),
        el('pre', { class: 'code json', text: archive.content || `published separately at ${archive.id}` })
      );
    } else {
      body.append(
        el('div', { class: 'callout' }, el('p', { text: gtc.note })),
        el('p', { class: 'muted', text: 'Everything else in this chapter works either way. The credential simply carries one dependency representation instead of two.' })
      );
    }
  }

  show('classical');
  return panel(
    'One measurement, four ways of handing it over',
    certificateName === 'metas-calibration' ? 'Certificate METAS-2026-0417' : certificateName,
    [bar, body]
  );
}


async function chapterTraceability(context) {
  // Prose: web/content/chapters/07-traceability.md
  const t = context.text('traceability');
  const fragment = document.createDocumentFragment();
  fragment.append(t.prose('the-chain'));

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
      t.text('chain.title'),
      t.text('chain.hint'),
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

  fragment.append(await representationPanel(context, 'metas-calibration'));
  fragment.append(await duplicationPanel(context, 'metas-calibration'));

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
    panel(t.text('recompute.title'), t.text('recompute.hint'), [
      sliderRow({
        label: 'U inherited from the institute',
        min: -5,
        max: -1,
        step: 0.02,
        value: Math.log10(state.parent_expanded_uncertainty),
        format: (raw) => `${num(Math.pow(10, raw), 3)} Ω`,
        onInput: (raw) => {
          state.parent_expanded_uncertainty = Math.pow(10, raw);
          return recompute();
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
          return recompute();
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
          return recompute();
        },
      }),
      live,
    ]),
    t.callout('try-dragging')
  );

  await recompute();
  return fragment;
}

// ---------------------------------------------------------------- chapter 7

const OPERATIONS = [
  { key: 'difference', label: 'R1 − R2', hint: 'checking two standards against each other' },
  { key: 'ratio', label: 'R1 / R2', hint: 'a resistance ratio' },
  { key: 'mean', label: '(R1 + R2) / 2', hint: 'averaging two check standards' },
];

async function chapterDependencies(context) {
  // Prose: web/content/chapters/08-dependencies.md
  const t = context.text('dependencies');
  const fragment = document.createDocumentFragment();

  fragment.append(t.prose('shared-standard'));

  const output = el('div', {});
  const state = { operation: 'difference' };

  const picker = el(
    'div',
    { class: 'chips' },
    OPERATIONS.map((operation) =>
      el('button', {
        class: 'chip',
        text: operation.label,
        title: operation.hint,
        'aria-pressed': String(operation.key === state.operation),
        onclick: () => {
          state.operation = operation.key;
          picker.querySelectorAll('.chip').forEach((chip, index) =>
            chip.setAttribute('aria-pressed', String(OPERATIONS[index].key === state.operation))
          );
          run();
        },
      })
    )
  );

  async function run() {
    clear(output).append(el('p', { class: 'spinner', text: 'Combining…' }));
    const data = await api.combine({ operation: state.operation });

    const understates = data.direction === 'understates';
    clear(output).append(
      el('div', { class: 'split' }, [
        panel(t.text('tracked.title'), t.text('tracked.hint'), [
          el('div', { class: 'stat__value', text: data.tracked.reported }),
          el('p', { class: 'muted', text: data.tracked.basis }),
        ]),
        panel(t.text('naive.title'), t.text('naive.hint'), [
          el('div', { class: 'stat__value', text: data.naive.reported }),
          el('p', { class: 'muted', text: data.naive.basis }),
        ]),
      ]),
      el('div', { class: `verdict verdict--${understates ? 'fail' : 'pass'}` }, [
        el('div', { class: 'verdict__mark', text: understates ? '!' : '✓' }),
        el('div', { class: 'verdict__text' }, [
          el('strong', {
            text: `Classical reporting ${data.direction} the uncertainty of ${data.expression} by ${data.factor.toFixed(2)}×`,
          }),
          el('span', {
            text: understates
              ? t.text('optimistic')
              : `The two results are correlated at r = ${data.correlation.toFixed(3)} because they share ${data.sharedInfluences.length} input quantities. That correlation is recoverable from the dependency representations and from nothing else.`,
          }),
        ]),
      ]),
      panel(
        t.text('shared.title'),
        t.text('shared.hint'),
        table(
          ['Identifier', 'Influence'],
          data.sharedInfluences.map((influence) => [
            el('span', { class: 'hash', text: influence.id }),
            influence.description,
          ])
        )
      ),
      panel(t.text('inputs.title'), null, table(
        ['Certificate', 'As reported'],
        data.inputs.map((input) => [
          el('button', {
            class: 'chip',
            text: input.certificate.split('/').pop(),
            onclick: () => context.inspect(input.certificate),
          }),
          input.reported,
        ])
      ))
    );
  }

  fragment.append(
    panel(t.text('question.title'), null, picker),
    output,
    t.callout('the-cost')
  );

  await run();
  return fragment;
}

// ---------------------------------------------------------------- chapter 8

async function chapterBreakIt(context) {
  // Prose: web/content/chapters/09-break.md
  const t = context.text('break');
  const fragment = document.createDocumentFragment();
  fragment.append(t.prose('why-break-it'));

  // The three group headings and their notes used to be two module-level maps keyed by
  // group name. They are read by literal key instead, because a computed key is
  // invisible to the test that checks every key a chapter asks for exists -- and that
  // one test is what makes the others able to see anything at all.
  const GROUPS = [
    { key: 'forgery', label: t.text('forgery.title'), note: t.text('forgery.hint') },
    { key: 'standing', label: t.text('standing.title'), note: t.text('standing.hint') },
    { key: 'metrological', label: t.text('metrological.title'), note: t.text('metrological.hint') },
  ];
  const labelFor = (key) => (GROUPS.find((group) => group.key === key) || {}).label;

  const output = el('div', {});

  for (const group of GROUPS) {
    const cases = context.world.tamperCases.filter((item) => item.group === group.key);
    fragment.append(
      panel(
        group.label,
        null,
        [
          el('p', { class: 'muted', style: 'margin-top:-4px', text: group.note }),
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
      panel(result.case.title, labelFor(result.case.group), [
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

// ---------------------------------------------------------------- chapter 9

async function chapterImplications(context) {
  // Prose: web/content/chapters/10-implications.md
  const t = context.text('implications');
  const fragment = document.createDocumentFragment();

  fragment.append(t.prose('prototype'));
  fragment.append(panel(t.text('different.title'), null, t.prose('different')));
  fragment.append(panel(t.text('needed.title'), null, t.prose('needed')));
  fragment.append(panel(t.text('questions.title'), null, t.prose('questions')));

  return fragment;
}
// ---------------------------------------------------------------- chapter 10

// Blue for the anchor, amber for a key an organisation has to hold itself, green for
// not holding one. The ordering is the argument: the further down the chain, the less
// ceremony the key demands.
const CUSTODY = {
  root: ['anchor', 'Root-grade custody'],
  service: ['warn', 'Service-grade custody'],
  delegated: ['pass', 'Delegated, or no key at all'],
};

const ONLINE_KIND_LABELS = {
  'did-document': 'DID document — the signing key, and nothing secret',
  'status-list': 'Status list — what has been withdrawn since',
  'registry-entry': 'Registry entries — the published CMCs and scopes',
  schema: 'Schemas — the shape each claim has to take',
  presentation: 'whois — the fallback that recognition discovery uses',
};

async function chapterInfrastructure(context) {
  // Prose: web/content/chapters/11-infrastructure.md
  const t = context.text('infrastructure');
  const fragment = document.createDocumentFragment();
  const data = await api.infrastructure();

  fragment.append(t.prose('two-properties'));

  const trace = data.verifierTrace;
  const uncached = trace.documents - trace.distinct;

  fragment.append(
    panel(t.text('fetches.title'), `verifying ${trace.title}, the deepest chain here`, [
      el('div', { class: 'stat-row' }, [
        stat(trace.distinct, 'distinct documents'),
        stat(trace.hostCount, 'hosts contacted'),
        stat(0, 'accounts needed at any of them'),
        stat(trace.documents, 'retrievals, with no cache'),
      ]),
      callout([
        `The gap between ${trace.documents} retrievals and ${trace.distinct} distinct documents is this implementation resolving the same DID documents again at every hop. An ordinary HTTP cache removes all ${uncached} of them. Nothing in the design requires that work, and the unflattering number is quoted here rather than quietly dropped.`,
        `The ${trace.hostCount} hosts are simply the organisations in the chain, and the verifier holds no relationship with any of them. That is the entire online surface the system depends on.`,
      ]),
    ])
  );

  fragment.append(t.prose('unevenly-spread'));

  const output = el('div', {});
  const state = { did: data.roles[0].actor.id };

  const picker = el(
    'div',
    { class: 'chips' },
    data.roles.map((role) =>
      el('button', {
        class: 'chip',
        text: role.actor.name,
        title: role.actor.role,
        'aria-pressed': String(role.actor.id === state.did),
        onclick: () => {
          state.did = role.actor.id;
          picker.querySelectorAll('.chip').forEach((chip, index) =>
            chip.setAttribute('aria-pressed', String(data.roles[index].actor.id === state.did))
          );
          render();
        },
      })
    )
  );

  function checklist(modifier, items) {
    return el(
      'ul',
      { class: `checklist checklist--${modifier}` },
      items.map((item) => el('li', { text: item }))
    );
  }

  function render() {
    const role = data.roles.find((item) => item.actor.id === state.did);
    const profile = role.profile;
    const hosting = role.hosting;
    const [tone, custodyLabel] = CUSTODY[profile.custodyGrade];

    clear(output).append(
      panel(role.actor.legalName, role.actor.role, [
        callout([profile.posture]),
        el('div', { class: 'stat-row' }, [
          stat(hosting.onlineCount, 'documents it must keep online'),
          stat(role.issuedCount, 'credentials it issued'),
          stat(hosting.travellingCount, 'documents that travel, unhosted'),
        ]),
        el('p', {
          class: 'muted',
          text:
            role.issuedCount === 0
              ? t.text('pure-verifier')
              : t.text('does-not-grow'),
        }),
      ]),

      panel(
        t.text('reachable.title'),
        t.text('reachable.hint'),
        hosting.online.map((group) =>
          el('div', {}, [
            el('p', { class: 'muted', text: ONLINE_KIND_LABELS[group.kind] || group.kind }),
            el(
              'div',
              { class: 'chips' },
              group.urls.map((url) =>
                el('button', {
                  class: 'chip',
                  text: url.replace('https://', ''),
                  onclick: () => context.inspect(url),
                })
              )
            ),
          ])
        )
      ),

      panel(t.text('key.title'), null, [
        el('div', { style: 'margin-bottom:10px' }, [badge(tone, custodyLabel)]),
        prose([profile.custody]),
      ]),

      el('div', { class: 'split' }, [
        panel(t.text('already.title'), t.text('already.hint'), [checklist('has', profile.alreadyRuns)]),
        panel(t.text('must-add.title'), null, [checklist('needs', profile.mustAdd)]),
      ]),

      panel(t.text('availability.title'), null, [
        keyValues([
          ['If it is unreachable', profile.availability],
          ['Volume', profile.scale],
        ]),
      ]),

      el('div', { class: 'callout', html: t.fill('hardest', { part: profile.hardestPart }) })
    );
  }

  fragment.append(panel(t.text('whose.title'), null, picker), output);

  fragment.append(
    panel(t.text('new.title'), null, t.prose('new'))
  );

  fragment.append(t.prose('next-chapter'));

  render();
  return fragment;
}

// ---------------------------------------------------------------- chapter 11

// Render a blank-line-separated editorial field as paragraphs, without opening it to
// markup. `keyValues` sets textContent, which is deliberate -- tests/test_deployment.py
// asserts no harmonisation field contains a tag, because a field that reached innerHTML
// would show a reader its angle brackets. So this builds real <p> elements and still
// sets `text:` on each, which gives paragraphs and keeps that contract.
function textParagraphs(value) {
  const parts = String(value).split('\n\n').filter((part) => part.trim());
  if (parts.length < 2) return value;
  return el('div', { class: 'stacked' }, parts.map((part) => el('p', { text: part })));
}

// Ordered by how much already exists, and coloured for it: green where a register exists
// and the work is adoption, amber where a specification answers the mechanical half and
// something institutional is left, grey where somebody else is still building it, blue
// where the page is genuinely blank.
//
// `partial` arrived with the review. Without it, five items that had answers in published
// specifications were filed under 'Nothing exists yet', which is the one thing on this
// page most likely to be quoted and the one it was most wrong about.
const HARMONISATION_STATUS = {
  available: ['pass', 'A register already exists'],
  partial: ['warn', 'Answered in part, elsewhere'],
  emerging: ['skip', 'Being built elsewhere'],
  open: ['anchor', 'Nothing exists yet'],
};

async function chapterHarmonisation(context) {
  const fragment = document.createDocumentFragment();
  const data = await api.harmonisation();
  const titleOf = {};
  for (const tier of data.tiers) {
    for (const item of tier.items) titleOf[item.key] = item.title;
  }

  fragment.append(
    prose([
      'The previous chapter asked what one organisation would have to run. This asks the harder question: what would they all have to agree with each other, so that a certificate written in one country means the same thing in another. That is the problem the quality infrastructure exists to solve, and signatures do not touch it.',
      'Start with something this demonstration gets wrong, because it is the clearest case on the page.',
    ])
  );

  const cmc = (context.world.cmcEntries || []).find((entry) => entry.measurand === 'dc.resistance');
  const scope = (context.world.accreditations || []).find((entry) => entry.measurand === 'dc.resistance');

  fragment.append(
    panel('Two organisations, one string', 'fetch both — the BIPM publishes one, the accreditation body the other', [
      el('div', { class: 'chips' }, [
        cmc
          ? el('button', {
              class: 'chip',
              text: `CMC ${cmc.identifier}`,
              onclick: () => context.inspect(cmc.id),
            })
          : null,
        scope
          ? el('button', {
              class: 'chip',
              text: `Accreditation scope ${scope.identifier}`,
              onclick: () => context.inspect(scope.id),
            })
          : null,
      ]),
      callout([
        'Both say <code>dc.resistance</code>, and chapter 5 decides whether a calibration may carry the CIPM MRA logo by comparing those two strings for equality. They match because one author wrote both files. Two organisations that had never spoken would not have produced the same string, and the comparison would fail — not because the laboratory was outside its scope, but because nobody had agreed a name for resistance.',
        'The instinct is to conclude that the metrology vocabularies are missing and would have to be invented. That is wrong, and worth correcting carefully: the BIPM already publishes permanent digital identifiers for every SI unit through the <a href="https://si-digital-framework.org/SI?lang=en">SI Digital Framework</a>, resolvable CMC identifiers already exist through the <a href="https://si-digital-framework.org/kcdb-cmc/">KCDB-CMC service</a>, and identifiers for measurands are being worked on at ISO and IEC. The finding is not that no vocabulary exists. It is that one exists and this demonstration did not use it.',
      ]),
    ])
  );

  fragment.append(
    prose([
      'What follows is sorted by one test, and anything failing it was left out: <strong>two conforming implementations that differ here cannot interoperate.</strong> That is what separates a harmonisation need from a deployment gap, and chapter 9 has the deployment gaps already. The tiers are meant to be read in order, because the order is the argument.',
    ])
  );

  // Counted from the items rather than written into the prose. An earlier draft of this
  // chapter left the impression that most of the list was a blank page, and it was the
  // one claim here a reader was most likely to repeat.
  const items = data.tiers.flatMap((tier) => tier.items);
  const count = (status) => items.filter((item) => item.status === status).length;
  const openCount = count('open');
  const share = Math.round((openCount / items.length) * 100);

  fragment.append(
    panel('How much of this is actually open', 'counted from the items below, not asserted', [
      el('div', { class: 'chips' }, [
        badge('pass', `${count('available')} already exist`),
        badge('warn', `${count('partial')} answered in part`),
        badge('skip', `${count('emerging')} being built`),
        badge('anchor', `${openCount} genuinely open`),
      ]),
      callout([
        `Of ${items.length} items, <strong>${openCount}</strong> — about ${share}% — have nothing to read yet. The rest have a specification, a register or a deployed mechanism behind them, and the work is adoption or a choice rather than invention.`,
        'That balance is a correction. The first version of this page filed seven items under <em>nothing exists yet</em>, and a reviewer who works on these specifications pointed out that five of them had answers — some published while this was being written, some still moving through as pull requests. The items below now open by saying what the earlier draft got wrong, which is left visible on purpose: a page about unsolved problems goes stale by overstating them, and one shown correction is a cheap warning that there are probably others.',
        'What is left, once the answered items are set aside, is a short list and it is not a technical one: what a document authorises as distinct from what it attests, how three arrangements compose when no two of them share a technical body, which copy of a certificate governs, and whether anyone can undertake that an identifier still means the same organisation in thirty years. The last of those cannot be settled by evidence until something has been running for thirty years. Theories are available. Data is not.',
      ]),
    ])
  );

  for (const tier of data.tiers) {
    fragment.append(
      el('h3', { text: tier.label }),
      el('p', { class: 'muted', style: 'max-width:70ch;margin-top:-6px', text: tier.test })
    );

    for (const item of tier.items) {
      const [tone, statusLabel] = HARMONISATION_STATUS[item.status];
      const pairs = [
        ['What would have to be agreed', textParagraphs(item.requirement)],
        ['This demonstration', textParagraphs(item.demonstrated)],
        item.exists ? ['What already exists', textParagraphs(item.exists)] : null,
        // A bare URL in a field of its own, linked here rather than written into the
        // prose: every other field reaches textContent, so an anchor tag in one of them
        // would show the reader its angle brackets.
        item.source
          ? ['Where to read it', el('a', { href: item.source, text: item.source })]
          : null,
        ['If two parties answer differently', item.consequence],
        ['Who would have to agree it', item.forum],
      ].filter(Boolean);

      fragment.append(
        panel(item.title, null, [
          el('div', { style: 'margin-bottom:12px' }, [badge(tone, statusLabel)]),
          keyValues(pairs),
        ])
      );
    }
  }

  fragment.append(
    prose([
      'The steps below are dependency structure rather than advice. Each rung is possible without the ones above it, and none of the upper rungs delivers anything without the lower ones — so whoever turns out to act, this is the order the blocking relationships force.',
    ])
  );

  for (const step of data.nextSteps) {
    fragment.append(
      panel(`${step.order}. ${step.title}`, step.scope, [
        // Split on the blank line rather than passing the whole detail as one string.
        // Two steps write paragraph breaks into their text, and inside a single <p>
        // those collapse to a space -- a wall of prose that reads as a mistake nobody
        // can point at.
        prose(step.detail.split('\n\n')),
        step.unblocks.length
          ? el('p', {
              class: 'muted',
              text: `Advances: ${step.unblocks.map((key) => titleOf[key] || key).join(' · ')}`,
            })
          : null,
      ])
    );
  }

  fragment.append(
    callout([
      'Notice where the ladder stops. Every rung up to the fourth needs nobody’s permission, and the fifth needs one organisation to decide something about data it already owns. The sixth requires two arrangements to agree — and it is the one item here with no existing forum to agree it in, because the CIPM MRA and the Global ACI arrangement have no standing joint technical body. Creating somewhere for the conversation to happen is the real first step, and it is institutional rather than technical, which is usually the finding nobody wants.',
      'The seventh rung is the newest and the odd one out. Legal metrology raised two questions the other two pillars never had to ask — what a document authorises as distinct from what it attests, and what identifies a design rather than one instrument — and both sit in the first tier, because getting either wrong is not a missing feature but a wrong answer. It is also the only rung whose forum plainly exists: the OIML has a standing structure for this conversation, which is more than the sixth rung can say.',
    ])
  );

  fragment.append(
    el('p', {
      class: 'footnote',
      html:
        'Built as an exploration, not a proposal. This chapter names real organisations — the BIPM, the Global ACI arrangement, the PTB, ISO, IEC, the JCGM — because the dependencies genuinely run through them, and the ordering above is what the blocking relationships force rather than a course of action anyone has been asked to take. Nothing here reflects the position of any of them. The registers linked above are real; everything else in this demonstration remains fictional, the identifiers use the <code>.example</code> domain reserved by RFC 2606, and the signing keys are derived from a seed published in the source tree.',
    })
  );

  return fragment;
}

// ---------------------------------------------------------------- chapter 12

// What the coordinator is doing in a given exchange, which is a property of the exchange
// and not of the organisation. Verifica is an issuer here and a verifier in the same
// breath; that it can be both at once is the whole point of the last one.
const EXCHANGE_ROLE = {
  issuer: ['pass', 'issuing'],
  verifier: ['anchor', 'verifying'],
  'issuer-verifier': ['warn', 'both at once'],
};

function exchangeMessage(number, direction, title, hint, body, context) {
  const arrow = direction === 'up' ? '&uarr;' : '&darr;';
  const who = direction === 'up' ? 'holder to coordinator' : 'coordinator to holder';
  return panel(`${number}. ${title}`, hint, [
    el('p', { class: 'muted', html: `${arrow} ${who}` }),
    body === null ? el('p', { class: 'muted', text: 'Empty body.' }) : jsonView(body, context.inspect, { tall: true }),
  ]);
}

async function chapterMoving(context) {
  const fragment = document.createDocumentFragment();
  const data = await api.workflows();

  fragment.append(
    prose([
      'Every verifier you have met so far already had the document in hand. That is a comfortable place to start a chapter and nobody arrives there by accident: somebody asked, somebody answered, and both steps happened before the page opened.',
      'There are two ways to answer the question, and they disagree about almost everything. One says the document should travel — signed, self-contained, by whatever means is to hand — and that no protocol is needed for most of it. The other says the parties should talk, over an agreed protocol, so that each can ask for exactly what it needs. This world can do both, and the rest of the chapter is what each one costs.',
    ])
  );

  const stage = el('div');
  let selected = data.workflows[0];

  // aria-pressed marks the one already chosen, which the CSS colours and which
  // tools/ui-clicks.mjs skips -- a chip that selects the state it is already in has
  // nothing to change, and saying so is better than leaving the harness to call it
  // broken. It was right to: without this the first chip really did nothing.
  const chips = el(
    'div',
    { class: 'chips' },
    data.workflows.map((workflow, index) =>
      el('button', {
        class: 'chip',
        text: workflow.title,
        'aria-pressed': String(index === 0),
        onclick: (event) => {
          chips
            .querySelectorAll('.chip')
            .forEach((chip) => chip.setAttribute('aria-pressed', String(chip === event.target)));
          selected = workflow;
          show();
        },
      })
    )
  );

  fragment.append(
    el('h3', { text: 'One: the credential is a file' }),
    prose([
      'UN/CEFACT put the argument for this most sharply, and it is an argument from failure rather than from elegance. Fifty years of electronic data interchange digitised something like a tenth of cross-border trade, because a network of hubs and pipes only ever reaches the parties who joined it, and a commercial invoice is needed by the exporter, the importer, two customs authorities, banks, insurers, brokers and freight forwarders. The network never reaches all of them. So <a href="https://unvtd.unece.org/architecture/portable-credentials/">stop building the network</a>: sign the document, and let it travel with the consignment by email, file transfer, a USB drive or a QR code.',
      '<strong>This demonstration was already built that way and had not noticed.</strong> Every credential here is a signed file that verifies wherever it is found; the world dumps to 76 documents on disk and they verify from there. Chapter 10 computes the same property from the other end — the institute keeps three documents online while six of its credentials travel unhosted — and calls it a hosting burden rather than an architecture.',
      'Metrology has the oldest instance of the idea in existence, and it is not digital. <strong>A calibration certificate already travels with the instrument.</strong> The paper in the box is a portable credential: self-contained, checkable by whoever opens the box, and dependent on no service being reachable. What the cryptography adds is not the idea. It is that the copy in the box can now be checked.',
    ])
  );
  const portability = await api.portability();
  const travelling = portability.split.find((row) => row.key === 'travels') || { count: 0 };
  const signed = portability.ifRegistriesWereSigned;

  fragment.append(
    el('h3', { text: 'Two: what can travel, and what cannot' }),
    prose([
      'The interesting question is not whether the portable model works. It is where it stops, and that is measurable rather than arguable. Below, the same certificate of conformity is verified twice: once with the verifier given nothing, and once with the verifier handed every document a holder is allowed to bring. The difference is read out of the resolver&rsquo;s own retrieval log.',
    ]),
    panel('The same verification, twice', `${portability.title}`, [
      el('div', { class: 'stat-row' }, [
        stat(portability.baseline.distinct, 'documents, nothing supplied'),
        stat(travelling.count, 'a holder may bring'),
        stat(portability.stapled.stillFetched, 'still fetched'),
        stat(signed.stillFetched, 'if registries were signed'),
      ]),
      callout([
        `Both runs reach <strong>${portability.stapled.outcome}</strong>. Handing the verifier everything it is allowed to accept second-hand removes ${travelling.count} of the ${portability.baseline.distinct} retrievals and changes no verdict, which is the portable-credential claim holding up under measurement rather than in principle.`,
        `What is left is the part that is not portable. And if the registries were signed — the one removable reason below — the residue would be ${signed.stillFetched} documents of exactly two kinds: <strong>${signed.kinds.join(' and ')}</strong>. That is each organisation&rsquo;s key and its revocation list, and nothing else. It is also, to the document, the hosting burden chapter 10 computed from the opposite direction. Neither chapter knew it was describing the same quantity.`,
      ]),
    ])
  );

  for (const item of portability.classes) {
    const row = portability.split.find((entry) => entry.key === item.key) || { count: 0, hosts: [] };
    fragment.append(
      panel(item.label, `${row.count} of ${portability.baseline.distinct} documents, across ${row.hosts.length} host${row.hosts.length === 1 ? '' : 's'}`, [
        el('div', { style: 'margin-bottom:12px' }, [
          badge(item.travels ? 'pass' : 'anchor', item.travels ? 'may be brought by the holder' : 'the verifier must fetch it'),
          item.removable ? badge('warn', 'and this reason could be removed') : null,
        ]),
        keyValues([['Kinds', item.kinds.join(', ')], ['Why', item.why]]),
      ])
    );
  }

  fragment.append(
    callout([
      'The forgery in the second class is not hypothetical, and it is worth being plain that this demonstration had it. A holder could staple a DID document claiming a trust anchor&rsquo;s identifier, sign a credential in that anchor&rsquo;s name with its own key, and the pipeline reported <em>verified</em> — every check passing, because the verifier was reading the attacker&rsquo;s own account of whose key was whose. <code>vc/resolver.py</code> now refuses to take any of these kinds second-hand, and the exploit is kept as a regression test.',
    ])
  );

  fragment.append(
    el('h3', { text: 'Three: when somebody has to ask' }),
    prose([
      'Portable credentials answer distribution and say nothing about the case where the verifier does not have the document and wants it — an authority at a border, an issuing authority that needs to see evidence before it certifies anything. For that the parties do have to talk, and what follows is W3C&rsquo;s <a href="https://www.w3.org/TR/vcalm-1.0/">VCALM</a> exchange, implemented against this same world. Two properties of it do all the work.',
      '<strong>One endpoint, used twice.</strong> The holder POSTs to an exchange and is answered with a request for a presentation. It POSTs the presentation to the same URL and is answered with a result. Not two services with two protocols — one conversation with two turns.',
      '<strong>The holder starts it.</strong> There is no way for an issuer or a verifier to reach into a wallet. Every flow begins with the party holding the credentials, which is why even this arrangement survives a fifteen-person laboratory sitting behind a firewall with no inbound port.',
    ])
  );
  fragment.append(panel('Three exchanges this world can hold', 'pick one, then run it', [chips, stage]));

  async function run(replay) {
    const log = el('div');
    clear(stage).append(describe(), log);

    try {
      const opened = await api.openExchange(selected.id);
      log.append(
        exchangeMessage(
          1,
          'up',
          'The holder opens an exchange',
          `POST /workflows/${selected.id}/exchanges`,
          { workflowId: opened.workflowId, exchangeId: opened.exchangeId, url: opened.url },
          context
        )
      );

      const request = await api.exchangeTurn(selected.id, opened.exchangeId, {});
      log.append(
        exchangeMessage(
          2,
          'down',
          'The coordinator asks for a presentation',
          'the same URL, answered with a request',
          request.verifiablePresentationRequest,
          context
        ),
        callout([request.vcqi.explains])
      );

      const presented = await api.presentAs(selected.id, opened.exchangeId);
      const presentation = presented.verifiablePresentation;
      log.append(
        exchangeMessage(
          3,
          'up',
          'The holder answers',
          selected.presents.length
            ? `signed with ${selected.holderName}&rsquo;s key, carrying ${selected.presents.length} credential${selected.presents.length === 1 ? '' : 's'}`
            : `signed with ${selected.holderName}&rsquo;s key, carrying no credential at all`,
          presentation,
          context
        ),
        callout([
          `Look at the proof. Its <code>proofPurpose</code> is <code>authentication</code> rather than <code>assertionMethod</code> — the holder is not asserting the contents, which the issuers already signed, but proving it is the party that was asked. And it carries the <code>challenge</code> from the request and the <code>domain</code> of the coordinator, both signed in. That is what makes this presentation an answer to <em>this</em> exchange and no other, and it is why it could not have been prepared in advance: the challenge did not exist until step 1.`,
        ])
      );

      let target = opened.exchangeId;
      if (replay) {
        const second = await api.openExchange(selected.id);
        await api.exchangeTurn(selected.id, second.exchangeId, {});
        target = second.exchangeId;
        log.append(
          callout([
            `Now a second exchange has been opened, with its own challenge, and the presentation from the first one is about to be posted into it — which is precisely what an attacker who intercepted a presentation would try.`,
          ])
        );
      }

      const result = await api.exchangeTurn(selected.id, target, {
        verifiablePresentation: presentation,
      });
      const outcome = result.vcqi;

      log.append(
        panel(
          `4. The coordinator ${outcome.state === 'complete' ? 'answers' : 'refuses'}`,
          outcome.state === 'complete' ? 'verified, and issued where there is something to issue' : 'and nothing is issued',
          [
            el('div', { style: 'margin-bottom:12px' }, [
              badge(outcome.state === 'complete' ? 'pass' : 'fail', outcome.state),
              ...(outcome.reports || []).map((report) =>
                badge(report.outcome === 'verified' ? 'pass' : 'fail', `presented: ${report.outcome}`)
              ),
            ]),
            outcome.refused ? callout([`<strong>Refused.</strong> ${outcome.refused}`]) : null,
            result.verifiablePresentation
              ? jsonView(result.verifiablePresentation, context.inspect, { tall: true })
              : el('p', { class: 'muted', text: 'Empty body — the exchange is finished and there is nothing further to send.' }),
            callout([outcome.explains]),
          ].filter(Boolean)
        )
      );

      if ((outcome.reports || []).length) {
        log.append(
          panel(
            'What the coordinator checked before answering',
            'the same pipeline every other chapter uses, run over what the holder sent',
            outcome.reports.map((report) => stepTree(report.steps, 0))
          )
        );
      }
    } catch (error) {
      log.append(callout([`The exchange could not be completed: ${error.message}`]));
    }
  }

  function describe() {
    const [tone, label] = EXCHANGE_ROLE[selected.role];
    return panel(selected.title, null, [
      el('div', { style: 'margin-bottom:12px' }, [
        badge(tone, `${selected.coordinatorName} is ${label}`),
      ]),
      keyValues([
        ['Holder, who starts it', `${selected.holderName} (${selected.holder})`],
        ['Coordinator, who answers', `${selected.coordinatorName} (${selected.coordinator})`],
        ['What is asked for', selected.asksFor.length ? selected.asksFor.join(', ') : 'Only proof that the holder controls its identifier'],
        ['What comes back', selected.issues ? selected.issues : 'Nothing — this coordinator is checking, not issuing'],
      ]),
      callout([selected.lesson]),
      el('div', { class: 'chips' }, [
        el('button', { class: 'chip', text: 'Run the exchange', onclick: () => run(false) }),
        el('button', { class: 'chip', text: 'Replay the answer into a second exchange', onclick: () => run(true) }),
      ]),
    ]);
  }

  function show() {
    clear(stage).append(describe());
  }

  show();

  fragment.append(
    panel('What each one buys', 'and what it charges for it', [
      table(
        ['', 'The document travels', 'The parties talk'],
        [
          ['What the verifier runs', 'Nothing. It needs the file and the issuer\u2019s key.', 'An endpoint, and state for every conversation in progress.'],
          ['Works offline', 'Yes, apart from the residue above.', 'No. Both parties reachable at once.'],
          ['Reaches parties with no prior relationship', 'Yes. Anyone handed the file.', 'Only those who implement the same protocol.'],
          ['Proves who is presenting', 'No. Anyone with a copy can present it.', 'Yes. The challenge is signed into the answer.'],
          ['Carries revocation', 'No. Status is a claim about now.', 'No, and it fetches it anyway.'],
          ['Lets the verifier ask for something', 'No.', 'Yes, which is the entire point.'],
        ]
      ),
      callout([
        'The fourth row is where the two models genuinely need each other, and it is the honest limit of the portable one. A signed file proves who issued it and says nothing about who is holding it out, so <strong>anyone with a copy can present it</strong>. For a calibration certificate that is usually harmless — it is a public attestation about an instrument, and a copy is as true as the original. For a laboratory claiming its own accreditation in order to win work, a copy is enough to impersonate it. UNECE&rsquo;s own business-wallet page does not discuss holder binding, a nonce or replay at all, and that gap is exactly what the challenge in the exchange above closes.',
        `And the exchange charges for it. State means a service, a store, an expiry policy and something to attack: this is the only thing in the whole demonstration that the server has to remember between requests, and it holds at most ${data.maxExchanges} exchanges for ${Math.round(data.ttlSeconds / 60)} minutes each, evicting the oldest when it runs out of room.`,
      ]),
    ]),
    panel('Chapter 10’s claim, stated properly', 'it was right, and for a reason it did not give', [
      prose([
        'Chapter 10 says a verifier operates nothing, and an earlier version of this chapter called that an overstatement. It is not one — it is a claim about the portable model, and under that model it is true. Checking a credential you already hold is free and works on a laptop at a border post with an intermittent connection.',
        'What is true alongside it is that <em>asking</em> for a credential is not free. So the cost is a property of the architecture chosen, not of credentials: choose the portable model and a verifier really does operate nothing, at the price of never being able to ask; choose the exchange and it can ask, at the price of running something. The measurement above is what that choice actually costs in this world, and the residue — a key and a revocation list per organisation — is what neither model can avoid.',
      ]),
    ])
  );

  fragment.append(
    el('p', {
      class: 'footnote',
      html:
        'Two things here are deliberately not real. There is no authorization on these endpoints, so anyone may open any exchange and this world&rsquo;s fictional holders will present for them; a deployment puts OAuth or a capability in front, which VCALM discusses and which would teach nothing extra here. And the browser cannot hold a private key it was never given, so when it acts as the holder it asks this same server to sign on the holder&rsquo;s behalf — one process still plays every actor, exactly as it does in every other chapter. The credentials that come back are the ones the earlier chapters already showed, which is the honest thing to point out about an exchange: it is transport, and the same document arrives. What changed is that somebody had to ask for it.',
    })
  );

  return fragment;
}

// ----------------------------------------------------------------

export const CHAPTERS = [
  {
    // First deliberately: app.js falls back to CHAPTERS[0] for an empty or unknown
    // hash, so this is also the landing page. Heading text comes from
    // web/content/chapters/00-cautions.md
    //
    // `unnumbered` keeps it out of the chapter numbering rather than taking 0 from
    // orientation. ARCHITECTURE.md fixes the numbers because the prose says "chapter 5"
    // and "the next chapter" in twenty-odd places, several of them in editorial fields
    // served to the reader from actors/harmonisation.py; shifting them all to seat this
    // page at 0 would break every one of those silently.
    id: 'cautions',
    unnumbered: true,
    render: chapterCautions,
  },
  {
    // Heading text comes from web/content/chapters/01-orientation.md
    id: 'orientation',
    render: chapterOrientation,
  },
  {
    // Heading text comes from web/content/chapters/02-keys.md
    id: 'keys',
    render: chapterKeys,
  },
  {
    // Heading text comes from web/content/chapters/03-graph.md
    id: 'graph',
    render: chapterGraph,
  },
  {
    // Heading text comes from web/content/chapters/04-issuing.md
    id: 'issuing',
    render: chapterIssuing,
  },
  {
    // Heading text comes from web/content/chapters/05-verification.md
    id: 'verification',
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
    // Heading text comes from web/content/chapters/07-traceability.md
    id: 'traceability',
    render: chapterTraceability,
  },
  {
    // Heading text comes from web/content/chapters/08-dependencies.md
    id: 'dependencies',
    render: chapterDependencies,
  },
  {
    // Heading text comes from web/content/chapters/09-break.md
    id: 'break',
    render: chapterBreakIt,
  },
  {
    // Heading text comes from web/content/chapters/10-implications.md
    id: 'implications',
    render: chapterImplications,
  },
  {
    // Heading text comes from web/content/chapters/11-infrastructure.md
    id: 'infrastructure',
    render: chapterInfrastructure,
  },
  {
    id: 'harmonisation',
    title: 'What would have to be agreed',
    eyebrow: 'Harmonisation',
    lede: 'The minimum that has to be common for any of this to cross a border, what cannot be decided later however convenient that would be, and what a deployment can do without.',
    render: chapterHarmonisation,
  },
  {
    // Last, and after harmonisation on purpose. Seating it earlier would renumber
    // every chapter from 9 upward, and two dozen references to a chapter by number --
    // several of them editorial fields in actors/harmonisation.py served to the reader
    // -- would quietly become wrong. ARCHITECTURE.md records the rule.
    id: 'exchange',
    title: 'How a credential moves',
    eyebrow: 'Distribution',
    lede: 'Two architectures answer the same question and disagree about almost everything: let the document travel, or make the parties talk. Both are built here, and the cost of each is measured rather than argued.',
    render: chapterMoving,
  },
];
