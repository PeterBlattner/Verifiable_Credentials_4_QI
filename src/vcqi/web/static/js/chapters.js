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
          ['Root of trust', 'BIPM under the CIPM MRA; Global ACI under the Global ACI MRA'],
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

const ISSUE_MODES = [
  { key: 'honest', label: 'Sign as yourself' },
  { key: 'impersonate', label: 'Claim to be METAS' },
  { key: 'steal-key-id', label: 'Claim METAS and its key id' },
];

async function chapterKeys(context) {
  const fragment = document.createDocumentFragment();
  const state = { key: null };

  fragment.append(
    prose([
      'The previous chapter said a credential is a document signed with a key that its issuer publishes. That sentence carries the whole idea, and it is worth slowing down on, because everything after it depends on what a key actually is.',
      'A <strong>private key</strong> is a number. Not a file, not a password: a number, about 78 digits long. A <strong>public key</strong> is a second value computed from the first. The computation goes one way only, which is the entire trick and the reason the second one can be published.',
    ])
  );

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
              el('strong', { text: 'Exactly the same key came back' }),
              el('span', {
                text:
                  'Which is the whole problem with deriving a key from words. Nothing about this key is unpredictable: anyone who tries the same passphrase gets the same private key, and it is the private key that is supposed to be the secret. Change a character, or ask for a random one, and watch it move.',
              }),
            ]),
          ])
        : null,
      el('div', { class: 'callout' }, el('p', { text: data.note })),
      el('h3', { text: 'Your private key' }),
      el('pre', { class: 'code', text: wrap(data.privateScalarHex, 64) }),
      el('p', {
        class: 'muted',
        text: `That is the whole secret: one number, 32 bytes, ${data.privateScalarDecimalDigits} digits in decimal. Anyone who has it can sign anything at all in your name.`,
      }),
      el('h3', { text: 'The public key, computed from it' }),
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
      prose([
        `That multiplication is a few hundred point additions on the ${data.curve.name} curve and takes well under a millisecond. Going the other way — recovering <em>d</em> from the point — is the elliptic curve discrete logarithm problem, and after forty years of trying, nobody knows how to do it. That asymmetry is the only reason the right-hand value can be published at all.`,
      ]),
      panel(
        'From a point to publicKeyMultibase',
        'four ordinary encodings stacked up, none of them cryptography',
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
      prose([
        'Notice what that identifier is. A <code>did:key</code> <em>contains</em> the public key, so a verifier needs to fetch nothing at all to check a signature made with it. Compare <code>did:web:metas.example</code>, which has to be resolved to a document before you learn anything. The trade is that a <code>did:key</code> can never rotate its key, cannot carry a name or a website, and cannot be the subject of a recognition credential — you would be recognising a key rather than an organisation.',
      ])
    );
  }

  fragment.append(
    panel('Make a keypair', 'nothing here is secret; see the warning below', [
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
    callout([
      'Press <strong>Derive</strong> twice with the same words and you get the same key every time. Press <strong>random</strong> twice and you get two different keys. That contrast is the point: a real private key is chosen at random from about 2<sup>256</sup> possibilities, and one derived from words you can remember is one an attacker can guess.',
      'And to be explicit about what you are looking at: this page shows you a private key and sends it back and forth over HTTP. Every key in this demonstration comes from a seed published in the source and protects nothing. A real private key is generated on the device that will use it and never leaves it.',
    ])
  );

  // ---- 2. which half does what ------------------------------------------------
  fragment.append(
    el('h3', { text: 'Which half does what' }),
    prose([
      'This is where most of the confusion lives, and it comes from encryption. In encryption the <em>public</em> key encrypts and the <em>private</em> key decrypts, so people reasonably assume signing works the same way round. It does not.',
    ]),
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
    callout([
      'So a verifiable credential is <strong>not secret</strong>. A calibration certificate signed this way is as readable as one on paper. The signature does not hide anything; it says who wrote it and that nobody has changed it since. If you also need it kept confidential, that is a separate mechanism on top.',
    ])
  );

  // ---- 3. sign, then break it -------------------------------------------------
  const message = el('input', { type: 'text', value: 'The 10 kilohm standard reads 10000.0012 ohm.', style: 'min-width: 380px' });
  const signOutput = el('div', {});

  async function signAndBreak() {
    if (!state.key) {
      clear(signOutput).append(el('p', { class: 'muted', text: 'Make a keypair above first.' }));
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
    panel('Sign something, then break it four ways', 'a signature is never valid on its own, only for one message and one key', [
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
      clear(issueOutput).append(el('p', { class: 'muted', text: 'Make a keypair above first.' }));
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
      panel('Every check the verifier ran', 'the same pipeline every other chapter uses', stepTree(data.report.steps, 0)),
      panel('The credential you just signed', null, jsonView(data.credential, context.inspect, { tall: true }))
    );
    issueOutput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  fragment.append(
    el('h3', { text: 'Anyone can sign. That is the point, and the problem.' }),
    prose([
      'Nothing stopped you making that key, and nothing stops you signing a calibration certificate with it right now. The mathematics does not know or care who you are. So try it: take the real METAS certificate from this demonstration, sign it with your own key, and put it through the same verification pipeline every other chapter uses.',
      'Three ways to try, and all three fail — for three <em>different</em> reasons, which is what makes this worth doing rather than reading.',
    ]),
    panel('Sign a real calibration certificate with your key', null, [
      el(
        'div',
        { class: 'chips' },
        ISSUE_MODES.map((mode) =>
          el('button', { class: 'chip', text: mode.label, onclick: () => attempt(mode.key) })
        )
      ),
      issueOutput,
    ]),
    callout([
      'The second attempt is the one to think about. Claiming to be METAS while naming your own key <strong>passes</strong> the recognition check, because recognition asks whether the issuer the credential <em>names</em> is recognised — and METAS genuinely is. Only the proof check binds that claim to a key, and only then does the forgery come apart.',
      'Two checks, two different questions. A forgery would sail straight through either one on its own, which is why the pipeline runs both and why a valid signature, by itself, settles almost nothing.',
    ])
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
      prose([
        'And crucially, the verifier takes the key from <strong>the controller the credential names</strong>, never from the credential itself. A document that carried its own public key would prove only that whoever wrote it owned a key — which is precisely the second attempt above.',
        'The document also says what each key may be <em>used</em> for. A key listed under <code>authentication</code> is for proving you are present, logging in; one listed under <code>assertionMethod</code> is for making statements that outlive the conversation. The pipeline refuses a credential signed with a key its controller published only for authentication, and that is not pedantry: a key used to log in is exposed far more often than one kept for issuing.',
      ]),
      jsonView(actor.didDocument, context.inspect)
    );
  }

  fragment.append(
    el('h3', { text: 'How the verifier gets the right key' }),
    panel('Follow it from the proof back to the published key', null, [
      el('button', { class: 'action', text: 'Follow the chain for METAS-2026-0417', onclick: followChain }),
      chainOutput,
    ])
  );

  // ---- and what happens when it leaks -----------------------------------------
  fragment.append(
    el('h3', { text: 'And the day it leaks' }),
    prose([
      'If a private key gets out, everything it ever signed becomes questionable, because there is no longer any way to tell what the holder signed from what the thief signed. Anyone can issue in that name, backdated, indefinitely.',
      'That is what revocation lists, key rotation and validity periods are really for, and why an identifier that can publish a <em>new</em> key without becoming a different party matters more than it first appears. It is also why <code>ARCHITECTURE.md</code> lists key management and long-term validation among the things a real deployment would have to solve that this demonstration does not.',
    ]),
    el('p', {
      class: 'footnote',
      text:
        'Every key here is derived from a seed published in this repository, including the one you just made. They exist to be looked at, not to protect anything.',
    })
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
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'Ten organisations, and one supply chain running through them. A national metrology institute calibrates a laboratory&rsquo;s transfer standard; the laboratory calibrates a testing laboratory&rsquo;s multimeter; the testing laboratory measures a kettle; a certification body certifies the kettle; the manufacturer presents that certificate at a border.',
      'One of the two anchors is new. On 1 January 2026 the IAF and ILAC consolidated into a single body, <strong>Global Accreditation Cooperation Incorporated</strong>, whose arrangement is the Global ACI Multilateral Recognition Arrangement. Worth pausing on, because it is exactly the event a real deployment has to survive: a trust anchor changing its name, and with it the identifier every credential beneath it points at. Everything a verifier had configured would need to follow.',
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

// ---------------------------------------------------------------- chapter 3

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

// ---------------------------------------------------------------- chapter 4

async function chapterVerification(context) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    prose([
      'This is the demonstration proper. A market surveillance authority in an importing country receives a certificate of conformity. It has no relationship with the certification body, the testing laboratory, the calibration laboratory or the institute. It trusts two identifiers in the world: the BIPM and Global ACI.',
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

// ---------------------------------------------------------------- chapter 5

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

// ---------------------------------------------------------------- chapter 6

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
    'One measurement, three ways of handing it over',
    certificateName === 'metas-calibration' ? 'Certificate METAS-2026-0417' : certificateName,
    [bar, body]
  );
}


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

  fragment.append(await representationPanel(context, 'metas-calibration'));

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

// ---------------------------------------------------------------- chapter 7

const OPERATIONS = [
  { key: 'difference', label: 'R1 − R2', hint: 'checking two standards against each other' },
  { key: 'ratio', label: 'R1 / R2', hint: 'a resistance ratio' },
  { key: 'mean', label: '(R1 + R2) / 2', hint: 'averaging two check standards' },
];

async function chapterDependencies(context) {
  const fragment = document.createDocumentFragment();

  fragment.append(
    prose([
      'One institute, one national standard, two certificates. Both check standards were compared against the same 10 kΩ national standard, so a large part of what is uncertain about each result is <em>the same thing</em> being uncertain twice.',
      'A customer who combines the two ought to get the benefit of that. Whether they can depends entirely on what the institute transmitted, and the choice was made when the certificate was written, not when the customer opened it.',
    ])
  );

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
        panel('With the dependencies transmitted', 'the shared influence is recognised and cancels correctly', [
          el('div', { class: 'stat__value', text: data.tracked.reported }),
          el('p', { class: 'muted', text: data.tracked.basis }),
        ]),
        panel('From the printed value and U alone', 'the shared influence is invisible, so it is counted twice', [
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
              ? 'Note the direction. For a mean, positive correlation makes the result less certain, not more, so ignoring it is optimistic rather than cautious. Classical reporting is not conservative; it is simply wrong by an amount nobody can compute.'
              : `The two results are correlated at r = ${data.correlation.toFixed(3)} because they share ${data.sharedInfluences.length} input quantities. That correlation is recoverable from the dependency representations and from nothing else.`,
          }),
        ]),
      ]),
      panel(
        'The influences the two certificates have in common',
        'matched by identifier, not by name — two laboratories using the same wording are still different influences',
        table(
          ['Identifier', 'Influence'],
          data.sharedInfluences.map((influence) => [
            el('span', { class: 'hash', text: influence.id }),
            influence.description,
          ])
        )
      ),
      panel('The two certificates', null, table(
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
    panel('What would you like to compute from the two certificates?', null, picker),
    output,
    callout([
      'It is worth being clear about what the customer did wrong in the right-hand column: <strong>nothing</strong>. Combining in quadrature is the correct thing to do with two numbers that you have no reason to believe are related. The information that they were related existed, at the laboratory, and was not sent.',
      'This is also the honest cost of the idea. A dependency representation exposes the structure of an uncertainty budget, and many laboratories regard that as commercially confidential. Selective disclosure is where that tension would be addressed, and it is not implemented here.',
    ])
  );

  await run();
  return fragment;
}

// ---------------------------------------------------------------- chapter 8

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

// ---------------------------------------------------------------- chapter 9

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
    id: 'keys',
    title: 'Keys: what a signature actually proves',
    eyebrow: 'The idea underneath',
    lede: 'A private key is a number, a public key is computed from it, and the computation goes one way only. Make a keypair, sign something, and watch what a signature does and does not settle.',
    render: chapterKeys,
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
    id: 'dependencies',
    title: 'Why the dependencies matter',
    eyebrow: 'The argument for transmitting them',
    lede: 'Two certificates from one institute, resting on one national standard. What a customer can do with them depends on what was sent.',
    render: chapterDependencies,
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
