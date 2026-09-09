<!-- 03-graph.md -- chapter 2 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterGraph() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The sentence under the arrangement filter counts organisations and documents and
     names the laboratories that appear in more than one arrangement, so it is built in
     the code from the graph the server sent. The field names in the detail panel --
     Identifier, Role, Country and the rest -- are labels and stay there too. -->

<!-- block: title -->

The quality infrastructure as a trust graph

<!-- block: eyebrow -->

The world

<!-- block: lede -->

Ten organisations, two international anchors, and one supply chain running from a national standard to a kettle at a border.

<!-- block: the-world -->

Thirteen organisations, and two supply chains running through them. A national metrology institute calibrates a laboratory’s transfer standard; the laboratory calibrates a testing laboratory’s multimeter; the testing laboratory measures a kettle; a certification body certifies the kettle; the manufacturer presents that certificate at a border. The same testing laboratory also evaluates a type of electricity meter against an OIML Recommendation, and an Issuing Authority certifies the type on the strength of that evaluation.

The three organisations at the top are the roots of trust: one for metrology, one for accreditation, one for legal metrology. All three are inventions, like everything else here. **Global ACI** stands in for whichever body holds the accreditation role, and nothing in the demonstration rests on that name — a verifier reaches an anchor by following identifiers upward from the document in front of it, not by knowing who occupies the position.

The three arrangements are separate, and the interesting part is where they are not. **Helvetia Testing** is accredited by SAS under ISO/IEC 17025 *and* recognised by OIML to perform type evaluation — one laboratory, one identifier, two arrangements above it, and neither of them aware the other exists. Filter to one arrangement to see its shape; the rest dims rather than disappearing, because a document resting on two of them at once is the thing worth looking at.

Click any organisation to see the identifier it signs with and what it has issued. Click any edge to read the credential behind it.

<!-- block: detail.title -->

Select an organisation or an edge

<!-- block: detail.hint -->

Everything below is fetched from the running server

<!-- block: nothing-selected -->

Nothing selected yet.

<!-- block: did.title -->

DID document

<!-- block: did-resolves -->

This is all an identifier resolves to: a key, what the key may be used for, and where to ask about the holder.

<!-- block: issued.title -->

Credentials it has issued
