<!-- 01-orientation.md -- chapter 0 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterOrientation() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before. -->

<!-- block: title -->

What a verifiable credential is

<!-- block: eyebrow -->

Start here

<!-- block: lede -->

Written for someone who has not met verifiable credentials before, and who does know what a calibration certificate is.

<!-- block: what-it-is -->

A **verifiable credential** is a document with a digital signature over it, made with a key that its issuer publishes at a stable identifier. That is nearly the whole idea. Anyone who receives the document can check the signature without contacting the issuer, without an account, and without a prior relationship.

Three parties appear in every description of it. The **issuer** makes the document. The **holder** keeps it and presents it when needed. The **verifier** receives it and decides whether to believe it. In this domain those are usually a calibration laboratory, its customer, and whoever the customer has to satisfy.

<!-- block: the-gap-signatures-leave -->

Signatures alone answer only one question: has this document been altered since it was made. They leave the harder question untouched, which is whether the party who made it had any standing to. A perfectly valid signature by an organisation nobody has heard of proves only that the organisation exists.

That is the gap the W3C **Recognized Entities** specification addresses. A recognising authority issues a credential listing the entities it recognises and what each is recognised to do. A document carries a pointer to the list it claims to appear in, and a verifier follows those pointers upward until it reaches an identifier it already trusts.

The quality infrastructure already works exactly this way. It just does it on paper, and the checking is done by people.

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
