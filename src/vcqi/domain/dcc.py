"""The PTB/DKD Digital Calibration Certificate, as a carrier of a whole certificate.

Note the name. Several things are called a DCC; this module means the one defined by the
PTB and the DKD, schema version 3.3.0 in the namespace ``https://ptb.de/dcc``, whose
quantities are expressed in D-SI version 2.2.1 in ``https://ptb.de/si``.

It belongs at a different level from everything else in `domain/uncertainty.py`, and
keeping the levels apart is the point of carrying it at all:

* the classical statement, an UncLib serialisation and a GTC archive all describe **a
  result** — how good a number is, and what it depends on;
* a PTB/DKD DCC describes **a document** — who calibrated what, for whom, when, under
  which conditions, with which equipment, and what came out.

They are not alternatives, and they compose. D-SI's ``si:expandedUnc`` carries a value,
an uncertainty, a coverage factor and a coverage probability, which is precisely the
classical statement and precisely not the dependency structure. So a certificate that
wants both a standardised document *and* transmissible dependencies carries a PTB/DKD DCC
and an UncLib block side by side, which is what the credentials here do.

What is built here is a **subset**. It uses the real namespaces, the real element names
and the real nesting, and it includes only the elements this demonstration has data for.
It is not schema-validated against the published XSD and it is not a conformant document.
See ARCHITECTURE.md for the rest of that list.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from typing import Any

from vcqi.domain.uncertainty import MeasurementResult

__all__ = [
    "DCC_NAMESPACE",
    "DCC_SCHEMA_VERSION",
    "SI_NAMESPACE",
    "SI_VERSION",
    "DSI_UNITS",
    "dsi_unit",
    "to_dcc_xml",
    "parse_dcc_result",
    "parse_dcc_administrative",
]

DCC_NAMESPACE = "https://ptb.de/dcc"
DCC_SCHEMA_VERSION = "3.3.0"
SI_NAMESPACE = "https://ptb.de/si"
SI_VERSION = "2.2.1"

#: D-SI writes units the way siunitx does: English names, each preceded by a backslash,
#: with prefixes and powers as separate tokens. The one that catches people is the
#: kilogram. It is ``\kilo\gram`` and not ``\kilogram``, because ``kilo`` is a prefix
#: token in its own right and the base unit is ``gram`` even though the SI base unit is
#: the kilogram. Powers use ``\tothe{n}``, so a cubic metre is ``\metre\tothe{3}``.
DSI_UNITS: dict[str, str] = {
    "": r"\one",
    "1": r"\one",
    "ohm": r"\ohm",
    "V": r"\volt",
    "A": r"\ampere",
    "kg": r"\kilo\gram",
    "g": r"\gram",
    "m": r"\metre",
    "s": r"\second",
    "K": r"\kelvin",
    "degC": r"\degreecelsius",
    "Hz": r"\hertz",
    "F": r"\farad",
}


def dsi_unit(symbol: str) -> str:
    """Translate a unit symbol into D-SI notation.

    Args:
        symbol: The unit as this demonstration writes it, for example ``ohm``.

    Returns:
        The D-SI form, for example ``\\ohm``.

    Raises:
        ValueError: If the unit has no mapping. Deliberately an error rather than a
            fallback: a calibration certificate that quietly states the wrong unit is
            worse than one that fails to be produced.
    """
    try:
        return DSI_UNITS[symbol]
    except KeyError:
        raise ValueError(
            f"no D-SI notation is defined here for the unit {symbol!r}; add it to "
            f"DSI_UNITS rather than guessing"
        ) from None


def _element(parent: Any, namespace: str, tag: str, text: str | None = None) -> Any:
    """Append a namespaced child element.

    Args:
        parent: The element to append to.
        namespace: The namespace URI.
        tag: The local name.
        text: Optional text content.

    Returns:
        The new element.
    """
    child = ElementTree.SubElement(parent, f"{{{namespace}}}{tag}")
    if text is not None:
        child.text = text
    return child


def _named_block(parent: Any, tag: str, name: str) -> Any:
    """Append a DCC element carrying a single human-readable name.

    Several DCC elements share the shape of a ``dcc:name`` holding one or more
    ``dcc:content`` strings tagged by language. This builds that shape once.

    Args:
        parent: The element to append to.
        tag: The local name of the element to create.
        name: The text to put in its content.

    Returns:
        The new element, so a caller can add further children.
    """
    block = _element(parent, DCC_NAMESPACE, tag)
    name_element = _element(block, DCC_NAMESPACE, "name")
    content = _element(name_element, DCC_NAMESPACE, "content", name)
    content.set("lang", "en")
    return block


def to_dcc_xml(
    result: MeasurementResult,
    *,
    certificate_number: str,
    performed_on: str,
    issued_on: str,
    measurand: str,
    conditions: str,
    instrument: dict[str, Any],
    laboratory: dict[str, Any],
    customer: dict[str, Any],
    reference_certificate: str | None = None,
) -> str:
    """Express one calibration result as a PTB/DKD DCC.

    Args:
        result: The evaluated measurement result.
        certificate_number: The certificate number, which becomes the unique identifier.
        performed_on: Date the calibration was performed, as an ISO 8601 date.
        issued_on: Date the certificate was issued, as an ISO 8601 date.
        measurand: Machine-readable identifier of the measured quantity.
        conditions: The stated measurement conditions.
        instrument: The calibrated artefact, from ``Instrument.to_json``.
        laboratory: The issuing laboratory, as an identifier and a name.
        customer: The organisation the certificate was issued to.
        reference_certificate: Identifier of the certificate of the reference standard
            used, when there is one.

    Returns:
        The document as an XML string.

    Raises:
        ValueError: If the unit of the result has no D-SI notation defined.
    """
    ElementTree.register_namespace("dcc", DCC_NAMESPACE)
    ElementTree.register_namespace("si", SI_NAMESPACE)

    root = ElementTree.Element(f"{{{DCC_NAMESPACE}}}digitalCalibrationCertificate")
    root.set("schemaVersion", DCC_SCHEMA_VERSION)

    # --- administrativeData ------------------------------------------------------
    administrative = _element(root, DCC_NAMESPACE, "administrativeData")

    core = _element(administrative, DCC_NAMESPACE, "coreData")
    _element(core, DCC_NAMESPACE, "countryCodeISO3166_1", "CH")
    _element(core, DCC_NAMESPACE, "usedLangCodeISO639_1", "en")
    _element(core, DCC_NAMESPACE, "mandatoryLangCodeISO639_1", "en")
    _element(core, DCC_NAMESPACE, "uniqueIdentifier", certificate_number)
    _element(core, DCC_NAMESPACE, "beginPerformanceDate", performed_on)
    _element(core, DCC_NAMESPACE, "endPerformanceDate", performed_on)
    _element(core, DCC_NAMESPACE, "performanceLocation", "laboratory")
    _element(core, DCC_NAMESPACE, "issueDate", issued_on)

    items = _element(administrative, DCC_NAMESPACE, "items")
    item = _named_block(items, "item", str(instrument.get("name", "")))
    _element(item, DCC_NAMESPACE, "manufacturer")
    manufacturer = item.find(f"{{{DCC_NAMESPACE}}}manufacturer")
    _element(manufacturer, DCC_NAMESPACE, "name")
    manufacturer_name = manufacturer.find(f"{{{DCC_NAMESPACE}}}name")
    _element(
        manufacturer_name, DCC_NAMESPACE, "content", str(instrument.get("manufacturer", ""))
    )
    _element(item, DCC_NAMESPACE, "model", str(instrument.get("model", "")))
    identifications = _element(item, DCC_NAMESPACE, "identifications")
    identification = _element(identifications, DCC_NAMESPACE, "identification")
    _element(identification, DCC_NAMESPACE, "issuer", "manufacturer")
    _element(
        identification, DCC_NAMESPACE, "value", str(instrument.get("serialNumber", ""))
    )
    identification_name = _element(identification, DCC_NAMESPACE, "name")
    _element(identification_name, DCC_NAMESPACE, "content", "serial number")

    laboratory_block = _element(administrative, DCC_NAMESPACE, "calibrationLaboratory")
    laboratory_contact = _named_block(laboratory_block, "contact", str(laboratory.get("name", "")))
    _element(laboratory_contact, DCC_NAMESPACE, "eMail", str(laboratory.get("id", "")))

    customer_block = _named_block(administrative, "customer", str(customer.get("name", "")))
    _element(customer_block, DCC_NAMESPACE, "eMail", str(customer.get("id", "")))

    # --- measurementResults ------------------------------------------------------
    results_block = _element(root, DCC_NAMESPACE, "measurementResults")
    measurement = _named_block(results_block, "measurementResult", f"Calibration of {measurand}")

    used_methods = _element(measurement, DCC_NAMESPACE, "usedMethods")
    _named_block(used_methods, "usedMethod", f"Comparison measurement, {measurand}")

    if reference_certificate is not None:
        equipments = _element(measurement, DCC_NAMESPACE, "measuringEquipments")
        equipment = _named_block(equipments, "measuringEquipment", "Reference standard")
        equipment_ids = _element(equipment, DCC_NAMESPACE, "identifications")
        equipment_id = _element(equipment_ids, DCC_NAMESPACE, "identification")
        _element(equipment_id, DCC_NAMESPACE, "issuer", "calibrationLaboratory")
        _element(equipment_id, DCC_NAMESPACE, "value", reference_certificate)
        equipment_name = _element(equipment_id, DCC_NAMESPACE, "name")
        _element(equipment_name, DCC_NAMESPACE, "content", "calibration certificate")

    influences = _element(measurement, DCC_NAMESPACE, "influenceConditions")
    _named_block(influences, "influenceCondition", conditions)

    data_results = _element(measurement, DCC_NAMESPACE, "results")
    single = _named_block(data_results, "result", measurand)
    data = _element(single, DCC_NAMESPACE, "data")
    quantity_list = _element(data, DCC_NAMESPACE, "list")
    quantity = _named_block(quantity_list, "quantity", measurand)

    real = _element(quantity, SI_NAMESPACE, "real")
    _element(real, SI_NAMESPACE, "value", repr(result.value))
    _element(real, SI_NAMESPACE, "unit", dsi_unit(result.unit))
    expanded = _element(real, SI_NAMESPACE, "expandedUnc")
    _element(expanded, SI_NAMESPACE, "uncertainty", repr(result.expanded_uncertainty))
    _element(expanded, SI_NAMESPACE, "coverageFactor", repr(result.coverage_factor))
    _element(expanded, SI_NAMESPACE, "coverageProbability", "0.95")

    # dcc:comment, dcc:document and ds:Signature are deliberately absent. The signature
    # slot in particular is a decision rather than an omission: the credential carrying
    # this document signs it once and covers these bytes by digest, so there is exactly
    # one trust path. See ARCHITECTURE.md.

    ElementTree.indent(root, space="  ")
    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True)


def _text(root: Any, path: str) -> str | None:
    """Read the text of one element, tolerating its absence.

    Args:
        root: The element to search from.
        path: An ElementTree path using ``dcc`` and ``si`` prefixes.

    Returns:
        The text, or None when the element is not there.
    """
    found = root.find(path, {"dcc": DCC_NAMESPACE, "si": SI_NAMESPACE})
    return found.text if found is not None else None


def parse_dcc_result(dcc_xml: str) -> dict[str, Any]:
    """Read the measured quantity back out of a PTB/DKD DCC.

    Done with a plain XML parser rather than through any DCC library, so that a verifier
    checking this document does not depend on the tool that wrote it.

    Args:
        dcc_xml: The document.

    Returns:
        The value, the D-SI unit, the Expanded Uncertainty and the coverage factor.

    Raises:
        ValueError: If the document cannot be parsed or states no quantity.
    """
    try:
        root = ElementTree.fromstring(dcc_xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"the PTB/DKD DCC could not be parsed: {error}") from error

    base = (
        ".//dcc:measurementResults/dcc:measurementResult/dcc:results/dcc:result"
        "/dcc:data/dcc:list/dcc:quantity/si:real"
    )
    value = _text(root, f"{base}/si:value")
    unit = _text(root, f"{base}/si:unit")
    uncertainty = _text(root, f"{base}/si:expandedUnc/si:uncertainty")
    coverage = _text(root, f"{base}/si:expandedUnc/si:coverageFactor")

    if value is None or uncertainty is None or coverage is None:
        raise ValueError("the PTB/DKD DCC states no complete quantity")

    try:
        return {
            "value": float(value),
            "unit": unit,
            "expandedUncertainty": float(uncertainty),
            "coverageFactor": float(coverage),
        }
    except ValueError as error:
        raise ValueError(f"the quantity in the PTB/DKD DCC is not numeric: {error}") from error


def parse_dcc_administrative(dcc_xml: str) -> dict[str, Any]:
    """Read back the facts a PTB/DKD DCC states that the credential also states.

    These are the duplicated fields. Reading them is what makes the duplication useful
    rather than merely wasteful: a credential and the document inside it can disagree,
    and nothing but a comparison will notice.

    Args:
        dcc_xml: The document.

    Returns:
        The unique identifier, the laboratory, the customer and the performance dates.

    Raises:
        ValueError: If the document cannot be parsed.
    """
    try:
        root = ElementTree.fromstring(dcc_xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"the PTB/DKD DCC could not be parsed: {error}") from error

    core = "./dcc:administrativeData/dcc:coreData"
    return {
        "uniqueIdentifier": _text(root, f"{core}/dcc:uniqueIdentifier"),
        "beginPerformanceDate": _text(root, f"{core}/dcc:beginPerformanceDate"),
        "issueDate": _text(root, f"{core}/dcc:issueDate"),
        "calibrationLaboratory": _text(
            root,
            "./dcc:administrativeData/dcc:calibrationLaboratory/dcc:contact/dcc:name/dcc:content",
        ),
        "calibrationLaboratoryId": _text(
            root, "./dcc:administrativeData/dcc:calibrationLaboratory/dcc:contact/dcc:eMail"
        ),
        "customer": _text(
            root, "./dcc:administrativeData/dcc:customer/dcc:name/dcc:content"
        ),
        "customerId": _text(root, "./dcc:administrativeData/dcc:customer/dcc:eMail"),
    }
