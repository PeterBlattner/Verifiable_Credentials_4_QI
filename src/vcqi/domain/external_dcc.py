"""The PTB/DKD DCC this world carries by reference rather than inside a credential.

Every other calibration certificate here carries its PTB/DKD DCC as a passenger: the
document travels in ``uncertaintyRepresentations`` beside a readable subject that says
the same things in JSON. This one does the opposite. The document is published on its
own, and the credential that vouches for it holds a URL, a digest and four facts of
index -- nothing else.

The document itself is not generated. It is the DKD's own published example for standard
resistors, adapted to this world's fictional actors and committed as a package resource,
which is the point: the pointer model lets an issuer carry a document produced by its own
tooling, at whatever schema version that tooling emits. This one is **3.4.0-rc.2**, while
``domain/dcc.py`` generates 3.3.0, and nothing here has to reconcile them.

That is also the cost. This module deliberately does **not** parse the measurement out of
the document, and could not without work: the example states its uncertainty as
``si:valueExpandedMU``, while ``parse_dcc_result`` reads ``si:uncertainty``. So the four
index facts are what the issuer asserts about a document nothing reads, and a verifier
that believes them is believing the issuer rather than checking it. ``vc/verify.py`` says
so in as many words, and the chapter shows the resulting verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from vcqi.crypto.keys import DemoKey
from vcqi.crypto.xmldsig import sign_enveloped

__all__ = [
    "EXTERNAL_DCC_INDEX",
    "ExternalDccIndex",
    "external_dcc_bytes",
    "external_dcc_source",
]

#: Where the adapted example lives, beside this module inside the package.
_RESOURCE = Path(__file__).resolve().parent / "dcc_examples" / "DKD-E-1-1-resistor.xml"


@dataclass(frozen=True)
class ExternalDccIndex:
    """The handful of facts the credential states about the document.

    Enough to find the certificate, to route it, and to decide which capability it
    should be judged against. Not enough to judge it: there is no value, no Expanded
    Uncertainty and no budget, because all three live only inside the document.

    Attributes:
        certificate_number: The identifier the document carries as its
            ``dcc:uniqueIdentifier``.
        performed_on: Date of calibration, ISO 8601.
        measurand: Machine-readable identifier of the measured quantity, in the same
            vocabulary the CMC entries use.
        unit: Unit symbol, in this repository's notation rather than D-SI's.
        schema_version: The DCC schema version the document declares.
        namespace: The DCC namespace the document declares.
        quantity_format: The D-SI version its quantities are written in.
    """

    certificate_number: str
    performed_on: str
    measurand: str
    unit: str
    schema_version: str
    namespace: str
    quantity_format: str


#: The index for the committed document. Written down rather than parsed out, which is
#: exactly the weakness the pipeline reports: these are the issuer's claims about the
#: document, and nothing here confirms them against it.
EXTERNAL_DCC_INDEX = ExternalDccIndex(
    certificate_number="METAS-2026-0420",
    performed_on="2026-02-10",
    measurand="dc.resistance",
    unit="ohm",
    schema_version="3.4.0-rc.2",
    namespace="https://ptb.de/dcc",
    quantity_format="D-SI 2.2.1",
)


def external_dcc_source() -> str:
    """Return the unsigned document as committed.

    Returns:
        The adapted DKD example, without a ``ds:Signature``.
    """
    return _RESOURCE.read_text(encoding="utf-8")


@lru_cache(maxsize=4)
def _signed(scalar: int) -> bytes:
    """Sign the committed document with a private scalar.

    Memoised because the world is built more than once in a test session and signing
    walks a 28 kB document three times. Keyed on the scalar rather than on the key
    object so that two equal keys share one result.

    Args:
        scalar: The private scalar to sign with.

    Returns:
        The signed document as UTF-8 bytes.
    """
    key = DemoKey(
        did="",
        fragment="",
        private_key=ec.derive_private_key(scalar, ec.SECP256R1()),
        public_key_multibase="",
    )
    return sign_enveloped(external_dcc_source(), key).encode("utf-8")


def external_dcc_bytes(key: DemoKey) -> bytes:
    """Return the document with an enveloped ``ds:Signature`` over it.

    The signature is deterministic, so the published bytes -- and therefore the digest
    the credential records -- are the same on every run.

    Note what does not travel: nothing in the signature records whose key this was.
    ``ds:KeyValue`` has nowhere to put an identifier, and that is the contrast the
    document exists to draw. The credential around it is what names the issuer.

    Args:
        key: The institute's key. Only its private scalar is used.

    Returns:
        The signed document as UTF-8 bytes, ready to publish and to digest.
    """
    return _signed(key.private_key.private_numbers().private_value)
