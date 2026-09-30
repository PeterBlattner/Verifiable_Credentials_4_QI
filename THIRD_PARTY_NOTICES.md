# Third-Party Notices

This repository includes or references material developed by third parties.
Such material remains subject to its respective licence terms.

## UN Transparency Protocol — Digital Conformity Credential and Digital Identity Anchor schemas, and JSON-LD context

Files:

`src/vcqi/vendor/untp/untp-dcc-schema-0.7.0.json`  
`src/vcqi/vendor/untp/untp-dia-schema-0.7.0.json`  
`src/vcqi/vendor/untp/untp-context-0.7.0.jsonld`

Source:

UN/CEFACT — United Nations Transparency Protocol (UNTP), version 0.7.0, released on
4 May 2026. Taken from the UNTP specification repository at tag `v0.7.0`
(`https://opensource.unicc.org/un/unece/uncefact/spec-untp`):

- `artefacts/schema/v0.7.0/dcc/ConformityCredential.json`, published at
  `https://untp.unece.org/artefacts/schema/v0.7.0/dcc/ConformityCredential.json`
- `artefacts/contexts/v0.7.0/untp-context.jsonld`, published at
  `https://vocabulary.uncefact.org/untp/0.7.0/context/`
- `artefacts/schema/v0.7.0/dia/DigitalIdentityAnchor.json`, published at
  `https://untp.unece.org/artefacts/schema/v0.7.0/dia/DigitalIdentityAnchor.json`. The
  specification repository could not be reached when this was vendored, so the copy was
  taken from the UNTP Playground's bundle (`https://github.com/uncefact/tests-untp`,
  `packages/untp-utils/artefacts/schema/untp/0.7.0/dia.json`). Its content hash equals the
  one the Playground's manifest records for that tag.

These are the copies the UNTP Playground bundles. The copy of the DCC schema served at
`untp.unece.org` differs from the tag in two `example` strings. Content hashes (SHA-256 of
the JSON with keys sorted and no whitespace, as the Playground's artefact manifest computes
them): DCC schema `10869cc870bdf9e1d499c46a319c78fcdae7b1a4f37d837a84d34a4aaffb0883`, DIA
schema `0f125c2e8c6f0b01c79c7bf05ece2e33a88982edf023ee90479454b60b6b5eea`, context
`3c0f6d7e6fdd4e54fc167c98a8ae232739c582fab845522bf81e7c67c881714f`.

Licence:

Creative Commons Attribution 4.0 International (CC BY 4.0)

Copyright / attribution:

United Nations Economic Commission for Europe (UNECE) / UN/CEFACT

The UNTP specification site states that UN/CEFACT standards are free to use under the
Creative Commons Attribution 4.0 International licence.

No endorsement by UNECE or UN/CEFACT of this project is implied.

## W3C Verifiable Credentials Data Model v2.0 — JSON-LD context

File:

`src/vcqi/vendor/w3c/credentials-v2.jsonld`

Source:

`https://www.w3.org/ns/credentials/v2`, the context of the W3C Recommendation *Verifiable
Credentials Data Model v2.0*. Vendored only so that the offline check in
`src/vcqi/vc/jsonld_terms.py` can expand a projected credential without a network. Content
hash, computed as above: `b463c8d6a066214123ddd9827b135e1b50e1fc73322cc52a9b12a4f1fc7d86cf`.

Licence:

W3C Software and Document License,
`https://www.w3.org/copyright/software-license-2023/`

Copyright / attribution:

Copyright © World Wide Web Consortium. No endorsement by the W3C of this project is
implied.

## W3C VC Data Integrity ECDSA Cryptosuites — ecdsa-jcs-2019 test vectors

Files:

`tests/vectors/w3c-vc-di-ecdsa/p256KeyPair.json`  
`tests/vectors/w3c-vc-di-ecdsa/unsigned.json`  
`tests/vectors/w3c-vc-di-ecdsa/ecdsa-jcs-2019-p256/` (nine files)

Source:

The test vectors of the W3C Recommendation *Verifiable Credential Data Integrity ECDSA
Cryptosuites v1.0* (15 May 2025), Appendix A.5, "Representation: ecdsa-jcs-2019 with
curve P-256", taken unchanged from the specification repository
`https://github.com/w3c/vc-di-ecdsa`, directory `TestVectors/`, at commit
`59df72ca8cdb275d97eb496086fea6fac4fa7f0f`. Used only by `tests/test_w3c_vectors.py`.

Licence:

W3C Software and Document License,
`https://www.w3.org/Consortium/Legal/2015/copyright-software-and-document`

Copyright / attribution:

Copyright © World Wide Web Consortium and the contributors to the specification. No
endorsement by the W3C of this project is implied.
