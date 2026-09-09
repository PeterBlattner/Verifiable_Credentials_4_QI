<!-- 00-cautions.md -- first in the rail and deliberately carrying no chapter number.
     Rendered by chapterCautions() in ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The same statement is in the repository's README.md. If you correct one of them,
     correct the other -- otherwise the site and the repository say different things
     about how much to trust the work. -->

<!-- block: title -->

About these pages, and what they are not

<!-- block: eyebrow -->

Read this first

<!-- block: lede -->

Where this came from, and every reason not to rely on it.

<!-- block: where-this-came-from -->

These pages started as curiosity. A friend pointed me to the W3C Recognized Entities specification, whose use case §2.4 (Product Conformity) looked potentially relevant to the Quality Infrastructure. Over a few hours one weekend I used AI-assisted coding to sketch a simple metrology and accreditation scenario, mainly to understand Verifiable Credentials better myself.

I was struck by how much came together in so little time — which is exactly why the following warnings matter.

<!-- block: nothing-validated.title -->

Nothing here has been validated

<!-- block: nothing-validated.body -->

The concepts, data models, credential examples and workflows are illustrative sketches, not reference implementations. Nothing here has been tested in an interoperable deployment or checked line by line against the specifications.

One reviewer who works on these specifications has since spent about half an hour on it, over the data structures and the harmonisation chapter. Their reading was that most of the data structures hold up as a first draft, and that the harmonisation chapter overstated the problem: several things it listed as unsolved already have answers, some of them published while this was being written. Those corrections are now in chapter 11, which counts its open questions rather than asserting them. That is one reader's opinion after thirty minutes, and it is the only review this work has had. It is not validation, and it changes nothing about the warnings below.

Any DIDs, keys, signatures or credentials shown are fabricated for demonstration. The identifiers use the `.example` domain reserved by RFC 2606, and the signing keys are derived from a seed published in the source tree, so they protect nothing.

<!-- block: no-institution.title -->

No institution is speaking here

<!-- block: no-institution.body -->

BIPM, Global ACI, METAS and PTB appear only as recognisable placeholders in a fictional scenario. Nothing on these pages represents their views, plans, positions or endorsement, and none of them were involved in or informed about this work.

<!-- block: spec-moving.title -->

The underlying specification is still moving

<!-- block: spec-moving.body -->

Recognized Entities v1.0 is a W3C Working Draft, described by the Working Group as experimental and not fit for production deployment. Anything here may already be out of date.

<!-- block: no-warranty.title -->

No warranty

<!-- block: no-warranty.body -->

The content is provided as-is, for educational purposes only, with no assurance of correctness or fitness for any purpose. Do not rely on it for any decision about accreditation, conformity assessment or metrological traceability.

<!-- block: no-permanence.title -->

No permanence

<!-- block: no-permanence.body -->

These pages may change or disappear without notice.

<!-- block: correction -->

The hope is simply that this sparks curiosity — and, ideally, correction. If something here is wrong, I would genuinely like to hear it.

That has happened once already, unsolicited, and it made the work better rather than worse — which is the argument for publishing something unfinished in the first place. The offer stands.
