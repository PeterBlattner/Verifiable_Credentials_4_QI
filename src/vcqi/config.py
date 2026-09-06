"""Constants shared across the demonstrator.

Every identifier here is fictional. The ``.example`` top-level domain is reserved by
RFC 2606 precisely so that documentation and demonstrations cannot be mistaken for the
real thing, and no credential produced by this project should ever be presented as an
authentic output of the organisations it alludes to.

A handful of the constants below read the environment, because the demonstrator now runs
in two places rather than one: on a reader's own machine, where the defaults are what
they want, and behind a public URL, where the address, the port and the limits are the
host's to set. Every default is the local one, so running it locally needs no
environment at all.
"""

from __future__ import annotations

import os
from typing import Final


def _env_int(name: str, default: int) -> int:
    """Read a whole number from the environment.

    Args:
        name: The variable to read.
        default: What to use when it is unset or unreadable.

    Returns:
        The value, or the default. A malformed setting falls back rather than raising:
        a demonstrator should not refuse to start because a host passed a stray string,
        and the value it falls back to is the safe one in every case here.
    """
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a real number from the environment.

    Args:
        name: The variable to read.
        default: What to use when it is unset or unreadable.

    Returns:
        The value, or the default.
    """
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default

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

#: Address the server binds to. Localhost is what a reader running the demonstration on
#: their own machine wants; a container sets VCQI_HOST=0.0.0.0. The name is prefixed
#: because a bare HOST is a common and ambiguous variable in a hosting environment.
DEFAULT_HOST: Final[str] = os.environ.get("VCQI_HOST", "127.0.0.1")

#: Port to serve on. Managed hosts assign one and pass it as PORT.
DEFAULT_PORT: Final[int] = _env_int("PORT", 8000)

#: Whether this process is reachable from the public internet.
#:
#: ARCHITECTURE.md used to rest the safety argument for /api/keys/* on the server being
#: bound to localhost. Hosting makes that false, so the argument had to be replaced
#: rather than quietly dropped: there is still no secret to leak, because every key in
#: the demonstration derives from DEMO_SEED above and /api/keys/sign signs with a key
#: the caller supplied. What is left is unbounded CPU on attacker-chosen input, and the
#: limits below are the answer to it.
#:
#: The flag exists so that a reader running this locally is not made to fight rate
#: limits that only a public deployment needs.
PUBLIC: Final[bool] = os.environ.get("VCQI_PUBLIC", "0") == "1"

#: Largest request body the server will parse, in bytes. Every legitimate request is
#: well under a kilobyte except a credential pasted into POST /api/verify.
MAX_BODY_BYTES: Final[int] = _env_int("VCQI_MAX_BODY_BYTES", 256 * 1024)

#: Token bucket per client address, applied only to the POST routes that do real work.
#: Zero disables it, which is the default, so local use and the test suite are
#: unaffected. The container sets a burst that a person clicking through every chapter
#: will never reach and a script will reach immediately.
RATE_LIMIT_BURST: Final[int] = _env_int("VCQI_RATE_LIMIT_BURST", 0)
RATE_LIMIT_PER_SECOND: Final[float] = _env_float("VCQI_RATE_LIMIT_PER_SECOND", 1.0)

#: Asked of crawlers, and sent as X-Robots-Tag on every response. The demonstration is
#: meant to be opened from a link that someone was given, not found in a search for the
#: real organisations it names.
ALLOW_INDEXING: Final[bool] = os.environ.get("VCQI_ALLOW_INDEXING", "0") == "1"

#: Coverage factor used for every reported Expanded Uncertainty, per the CIPM MRA and
#: the GUM convention for calibration certificates.
COVERAGE_FACTOR: Final[float] = 2.0
