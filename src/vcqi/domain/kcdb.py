"""A stand-in for the BIPM key comparison database.

Under the CIPM MRA a National Metrology Institute may only claim international
recognition for calibrations that fall inside a Calibration and Measurement Capability
it has declared, peer reviewed through its Regional Metrology Organisation and
published in the KCDB. The CIPM MRA logo on a calibration certificate is exactly that
claim, which makes "is this certificate inside a published CMC?" the question a
recipient most needs answered and least often can answer.

Today the answer requires a human to open the KCDB, find the right entry and compare it
against the certificate by eye. The entries here carry the same information as a real
KCDB row, in a form a verifier can check by itself.

Every entry is fictional. The identifiers, ranges and uncertainties resemble real
services closely enough to be believable and are not taken from any published CMC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vcqi.config import BIPM_ORIGIN
from vcqi.domain.scope import DeclaredCapability, UncertaintyFloor

__all__ = ["CmcEntry", "CMC_ENTRIES", "cmc_by_id", "cmc_url", "cmcs_for_institute"]


@dataclass(frozen=True)
class CmcEntry:
    """One published Calibration and Measurement Capability.

    The attribute names follow the column groups a KCDB table uses, so that a reader
    who knows the database can recognise what each field corresponds to.

    Attributes:
        identifier: The CMC identifier, for example ``CH-EM-0042``.
        institute: DID of the institute the capability belongs to.
        institute_name: Human-readable name of that institute.
        country: ISO 3166 alpha-2 code of the institute.
        rmo: Regional Metrology Organisation that reviewed the entry.
        branch: KCDB columns A to C, the metrology area.
        service: The calibration or measurement service.
        instrument: The kind of artefact the service applies to.
        measurand: Machine-readable identifier of the measured quantity.
        unit: Unit symbol the range and uncertainty are expressed in.
        range_minimum: KCDB columns D to F, lowest covered level, in ``unit``.
        range_maximum: Highest covered level, in ``unit``.
        conditions: KCDB columns G and H, the measurement conditions.
        uncertainty_floor: KCDB columns I to M, the smallest covered Expanded
            Uncertainty as a function of level.
        supporting_comparison: The key or supplementary comparison that underpins the
            entry, which is what gives the declaration its evidence.
        published: Date the entry was published, as an ISO 8601 date.
    """

    identifier: str
    institute: str
    institute_name: str
    country: str
    rmo: str
    branch: str
    service: str
    instrument: str
    measurand: str
    unit: str
    range_minimum: float
    range_maximum: float
    conditions: str
    uncertainty_floor: UncertaintyFloor
    supporting_comparison: str
    published: str

    @property
    def url(self) -> str:
        """Return the address at which this entry is published.

        Returns:
            The URL a credential uses when it references this CMC.
        """
        return cmc_url(self.identifier)

    def as_capability(self) -> DeclaredCapability:
        """Return the entry in the form the scope check consumes.

        Returns:
            The declared capability, labelled with the CMC identifier.
        """
        return DeclaredCapability(
            label=f"CMC {self.identifier}",
            measurand=self.measurand,
            unit=self.unit,
            range_minimum=self.range_minimum,
            range_maximum=self.range_maximum,
            conditions=self.conditions,
            uncertainty_floor=self.uncertainty_floor,
        )

    def to_json(self) -> dict[str, Any]:
        """Return the entry as the registry would publish it.

        Returns:
            A JSON-compatible dictionary. The ``kcdbColumns`` member records which
            KCDB column group each part corresponds to, so a reader can line the
            document up against the database they already know.
        """
        return {
            "id": self.url,
            "type": "KcdbCmcEntry",
            "identifier": self.identifier,
            "institute": self.institute,
            "instituteName": self.institute_name,
            "country": self.country,
            "regionalMetrologyOrganisation": self.rmo,
            "branch": self.branch,
            "service": self.service,
            "instrument": self.instrument,
            "measurand": self.measurand,
            "unit": self.unit,
            "rangeMinimum": self.range_minimum,
            "rangeMaximum": self.range_maximum,
            "conditions": self.conditions,
            "expandedUncertainty": {
                **self.uncertainty_floor.to_json(),
                "description": self.uncertainty_floor.describe(self.unit),
            },
            "supportingComparison": self.supporting_comparison,
            "published": self.published,
            "kcdbColumns": {
                "A-C": "branch, service, instrument",
                "D-F": "rangeMinimum, rangeMaximum, unit",
                "G-H": "conditions",
                "I-M": "expandedUncertainty",
            },
        }


def cmc_url(identifier: str) -> str:
    """Return the published address of a CMC entry.

    Args:
        identifier: The CMC identifier, for example ``CH-EM-0042``.

    Returns:
        The URL the registry serves that entry at.
    """
    return f"{BIPM_ORIGIN}/kcdb/cmc/{identifier}"


#: The published capabilities of the demonstration institutes.
CMC_ENTRIES: tuple[CmcEntry, ...] = (
    CmcEntry(
        identifier="CH-EM-0042",
        institute="did:web:metas.example",
        institute_name="Federal Institute of Metrology (demonstration)",
        country="CH",
        rmo="EURAMET",
        branch="Electricity and Magnetism",
        service="DC resistance",
        instrument="Standard resistor",
        measurand="dc.resistance",
        unit="ohm",
        range_minimum=1.0,
        range_maximum=1.0e5,
        conditions="(23.0 +/- 1.0) degC, DC, four-terminal connection",
        uncertainty_floor=UncertaintyFloor(absolute=2.0e-4, relative=1.0e-7),
        supporting_comparison="EURAMET.EM-K2 (demonstration)",
        published="2025-03-14",
    ),
    CmcEntry(
        identifier="CH-EM-0071",
        institute="did:web:metas.example",
        institute_name="Federal Institute of Metrology (demonstration)",
        country="CH",
        rmo="EURAMET",
        branch="Electricity and Magnetism",
        service="DC voltage",
        instrument="Zener voltage standard",
        measurand="dc.voltage",
        unit="V",
        range_minimum=1.0,
        range_maximum=1000.0,
        conditions="(23.0 +/- 1.0) degC, DC",
        uncertainty_floor=UncertaintyFloor(absolute=5.0e-7, relative=2.0e-7),
        supporting_comparison="EURAMET.EM-K11 (demonstration)",
        published="2025-03-14",
    ),
    CmcEntry(
        identifier="CH-M-0015",
        institute="did:web:metas.example",
        institute_name="Federal Institute of Metrology (demonstration)",
        country="CH",
        rmo="EURAMET",
        branch="Mass and related quantities",
        service="Mass",
        instrument="Weights of OIML classes E2 to M1",
        measurand="mass",
        unit="kg",
        range_minimum=1.0e-6,
        range_maximum=20.0,
        conditions="(20.0 +/- 2.0) degC, conventional mass, air buoyancy corrected",
        uncertainty_floor=UncertaintyFloor(absolute=1.0e-7, relative=1.5e-8),
        supporting_comparison="EURAMET.M.M-K2 (demonstration)",
        published="2025-03-14",
    ),
    CmcEntry(
        identifier="DE-EM-0117",
        institute="did:web:ptb.example",
        institute_name="National Metrology Institute of Germany (demonstration)",
        country="DE",
        rmo="EURAMET",
        branch="Electricity and Magnetism",
        service="DC resistance",
        instrument="Standard resistor",
        measurand="dc.resistance",
        unit="ohm",
        range_minimum=1.0e-3,
        range_maximum=1.0e6,
        conditions="(23.0 +/- 0.5) degC, DC, four-terminal connection",
        uncertainty_floor=UncertaintyFloor(absolute=1.5e-4, relative=8.0e-8),
        supporting_comparison="CCEM-K2 (demonstration)",
        published="2025-06-02",
    ),
)

_BY_IDENTIFIER = {entry.identifier: entry for entry in CMC_ENTRIES}
_BY_URL = {entry.url: entry for entry in CMC_ENTRIES}


def cmc_by_id(reference: str) -> CmcEntry | None:
    """Look up a CMC entry by identifier or by published URL.

    Args:
        reference: A CMC identifier such as ``CH-EM-0042``, or the URL a credential
            references it by.

    Returns:
        The entry, or None when nothing is published under that reference. A verifier
        treats the absent case as "not covered", never as "assume covered".
    """
    return _BY_IDENTIFIER.get(reference) or _BY_URL.get(reference)


def cmcs_for_institute(institute: str) -> tuple[CmcEntry, ...]:
    """Return every capability published for one institute.

    Args:
        institute: DID of the institute.

    Returns:
        The published entries, in registry order.
    """
    return tuple(entry for entry in CMC_ENTRIES if entry.institute == institute)
