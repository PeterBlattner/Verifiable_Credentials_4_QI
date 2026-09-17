<!-- 09-tamper.md -- chapter 8 in the rail; the NN- prefix is the position in the
     CHAPTERS array, which counts the cautions. Rendered by chapterTamper() in
     ../../static/js/chapters.js.

     Each "block:" comment line below starts one block that the page asks for by
     name. Edit the words freely; renaming a key breaks the page, and the test suite
     will say which one. Read ../README.md first if you have not before.

     The fields themselves -- their labels, their units, the note under each one and the
     check each is expected to reach -- are in src/vcqi/actors/edit.py. They are records
     rather than prose, the server reads the same records to apply an edit, and a test
     runs every one of them through the pipeline to confirm the note is still true. Moving
     them here would split one fact across two files and leave the claim untested.

     The chapter before this one is the same argument with somebody else's hand on it:
     twenty-five cases that reach further than one document can, because they change the
     world around the certificate rather than the certificate. -->

<!-- block: title -->

Break it yourself

<!-- block: eyebrow -->

Hands on the document

<!-- block: lede -->

Change a field, decide whether the issuer signs it again, and see which check notices.

<!-- block: by-hand -->

The last chapter applied twenty-five failures somebody else chose. This is the same pipeline with the document in your hands: pick a certificate, change one of the fields it states, and run it.

Leave the signature alone and the answer is always the same — the proof fails, because the signature covers a canonical form of the whole document and a single digit invalidates it. That is worth seeing once. It is also the least interesting thing that can go wrong, and it is the only failure a system built on signatures alone can find.

So there is a second control. **Have the issuer sign it again**, and the document becomes cryptographically perfect: a genuine signature, by the organisation that claims to have issued it, over exactly the bytes you are looking at. Something else then has to catch it, or nothing does.

<!-- block: document.title -->

Which document would you like to break?

<!-- block: document.hint -->

the five documents a recipient is actually handed, rather than the recognitions behind them

<!-- block: fields.title -->

What would you like to change?

<!-- block: fields.hint -->

each field says what it is and which check it is expected to reach

<!-- block: resign.note -->

Only one check stops the report: a document that is not a Verifiable Credential at all is not examined further. **A failing proof stops nothing.** So with re-signing off you still see every later check run against the document you wrote, which is worth reading — it tells you what the document would and would not have survived on its own terms, quite apart from being unsigned.

<!-- block: changed.title -->

What you changed

<!-- block: inert-note -->

Three of the fields on offer change nothing, and they are on offer for that reason. A statement of conformity is the sentence a person reads and nothing adjudicates it. A test report names the instrument it measured with under a different member from the one the object-identity check looks for, so that check reports it has no object to compare and moves on — a real gap, left visible. And the copy of an OIML Recommendation carried inside a certificate is decoration, because the verifier reads the register's copy: editing your copy of somebody else's document changes nothing, which is the property you would want.

A pipeline is only as good as the list of things it thought to check. Finding the fields nobody checks is a better use of this page than confirming the ones they do.

<!-- block: catalogue-behind -->

One document at a time is as far as this goes, and that is the boundary between this chapter and the one before it. The cases there reach further — an accreditation suspended after the certificate was issued, a schema loosened after recognition was granted, a parent certificate reissued after it was referenced. None of those is a change to the document in front of you, and none of them could be made from here. Worth going back for, now that you have seen how much one document can be made to do on its own.
