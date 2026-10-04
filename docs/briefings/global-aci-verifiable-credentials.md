# Verifiable Credentials across the accreditation chain

A summary for experts of the Global Accreditation Cooperation (Global ACI), prepared by
Peter (with support from Claude) on 4 October 2026 from the VC-QI demonstrator.

It answers two questions:

1. What are the technical prerequisites for Global ACI to issue Verifiable Credentials
   to its members?
2. Could the members, in turn, issue credentials for their conformity assessment bodies
   (CABs) and for the CABs' certificates?

## What this is based on

The demonstrator builds a complete quality-infrastructure chain from W3C
Verifiable Credentials 2.0, signed with W3C Data Integrity, with `did:web` identifiers,
Bitstring Status Lists for revocation and suspension, and the W3C Recognized Entities
pattern for recognitions. It models three arrangements: the CIPM MRA, the Global ACI
arrangement and the OIML-CS. On the accreditation side the chain is:

```
Global ACI
  -> accreditation body, signatory for Calibration, Testing and Products certification
       -> calibration laboratory, testing laboratory, product certification body
            -> calibration certificate, test report, certificate of conformity
                 -> any recipient, who verifies the whole chain
```

It is a prototype. It shows what works and makes the gaps concrete enough to argue
about; it proves nothing about deployability. Every organisation, identifier and date in
it is fictional, including its stand-ins for Global ACI and the accreditation body.

Two of the building blocks are still drafts. W3C Recognized Entities is a Working Draft
that its Working Group calls experimental, and UNTP's Digital Identity Anchor, the
UN/CEFACT counterpart of a recognition, is also still in draft. Experts from both
communities are working together to align the two. Property names may therefore change;
the requirements in this summary do not depend on them.

## 1. Short answers

**Question 1: what does Global ACI need?** Very little infrastructure, and one real
governance decision.

- A stable domain, with one DID document published there. It is a static file.
- One recognition credential per signatory, stating each main scope (activity plus
  normative document, for example Calibration / ISO/IEC 17025:2017) and its date of
  signature. The accreditation body holds it and presents it; Global ACI does not host it.
  Neither draft yet has an agreed property for the main scope or for the signatory's
  registered number (section 5).
- A check, before recognising a signatory, that it really controls the DID it is
  recognised under. A recognition binds an identifier to a body only as firmly as that
  check.
- A status list, republished when a signatory is suspended.
- A signing key held at root grade: a hardware security module, split custody, a
  witnessed key ceremony, and a published rotation and compromise procedure.
- A statement on succession: what became of the ILAC and IAF identifiers, and whether
  what they signed before 1 January 2026 still verifies. When an identifier changes, the
  new one should be added as a further anchor rather than replace the old, so that
  certificates signed under the old one keep verifying.

In the demonstrator Global ACI keeps exactly two documents online. With tens of
signatories and a peer evaluation cycle measured in years, this is an archive question,
not a throughput question.

**Question 2: can members issue credentials for their CABs and certificates?** Yes. The
demonstrator does this end to end. In it, a signatory accreditation body issues:

- a recognition of each accredited CAB: who it is, for which main scope, valid when, and
  a reference to its accreditation scope;
- the accreditation scope itself as a signed credential, which the CAB's certificates
  cite and pin by content digest;
- a status list, so that a suspension takes effect at the next check without any
  certificate being recalled or reissued;
- for testing scopes with flexible rows, a query service that answers "did this scope
  cover standard X on date D" with a signed answer.

A deployment would add two things the demonstrator does not have: the accreditation
number as a structured identifier of the CAB (today it travels only as the identifier of
the scope), and a check, before the recognition is issued, that the CAB controls the DID
it is recognised under (today that is checked only when a credential is handed over).

The CABs then issue their own certificates (calibration certificates, test reports,
certificates of conformity) as credentials. A recipient checks the certificate, whether
it falls inside the scope it claims, and the recognition chain up to Global ACI, without
contacting anyone. The accreditation body does not issue the CAB's certificates, but it
is a natural candidate to hold small CABs' signing keys on their behalf.

## 2. How verification works, and why the burden is small

Two properties settle most of the infrastructure question.

- **Verification is a computation, not a conversation.** A recipient needs no account
  with the issuer, no registration and no channel back to it. Nothing an issuer runs
  grows with the number of people who check.
- **A credential travels with its holder.** A certificate reaches the verifier from the
  customer, not from the laboratory. An issuer therefore keeps online only what
  describes itself: its key (DID document) and its status list. The certificates need not
  be hosted at all.

There is one exception, and it falls on accreditation bodies. A testing scope can cover
hundreds of standards, list them as sets of equivalent names, and mark rows as flexible,
covering editions that did not exist when the scope was granted. What such a scope covers
has to be worked out rather than looked up, and only the granting body may do that. That
body therefore runs a service whose load rises with the number of verifications.

A main scope has to be recorded as a pair. Testing and Calibration rest on the same
ISO/IEC 17025, so a credential that listed only standards could not say which of the two a
body is a signatory for.

## 3. What each role would run

| Role | Already runs | Must add | Key custody | Hardest part |
|---|---|---|---|---|
| Global ACI | Stable domain; peer evaluation inherited from ILAC and IAF; the published signatory list, which is what gets signed | HSM and key ceremony; status list; a check that each signatory controls its DID; succession statement for the ILAC and IAF identifiers | Root grade | Succession, not custody: an accreditation granted in 2025 was granted by an organisation that no longer exists |
| Member accreditation body | Register of CABs and scopes; assessment process, including the dates a row enters and leaves a scope | A check that each CAB controls its DID; signatures over the scopes; a query service returning signed, dated answers; retention of row history; status list | Service grade, and the key must be online to sign answers | Undertaking to still answer years later |
| CAB (for example a 15-person laboratory) | Website; software that produces PDF certificates | A `did.json` at a well-known path; an arrangement with whoever holds the key; a route from its software to a signing service, usually a supplier update | Delegated, to the accreditation body or a trust service provider. `did:web` keeps the CAB's own name in the identifier | Never asking the laboratory to understand any of it |
| Verifier (authority, purchaser, customs) | Whatever it inspects with today | A verifier library; a trust list of the anchors it accepts; a policy for what a failed check means | None | Getting anyone to run it |

Capacity is not a consideration anywhere: a P-256 signature takes well under a
millisecond.

## 4. What is genuinely new

- **Key custody is the whole problem.** Who controls a key and what happens when it is
  compromised is a governance question wearing a technical costume. Buying hardware does
  not answer it.
- **Long-term validation has a deadline.** Certificates are kept for decades; a
  signature is comfortable for perhaps fifteen years. Signatures must carry a trusted
  timestamp (RFC 3161) from the day of issue. Almost everything else can be retrofitted;
  this cannot.
- **A new way to fail.** An unreachable DID document means unverifiable certificates,
  and for an anchor such as Global ACI that is a worldwide outage. Static files behind a
  CDN with a long cache lifetime make it manageable, but it is a dependency paper does not
  have.
- **A service fails worse than a file.** Documents can be cached, mirrored and archived
  by anyone holding a copy. An unsigned answer from a register cannot, so certificates
  that depended on it stop being verifiable once the register is gone. Signing the answers
  turns this back into an archiving problem. It is the cheapest decision in the whole
  design, and few registers make it today.

## 5. What would have to be agreed between organisations

An item is listed only if two conforming implementations that differ on it cannot
interoperate. Of the 24 such items the demonstrator identifies, 10 have nothing to build
on yet; the rest have a specification, register or deployed mechanism behind them, and
the work is adoption or a choice. Two more, marked *new*, came from a later review of the
recognition model and are not yet in the demonstrator.

**Where Global ACI is the natural forum** (it already sets the scope-publication rules):

| Item | Status | What is needed |
|---|---|---|
| Where a recognition says what it is recognised for (*new*) | Open | The W3C draft says what a recognised body may *do* (an action), not what it is recognised *for*: main scope, accreditation scope, standards. The demonstrator had to invent a property for the main scope, and UNTP's draft proposes its own. Each entry should point at the body's published scope, pinned by digest so it cannot be swapped silently, and that scope must be machine-readable or the checks cannot run. No link in the chain should grant more scope than it holds. For the quality infrastructure this is the most important gap in the recognition model |
| A structured registered identifier (*new*) | Partial | The accreditation number as a value plus the scheme that issued it, since a number is unique only within its scheme. UNTP's draft requires one; the W3C draft has no member for it, so without agreement each ecosystem names it differently |
| How a scope says what it covers | Open | A grammar for the coverage column. One real calibration scope already uses three: fixed values, an interval with a strict upper bound, and a nominal with a tolerance |
| How to ask a register what a scope covered | Open | A protocol with the date as a parameter, a signed reply, and a reply that repeats the question. The demonstrator had to invent one |
| What a status value means | Partial | Bitstring Status List (W3C Recommendation, May 2025) can carry a message per value and a reference to the governing rule. Who may suspend, and what that means for certificates already issued, is policy |
| The unit of suspension | Open | One credential per recognised entity rather than a roster; with a roster, suspending one body suspends all |
| Whether a recognition can be asked about in the past | Open | "Was this body a signatory for this main scope on the date of calibration?" Status lists describe the present only. Dated snapshots, short-lived recognitions or an event log: one answer is needed |
| How long an identifier keeps its meaning | Partial | `did:webvh` covers renaming and moving; dissolution needs someone to undertake to inherit the obligation |
| How verifiers learn the anchors | Partial | Signed trusted lists exist (ETSI TS 119 612, run at scale under eIDAS). Who operates and signs the list is open |

**Jointly with the CIPM MRA and the OIML:**

- **How a chain crosses arrangements** (open). A certificate of conformity rests on an
  accreditation under Global ACI and on calibrations traceable under the CIPM MRA.
  Someone has to say how a verifier composes the two, and the arrangements have no
  standing joint technical body.
- **What a verdict is good enough for** (open). A border authority and a purchaser need
  different rules, and relying parties have no seat in any arrangement.

**Common technical floor, a choice rather than an invention:** one cryptosuite (W3C Data
Integrity); one identifier method (`did:webvh`, which the Swiss federal e-ID already runs
on); one protocol for requesting a credential (W3C VCALM, or OpenID4VP as used by the EU
Digital Identity Wallet); unit identifiers from the BIPM's SI Digital Framework, and
measurand identifiers from the ISO and IEC work under way; and a certificate format. For
the format, the PTB/DKD Digital Calibration Certificate is mature but national, and the
UN/CEFACT Digital Conformity Credential (UNTP) has international standing but does not
carry measurement uncertainty. UNTP 0.7.0 already has a code, `authority-globalmra`, for
accreditation under the Global ACI arrangement. For the recognitions themselves, the W3C
and UNTP drafts are being aligned, and Global ACI gains more from contributing to that
alignment than from choosing one side early.

## 6. Suggested first steps for Global ACI

Each step is possible without the ones after it.

1. Decide who controls Global ACI's identifier and key. Publish it as a `did:webvh` log
   rather than a static `did.json`: same path, no extra cost on day one, and the
   difference between being able to rotate a key in ten years and not. State what became
   of the ILAC and IAF identifiers.
2. Issue each signatory's recognition as its own credential, with its main scopes, dates
   and registered number, after checking that it controls its DID, and a status list that
   states what suspension means. Timestamp from the first
   day, and keep a log of recognition events so that "was it recognised then" can be
   answered later. A log not kept from the start cannot be reconstructed.
3. Pilot with one or two member accreditation bodies: signed scopes alongside the
   existing publication, delegated signing for a few CABs, and cross-verification
   between two bodies with every disagreement written down.
4. Extend the existing scope-publication rules to a machine-readable scope grammar and a
   dated, signed query protocol. The same body, one layer out.
5. Open a joint technical conversation with the CIPM MRA, and the OIML, on how the
   chains compose. This is the one step with no existing forum, and it is institutional
   rather than technical.
6. Align the choices with eIDAS 2.0 and the EU Digital Identity Wallet, and with UNTP's
   Digital Conformity Credential and Digital Identity Anchor, rather than running beside
   them. Bringing the accreditation use case into the ongoing W3C and UNTP alignment of
   the recognition model is the most direct way to get a standard home for the scope and
   the registered number.

## 7. Open questions

- **Who verifies in practice?** The benefit exists only if checking happens where it
  does not happen today.
- **What does a failed check mean institutionally?** Software can say a certificate is
  outside a published scope; it cannot say whether that is an error, a typo, or a scope
  updated last week and not yet published.
- **Which copy governs**, the existing certificate or the credential? For a long time
  both will exist, and that is a legal question.
- **Confidentiality.** A CAB may need to prove its equipment is traceable and in scope
  without disclosing a customer's certificate. Selective disclosure (SD-JWT, BBS) is not
  implemented in the demonstrator.
- **Is a chain of recognitions better than each arrangement publishing one signed
  list?** For a hierarchy this shallow, possibly not, and that should be argued rather
  than assumed.

## Sources

In the demonstrator: the chapters "What it would take to run" (deployment), "What this
would mean in practice" and "What would have to be agreed" (harmonisation).

- W3C Verifiable Credentials Data Model 2.0: https://www.w3.org/TR/vc-data-model-2.0/
- W3C Data Integrity: https://www.w3.org/TR/vc-data-integrity/
- W3C Bitstring Status List: https://www.w3.org/TR/vc-bitstring-status-list/
- W3C Recognized Entities: https://www.w3.org/TR/vc-recognized-entities-1.0/
- W3C VCALM: https://www.w3.org/TR/vcalm-1.0/
- did:webvh: https://identity.foundation/didwebvh/next/
- ETSI TS 119 612 (trusted lists): https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/
- RFC 3161 (time-stamp protocol): https://www.rfc-editor.org/rfc/rfc3161
- UNTP Digital Conformity Credential: https://untp.unece.org/docs/specification/ConformityCredential/
- BIPM SI Digital Framework: https://si-digital-framework.org/SI?lang=en
