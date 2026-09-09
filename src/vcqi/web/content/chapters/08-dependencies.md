<!-- 08-dependencies.md -- chapter 7 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterDependencies() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The verdict line under the two columns is computed from the numbers, so it stays in
     the code. Only the one fixed sentence it can show instead -- "optimistic" below --
     is here. The operation chips and table headers are labels and stay too. -->

<!-- block: title -->

Why the dependencies matter

<!-- block: eyebrow -->

The argument for transmitting them

<!-- block: lede -->

Two certificates from one institute, resting on one national standard. What a customer can do with them depends on what was sent.

<!-- block: shared-standard -->

One institute, one national standard, two certificates. Both check standards were compared against the same 10 kΩ national standard, so a large part of what is uncertain about each result is *the same thing* being uncertain twice.

A customer who combines the two ought to get the benefit of that. Whether they can depends entirely on what the institute transmitted, and the choice was made when the certificate was written, not when the customer opened it.

<!-- block: question.title -->

What would you like to compute from the two certificates?

<!-- block: tracked.title -->

With the dependencies transmitted

<!-- block: tracked.hint -->

the shared influence is recognised and cancels correctly

<!-- block: naive.title -->

From the printed value and U alone

<!-- block: naive.hint -->

the shared influence is invisible, so it is counted twice

<!-- block: optimistic -->

Note the direction. For a mean, positive correlation makes the result less certain, not more, so ignoring it is optimistic rather than cautious. Classical reporting is not conservative; it is simply wrong by an amount nobody can compute.

<!-- block: shared.title -->

The influences the two certificates have in common

<!-- block: shared.hint -->

matched by identifier, not by name — two laboratories using the same wording are still different influences

<!-- block: inputs.title -->

The two certificates

<!-- block: the-cost -->

It is worth being clear about what the customer did wrong in the right-hand column: **nothing**. Combining in quadrature is the correct thing to do with two numbers that you have no reason to believe are related. The information that they were related existed, at the laboratory, and was not sent.

This is also the honest cost of the idea. A dependency representation exposes the structure of an uncertainty budget, and many laboratories regard that as commercially confidential. Selective disclosure is where that tension would be addressed, and it is not implemented here.
