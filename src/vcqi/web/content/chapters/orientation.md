<!-- orientation.md -- rendered by chapterOrientation() in ../../static/js/chapters.js.
     To send a reader to another chapter, write [chapter](#scope), or [Chapter](#scope)
     to start a sentence: the page shows the number the rail gives it.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The ```json blocks are shown coloured, like every other credential on the site,
     and a test checks that each one still parses after an edit. -->

<!-- block: title -->

What a verifiable credential is

<!-- block: eyebrow -->

Start here

<!-- block: lede -->

Written for someone who has not met verifiable credentials before, and who does know what a calibration certificate is.

<!-- block: what-it-is -->

A **verifiable credential** is a document with a digital signature over it, made with a key that its issuer publishes at a stable identifier. That is nearly the whole idea. Anyone who receives the document can check the signature without contacting the issuer, without an account, and without a prior relationship.

Three parties appear in every description of it. The **issuer** makes the document. The **holder** keeps it and presents it when needed. The **verifier** receives it and decides whether to believe it. In this domain those are usually a calibration laboratory, its customer, and whoever the customer has to satisfy.

<!-- block: json-ld -->

### How a credential is written down

The W3C data model writes a credential as JSON: named members, nested objects, lists. What makes it **JSON-LD** is the first member, `@context`. It is a list of addresses, each pointing to a document that says what the short names mean. There, `validFrom` is defined as `https://www.w3.org/2018/credentials#validFrom`, holding a date and a time. Two issuers who have never spoken to each other therefore mean the same thing by it, and neither had to register anything to get there.

The first entry is always `https://www.w3.org/ns/credentials/v2`, which defines the members every credential shares. Later entries add the vocabulary of a particular domain: a degree, a driving licence, a calibration. The same idea runs through the values. An `id` is a web address or a decentralised identifier, a **DID**, which can be looked up to learn more. A `type` names a class that a context defines, and every credential is at least a `VerifiableCredential`.

Read this way, a credential is less a form than a set of statements: this issuer says that this subject has this property, with this value. Statements about the same identifier can be joined across documents from different issuers, which is what lets a verifier follow a reference out of one credential and into another. A verifier that only reads plain JSON can still process one, provided it first checks that the `@context` list is one it recognises; the data model allows exactly that.

<!-- block: example-vc.title -->

An everyday credential: a university degree

<!-- block: example-vc.hint -->

What a graduate would keep in a wallet app, with the signature shortened

<!-- block: example-vc.body -->

Alex has finished a bachelor's degree, and the university issues it as a credential, instead of a sheet of paper or alongside one. Nothing in it is specific to metrology. A calibration certificate has the same skeleton with different contents.

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://www.w3.org/ns/credentials/examples/v2"
  ],
  "id": "https://university.example/degrees/2026/4711",
  "type": ["VerifiableCredential", "ExampleDegreeCredential"],
  "issuer": {
    "id": "did:web:university.example",
    "name": "Example State University"
  },
  "validFrom": "2026-06-30T00:00:00Z",
  "credentialSubject": {
    "id": "did:example:alex-7f3c",
    "name": "Alex Example",
    "degree": {
      "type": "ExampleBachelorDegree",
      "name": "Bachelor of Science in Computer Science"
    }
  },
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "ecdsa-rdfc-2019",
    "created": "2026-06-30T09:00:00Z",
    "verificationMethod": "did:web:university.example#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "z3FXQjecWufY46yg5abdVZsXqLhxhueu…"
  }
}
```

<!-- block: example-vc.reading -->

| Member | What it says |
| --- | --- |
| `@context` | The vocabularies in use. The second is the W3C's catch-all for examples: it turns any name it does not know, such as `degree`, into an address under `https://www.w3.org/ns/credentials/examples#`. A real university would point to a published vocabulary for degrees instead. |
| `id` | Where the credential itself can be found or referred to. Optional, but anything that wants to point at this degree needs it. |
| `type` | What kind of credential this is. `VerifiableCredential` always comes first, and the second type says which rules apply to everything else. |
| `issuer` | Who makes the claim. `did:web:university.example` resolves to `https://university.example/.well-known/did.json`, which is where the university publishes the public key that checks the signature. |
| `validFrom` | When the claim starts to hold. A degree does not lapse, so there is no `validUntil`; a driving licence or a calibration would carry one. |
| `credentialSubject` | Who the claims are about, and the claims themselves. The `id` here is Alex's own identifier, which later lets Alex show that the degree is theirs. |
| `proof` | The signature: which key made it (`verificationMethod`), for what purpose, when, and how the document was turned into bytes before signing (`cryptosuite`). |
| `credentialStatus` | Absent here. It would point into a list the university maintains, so that a verifier can learn a degree was withdrawn, even though the signature on every copy still checks out. |

<!-- block: securing -->

### How the signature is attached

There are two ways. An **embedded** proof, the W3C Data Integrity family, adds a `proof` member to the document and leaves everything else as readable JSON, which is what the example shows. An **enveloping** proof wraps the whole document instead, as the payload of a JSON Web Signature or a COSE message, or as an SD-JWT, which also lets the holder disclose some claims and withhold the rest. Both are W3C Recommendations, as Verifiable Credential Data Integrity and as VC-JOSE-COSE, and they protect the same claims in different packaging.

A signature is made over bytes, and one JSON document can be written as many different sequences of bytes. So before signing, the document is put into one agreed form, and `cryptosuite` names which. `ecdsa-rdfc-2019`, the one in the example, first expands the JSON-LD into the statements it stands for and puts those into a canonical order. The signature then survives any rewriting that leaves the statements unchanged, but the verifier has to fetch, or already hold, every context the document names. `ecdsa-jcs-2019` puts the JSON text itself into canonical form, following RFC 8785, and needs no JSON-LD processing at all. [Chapter](#issuing) walks through that step byte by byte.

<!-- block: json-ld-here -->

**What this demonstration does differently.** Every credential here is signed with `ecdsa-jcs-2019`, so that [chapter](#issuing) can show exactly which bytes are hashed; canonicalising the statements is correct, and impossible to display in a way that teaches anything.

The price is that the second context each credential names, `https://vcqi.example/contexts/v1`, is fictional and never fetched. Its metrology terms are labels, not definitions. A deployment would publish that context at a stable address, and would most likely sign with `ecdsa-rdfc-2019`.

<!-- block: the-gap-signatures-leave -->

Signatures alone answer only one question: has this document been altered since it was made. They leave the harder question untouched, which is whether the party who made it had any standing to. A perfectly valid signature by an organisation nobody has heard of proves only that the organisation exists. An employer handed Alex's degree learns that Example State University signed it, and nothing about whether anyone recognises Example State University as a university.

That is the gap the W3C **Recognized Entities** specification addresses. A recognising authority issues a credential listing the entities it recognises and what each is recognised to do. A document carries a pointer to the list it claims to appear in, and a verifier follows those pointers upward until it reaches an identifier it already trusts.

<!-- block: example-re.title -->

Who says the university is a university

<!-- block: example-re.hint -->

The same degree, the list it points into, and the walk an employer's software makes

<!-- block: example-re.body -->

In most countries a ministry or an accreditation agency decides which institutions may award degrees, and publishes the answer as a list on a web page. Under Recognized Entities the list is itself a credential, signed by that authority, and the degree's issuer says where to look for it:

```json
{
  "issuer": {
    "id": "did:web:university.example",
    "type": "RecognizedIssuer",
    "name": "Example State University",
    "recognizedIn": {
      "id": "https://education.state.example/lists/recognized-universities.json",
      "type": "RecognizedEntityCredential",
      "name": "State list of recognised universities"
    }
  }
}
```

The list at that address names each recognised institution and what it is recognised to do. Here the university may issue bachelor's degrees and the community college only associate degrees. Each recognition names the schema a degree must satisfy, pinned by its digest. Signatures and digests are shortened.

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://www.w3.org/ns/credentials/examples/v2"
  ],
  "id": "https://education.state.example/lists/recognized-universities.json",
  "type": ["VerifiableCredential", "RecognizedEntityCredential"],
  "name": "State list of recognised universities",
  "issuer": {
    "id": "did:web:education.state.example",
    "type": "RecognizedIssuer",
    "name": "State Department of Education"
  },
  "validFrom": "2026-01-01T00:00:00Z",
  "validUntil": "2027-01-01T00:00:00Z",
  "credentialSubject": [
    {
      "id": "did:web:university.example",
      "type": "RecognizedEntity",
      "name": "Example State University",
      "recognizedTo": {
        "type": "RecognizedAction",
        "action": "issue",
        "recognizedBy": "did:web:education.state.example",
        "outputValidation": {
          "id": "https://education.state.example/schemas/bachelor-degree.json",
          "type": "JsonSchema",
          "digestMultibase": "uEiBZl963sknNAHgPyslVv6V…"
        }
      }
    },
    {
      "id": "did:web:college.example",
      "type": "RecognizedEntity",
      "name": "Exemplar Community College",
      "recognizedTo": {
        "type": "RecognizedAction",
        "action": "issue",
        "recognizedBy": "did:web:education.state.example",
        "outputValidation": {
          "id": "https://education.state.example/schemas/associate-degree.json",
          "type": "JsonSchema",
          "digestMultibase": "uEiWQoRvpfWW1htfsknNAHgP…"
        }
      }
    }
  ],
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "ecdsa-rdfc-2019",
    "created": "2026-01-01T08:00:00Z",
    "verificationMethod": "did:web:education.state.example#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "z4oJ2mTzq8wKcRbX7sLpNvE3hYdGfA…"
  }
}
```

The employer's software checks the degree's signature as it would any other, and then follows the specification's discovery algorithm, section 4.1, in outline:

<!-- block: example-re.walk -->

1. **Check the degree's own signature**, with the key the university publishes at `did:web:university.example`. It holds, so the degree is exactly what the university signed. But the university is not an identifier the employer trusts.
2. **Follow `recognizedIn`** on the issuer, and fetch the list it names.
3. **Check the list**: its signature, with the education department's key, and that today falls between its `validFrom` and its `validUntil`.
4. **Find the university in it**: an entry in `credentialSubject` whose `id` is the degree's issuer.
5. **Stop at a trusted identifier.** The list was issued by `did:web:education.state.example`, which the employer already trusts, so the walk ends there. Had it not been, the department would carry a `recognizedIn` of its own, and the walk would go one level higher.

<!-- block: example-re.closing -->

That establishes that the university is on the list. It does not by itself say what for. The list does say, in `recognizedTo`: the action, and the schema a degree must satisfy. A bachelor's degree signed by the community college has a sound signature, and the college is on the list, but the degree fails the associate-degree schema its recognition names. The specification defines those members and leaves checking them to the verifier. This demonstration checks them, because in the quality infrastructure that is where the CMC and the accreditation scope go.

The quality infrastructure already works exactly this way. It just does it on paper, and the checking is done by people. [Chapter](#verification) runs the same walk from a calibration certificate up to the BIPM.

<!-- block: mapping.title -->

The specification and this domain, side by side

<!-- block: mapping.hint -->

The mapping is close enough that almost nothing had to be invented

<!-- block: mapping.rows -->

| Recognized Entities | Quality infrastructure |
| --- | --- |
| Root of trust | BIPM under the CIPM MRA; Global ACI under the Global ACI MRA |
| RecognizedEntityCredential | CIPM MRA participation; ISO/IEC 17025 accreditation |
| RecognizedAction with an outputValidation schema | The declared CMC or the granted accreditation scope |
| Leaf credential | Calibration certificate, test report, certificate of conformity |
| recognizedIn, followed upward by the verifier | The recognition path a recipient checks by hand today |
| Section 2.4, Product Conformity | A certificate of conformity meeting a market surveillance authority at a border |

<!-- block: beyond-the-spec -->

Two things in this demonstration go beyond the specification, because metrology needs them and general credential systems have no equivalent.

**The CMC decides the logo.** An institute may apply the CIPM MRA logo only to work covered by a capability it has published. Here that is a machine-checkable claim rather than an image, and the recipient adjudicates it.

**The uncertainty travels with its budget.** Each certificate states what it inherited from the one above it, so a recipient can check that the arithmetic holds and that nothing was quietly improved along the way.
