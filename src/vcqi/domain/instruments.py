"""The artefacts and products that the demonstration credentials are about.

A calibration certificate is a statement about a specific physical object at a specific
time, which is why every credential in the chain names an instrument rather than only a
laboratory. Following the instrument identifiers through the chain is what makes the
traceability visible: the standard that the national institute calibrated is the same
standard the accredited laboratory used, and the multimeter that laboratory calibrated
is the same one the testing laboratory measured with.

All identifiers, models and serial numbers are invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Instrument", "INSTRUMENTS", "instrument_by_id"]


@dataclass(frozen=True)
class Instrument:
    """One physical artefact or product.

    Attributes:
        id: Stable identifier used as the credential subject.
        kind: What the object is, for example ``StandardResistor``.
        name: Human-readable description.
        manufacturer: Who made it.
        model: Model designation.
        serial_number: Serial number.
        owner: DID of the organisation that owns it.
        nominal_value: Nominal value of the artefact, or None for a product.
        unit: Unit of the nominal value, or None for a product.
    """

    id: str
    kind: str
    name: str
    manufacturer: str
    model: str
    serial_number: str
    owner: str
    nominal_value: float | None = None
    unit: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Return the instrument as it appears inside a credential subject.

        Returns:
            A JSON-compatible dictionary describing the artefact.
        """
        document: dict[str, Any] = {
            "id": self.id,
            "type": self.kind,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serialNumber": self.serial_number,
        }
        if self.nominal_value is not None:
            document["nominalValue"] = self.nominal_value
        if self.unit is not None:
            document["unit"] = self.unit
        return document


#: The artefacts that appear in the demonstration traceability chain.
INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        id="urn:instrument:callab:standard-resistor:SR10K-0042",
        kind="StandardResistor",
        name="10 kilohm transfer standard",
        manufacturer="Tinsley (demonstration)",
        model="5685A",
        serial_number="SR10K-0042",
        owner="did:web:callab.example",
        nominal_value=1.0e4,
        unit="ohm",
    ),
    Instrument(
        id="urn:instrument:testlab:multimeter:DMM-1177",
        kind="DigitalMultimeter",
        name="Eight and a half digit reference multimeter",
        manufacturer="Fluke (demonstration)",
        model="8508A",
        serial_number="DMM-1177",
        owner="did:web:testlab.example",
        nominal_value=1.0e4,
        unit="ohm",
    ),
    Instrument(
        id="urn:product:acme:kettle:KT-2200-revC",
        kind="Product",
        name="Cordless kettle, 2200 W",
        manufacturer="Acme Appliances AG (demonstration)",
        model="KT-2200 revision C",
        serial_number="type series",
        owner="did:web:manufacturer.example",
    ),
)

_BY_ID = {instrument.id: instrument for instrument in INSTRUMENTS}


def instrument_by_id(identifier: str) -> Instrument | None:
    """Look up an artefact by identifier.

    Args:
        identifier: The instrument identifier used as a credential subject.

    Returns:
        The instrument, or None when the identifier is unknown.
    """
    return _BY_ID.get(identifier)


#: Two nominally equal standards, calibrated against the same transfer standard. They
#: exist so that the demonstration has a case where a customer combines two certificates
#: and the correlation between them actually matters.
SHARED_REFERENCE_PAIR: tuple[Instrument, Instrument] = (
    Instrument(
        id="urn:instrument:callab:standard-resistor:SR10K-0091",
        kind="StandardResistor",
        name="10 kilohm check standard A",
        manufacturer="Tinsley (demonstration)",
        model="5685A",
        serial_number="SR10K-0091",
        owner="did:web:callab.example",
        nominal_value=1.0e4,
        unit="ohm",
    ),
    Instrument(
        id="urn:instrument:callab:standard-resistor:SR10K-0092",
        kind="StandardResistor",
        name="10 kilohm check standard B",
        manufacturer="Tinsley (demonstration)",
        model="5685A",
        serial_number="SR10K-0092",
        owner="did:web:callab.example",
        nominal_value=1.0e4,
        unit="ohm",
    ),
)

INSTRUMENTS = INSTRUMENTS + SHARED_REFERENCE_PAIR
_BY_ID.update({instrument.id: instrument for instrument in SHARED_REFERENCE_PAIR})
