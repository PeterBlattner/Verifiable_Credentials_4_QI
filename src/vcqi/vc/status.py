"""Revocation and suspension with a Bitstring Status List.

A credential that was valid when it was issued may stop being valid later. An
accreditation gets suspended pending corrective action; a certificate gets withdrawn
because the artefact was found to have drifted. Neither event changes the signature, so
a verifier that only checks the proof will happily accept a withdrawn certificate.

The Bitstring Status List handles this without telling the issuer who is asking. The
issuer publishes one large bitstring covering many credentials; each credential says
which position in that list is its own. A verifier fetches the whole list, which reveals
nothing about which credential it cares about, and reads one bit. The list is
compressed, so covering a hundred thousand credentials costs a few kilobytes.

Compression is pinned to a fixed modification time so that an unchanged list encodes to
identical bytes on every run, keeping the demonstration diffable.
"""

from __future__ import annotations

import base64
import gzip
from typing import Any

from vcqi.config import CONTEXT_CREDENTIALS_V2, CONTEXT_VCQI_V1

__all__ = [
    "BitstringStatusList",
    "MINIMUM_LIST_LENGTH",
    "status_list_credential",
    "read_status",
]

#: The specification sets a floor on list length so that the size of a list cannot
#: itself reveal how many credentials an issuer has issued.
MINIMUM_LIST_LENGTH = 131072


class BitstringStatusList:
    """A bitstring recording the status of many credentials at once.

    Attributes:
        purpose: What a set bit means, either ``revocation`` or ``suspension``.
        length: Number of positions in the list.
    """

    def __init__(self, purpose: str = "revocation", length: int = MINIMUM_LIST_LENGTH) -> None:
        """Create an empty status list.

        Args:
            purpose: What a set bit means for credentials pointing into this list.
            length: Number of positions. Rounded up to a whole number of bytes.

        Raises:
            ValueError: If the length is below the specified minimum.
        """
        if length < MINIMUM_LIST_LENGTH:
            raise ValueError(
                f"a status list must cover at least {MINIMUM_LIST_LENGTH} positions"
            )
        self.purpose = purpose
        self.length = length
        self._bits = bytearray((length + 7) // 8)

    def set(self, index: int, value: bool = True) -> None:
        """Set or clear the bit for one credential.

        Args:
            index: Position of the credential in the list.
            value: True to mark the credential revoked or suspended.

        Raises:
            IndexError: If the position is outside the list.
        """
        if not 0 <= index < self.length:
            raise IndexError(f"position {index} is outside a list of {self.length}")
        byte, bit = divmod(index, 8)
        # Positions are numbered from the most significant bit of each byte.
        mask = 0x80 >> bit
        if value:
            self._bits[byte] |= mask
        else:
            self._bits[byte] &= 0xFF ^ mask

    def get(self, index: int) -> bool:
        """Read the bit for one credential.

        Args:
            index: Position of the credential in the list.

        Returns:
            True if the credential is marked revoked or suspended.

        Raises:
            IndexError: If the position is outside the list.
        """
        if not 0 <= index < self.length:
            raise IndexError(f"position {index} is outside a list of {self.length}")
        byte, bit = divmod(index, 8)
        return bool(self._bits[byte] & (0x80 >> bit))

    @property
    def encoded_list(self) -> str:
        """Return the compressed, multibase-encoded bitstring.

        Returns:
            The list as unpadded base64url with the multibase prefix ``u``.
        """
        compressed = gzip.compress(bytes(self._bits), compresslevel=9, mtime=0)
        return "u" + base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def read_status(encoded_list: str, index: int) -> bool:
    """Read one position out of a published status list.

    Args:
        encoded_list: The ``encodedList`` value from a status list credential.
        index: Position to read.

    Returns:
        True if the credential at that position is marked.

    Raises:
        ValueError: If the encoded list is malformed or too short for the position.
    """
    if not encoded_list.startswith("u"):
        raise ValueError("encodedList is not multibase base64url")
    body = encoded_list[1:]
    try:
        compressed = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        bits = gzip.decompress(compressed)
    except (ValueError, OSError, EOFError) as error:
        raise ValueError(f"encodedList could not be decoded: {error}") from error

    byte, bit = divmod(index, 8)
    if byte >= len(bits):
        raise ValueError(f"position {index} is outside the published list")
    return bool(bits[byte] & (0x80 >> bit))


def status_list_credential(
    *,
    credential_id: str,
    issuer: dict[str, Any],
    valid_from: str,
    status_list: BitstringStatusList,
    description: str,
) -> dict[str, Any]:
    """Build the credential that publishes a status list.

    The list is itself a verifiable credential, so a verifier can confirm that the
    revocation information really comes from the issuer whose credential it is checking
    and has not been substituted on the way.

    Args:
        credential_id: URL the list is published at.
        issuer: The issuer object, from ``issuer_reference``.
        valid_from: Start of validity, as an XML Schema dateTime.
        status_list: The list to publish.
        description: One sentence on what this list covers.

    Returns:
        The unsecured credential, ready to be signed.
    """
    return {
        "@context": [CONTEXT_CREDENTIALS_V2, CONTEXT_VCQI_V1],
        "id": credential_id,
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "description": description,
        "issuer": issuer,
        "validFrom": valid_from,
        "credentialSubject": {
            "id": f"{credential_id}#list",
            "type": "BitstringStatusList",
            "statusPurpose": status_list.purpose,
            "encodedList": status_list.encoded_list,
        },
    }
