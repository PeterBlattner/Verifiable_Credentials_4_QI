"""Constants shared across the demonstrator.

Every identifier here is fictional. The ``.example`` top-level domain is reserved by
RFC 2606 precisely so that documentation and demonstrations cannot be mistaken for the
real thing, and no credential produced by this project should ever be presented as an
authentic output of the organisations it alludes to.
"""

from __future__ import annotations

from typing import Final

#: Seed for deterministic demo key derivation. These keys are published in the source
#: tree and offer no security whatsoever; they exist so that every run of the demo
#: produces byte-identical credentials and screenshots.
DEMO_SEED: Final[bytes] = b"vcqi-demonstration-seed-v1"

#: Data Integrity cryptosuite used throughout. See ARCHITECTURE.md for why the demo
#: uses JCS canonicalization rather than the RDF canonicalization of ecdsa-rdfc-2019.
CRYPTOSUITE: Final[str] = "ecdsa-jcs-2019"

#: The base JSON-LD context every Verifiable Credential carries.
CONTEXT_CREDENTIALS_V2: Final[str] = "https://www.w3.org/ns/credentials/v2"

#: The context defining the metrology terms this demonstrator adds.
CONTEXT_VCQI_V1: Final[str] = "https://vcqi.example/contexts/v1"

#: Where the demonstrator's own documents live. Resolved locally, never fetched.
BIPM_ORIGIN: Final[str] = "https://bipm.example"
GLOBAL_ACI_ORIGIN: Final[str] = "https://global-aci.example"
SAS_ORIGIN: Final[str] = "https://sas.example"
METAS_ORIGIN: Final[str] = "https://metas.example"

#: Address the development server binds to.
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8000

#: Coverage factor used for every reported Expanded Uncertainty, per the CIPM MRA and
#: the GUM convention for calibration certificates.
COVERAGE_FACTOR: Final[float] = 2.0
