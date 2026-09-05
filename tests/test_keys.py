"""Tests for the key material the keys chapter teaches from.

The chapter makes four claims a reader is asked to believe: that a public key really is
computed from a private one, that a signature binds exactly one key to exactly one
message, that an identifier can carry its own key, and that a valid signature settles
almost nothing on its own. These make each of them checkable.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from vcqi.crypto.ecdsa_p256 import P256, public_point
from vcqi.crypto.keys import public_key_from_multikey
from vcqi.crypto.multibase import encode_p256_multikey
from vcqi.vc.resolver import DID_KEY_PREFIX, Resolver, did_key_document
from vcqi.web.app import app

ARBITRARY = 0x7F3A9C2E5B1D48A6F0E93C7B21D5860419AE3F72C8B04D61E5927AC3B8046F1D


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the application."""
    return TestClient(app)


@pytest.fixture(scope="module")
def derived(client: TestClient) -> dict:
    """Return a key derived from a fixed passphrase."""
    return client.post("/api/keys/derive", json={"passphrase": "a passphrase"}).json()


class TestPublicPoint:
    """The public key is genuinely computed from the private one."""

    @pytest.mark.parametrize("scalar", [1, 2, 3, ARBITRARY, P256.n - 1])
    def test_agrees_with_an_independent_implementation(self, scalar: int) -> None:
        """Point multiplication matches what the cryptography library derives."""
        expected = ec.derive_private_key(scalar, ec.SECP256R1()).public_key().public_numbers()
        assert public_point(scalar) == (expected.x, expected.y)

    def test_the_point_lies_on_the_curve(self) -> None:
        """The result satisfies the curve equation, which is what makes it a key."""
        x, y = public_point(ARBITRARY)
        assert (y * y - (x * x * x + P256.a * x + P256.b)) % P256.p == 0

    @pytest.mark.parametrize("scalar", [0, -1, P256.n, P256.n + 1])
    def test_scalars_outside_the_group_are_rejected(self, scalar: int) -> None:
        """Zero and the group order are not private keys, and must not look like one."""
        with pytest.raises(ValueError):
            public_point(scalar)

    def test_different_scalars_give_different_points(self) -> None:
        """Two people who choose different numbers get different keys."""
        assert public_point(ARBITRARY) != public_point(ARBITRARY + 1)


class TestDidKey:
    """An identifier that carries its own key needs no lookup."""

    def _multikey(self, scalar: int) -> str:
        """Return the Multikey for a private scalar."""
        private = ec.derive_private_key(scalar, ec.SECP256R1())
        return encode_p256_multikey(
            private.public_key().public_bytes(Encoding.X962, PublicFormat.CompressedPoint)
        )

    def test_the_identifier_expands_to_the_key_it_contains(self) -> None:
        """A did:key resolves to itself, with no document to fetch."""
        multikey = self._multikey(ARBITRARY)
        document = did_key_document(f"{DID_KEY_PREFIX}{multikey}")
        assert document is not None
        assert document["verificationMethod"][0]["publicKeyMultibase"] == multikey

    def test_it_resolves_without_any_retrieval(self) -> None:
        """No store, no network, and the right key comes back.

        The contrast with did:web is the teaching point: one identifier is the key, the
        other is a name that has to be resolved to find one.
        """
        from vcqi.vc.resolver import DocumentStore

        multikey = self._multikey(ARBITRARY)
        did = f"{DID_KEY_PREFIX}{multikey}"
        resolver = Resolver(DocumentStore())

        recovered = resolver.resolve_public_key(f"{did}#{multikey}")
        expected = ec.derive_private_key(ARBITRARY, ec.SECP256R1()).public_key()
        assert recovered is not None
        assert recovered.public_numbers() == expected.public_numbers()
        assert resolver.assertion_methods(did) == [f"{did}#{multikey}"]
        assert [record.source for record in resolver.log] == ["self-describing"] * 2

    @pytest.mark.parametrize("did", ["did:web:metas.example", "did:key:", "", "nonsense"])
    def test_anything_else_is_not_a_did_key(self, did: str) -> None:
        """Only a well-formed did:key expands; everything else falls through to a fetch."""
        assert did_key_document(did) is None


class TestDeriveRoute:
    """Making a key, and what the chapter says about how it was made."""

    def test_a_passphrase_gives_the_same_key_every_time(self, client: TestClient) -> None:
        """Reproducible by design, which is exactly why it is not safe."""
        first = client.post("/api/keys/derive", json={"passphrase": "hunter2"}).json()
        second = client.post("/api/keys/derive", json={"passphrase": "hunter2"}).json()
        assert first["privateScalarHex"] == second["privateScalarHex"]
        assert first["reproducible"] is True

    def test_different_passphrases_give_different_keys(self, client: TestClient) -> None:
        """One character of difference is a completely different key."""
        first = client.post("/api/keys/derive", json={"passphrase": "hunter2"}).json()
        second = client.post("/api/keys/derive", json={"passphrase": "hunter3"}).json()
        assert first["publicKeyMultibase"] != second["publicKeyMultibase"]

    def test_random_keys_differ(self, client: TestClient) -> None:
        """The contrast the chapter rests on: unpredictable rather than derived."""
        first = client.post("/api/keys/derive", json={"random": True}).json()
        second = client.post("/api/keys/derive", json={"random": True}).json()
        assert first["privateScalarHex"] != second["privateScalarHex"]
        assert first["reproducible"] is False

    def test_an_empty_request_is_refused(self, client: TestClient) -> None:
        """Neither a passphrase nor a request for randomness is not a key."""
        assert client.post("/api/keys/derive", json={}).status_code == 400

    def test_the_encoding_chain_ends_where_a_did_document_starts(
        self, derived: dict
    ) -> None:
        """Each layer is reversible and the last one is what gets published."""
        layers = derived["encodingLayers"]
        assert [layer["step"] for layer in layers][-1].startswith("base58btc")
        assert layers[-1]["value"] == derived["publicKeyMultibase"]
        assert derived["didKey"] == f"{DID_KEY_PREFIX}{derived['publicKeyMultibase']}"

        published = derived["didDocument"]["verificationMethod"][0]["publicKeyMultibase"]
        assert published == derived["publicKeyMultibase"]

    def test_the_published_key_decodes_back_to_the_computed_point(
        self, derived: dict
    ) -> None:
        """The string in a DID document really is the point, four encodings later."""
        recovered = public_key_from_multikey(derived["publicKeyMultibase"]).public_numbers()
        assert f"{recovered.x:064x}" == derived["publicPoint"]["x"]
        assert f"{recovered.y:064x}" == derived["publicPoint"]["y"]


class TestSignAndVerifyRoutes:
    """A signature binds one key to one message, and nothing else."""

    def test_a_signature_is_sixty_four_bytes_whatever_the_message(
        self, client: TestClient, derived: dict
    ) -> None:
        """What is signed is the digest, which is why length does not matter.

        It is also why the credentials elsewhere are canonicalized before hashing: the
        signature commits to one sequence of bytes and nothing more forgiving.
        """
        scalar = derived["privateScalarHex"]
        for message in ("x", "a much longer message " * 40):
            signed = client.post(
                "/api/keys/sign", json={"private_scalar_hex": scalar, "message": message}
            ).json()
            assert signed["signature"]["bytes"] == 64

    def _verify(self, client, message, signature, public_key):
        """Ask the verify route about a message, a signature and a key."""
        return client.post(
            "/api/keys/verify",
            json={
                "message": message,
                "signature_multibase": signature,
                "public_key_multibase": public_key,
            },
        ).json()

    def test_all_three_together_verify(self, client: TestClient, derived: dict) -> None:
        """The right key and the untouched message."""
        signed = client.post(
            "/api/keys/sign",
            json={"private_scalar_hex": derived["privateScalarHex"], "message": "10000.0012 ohm"},
        ).json()
        result = self._verify(
            client, "10000.0012 ohm", signed["signature"]["multibase"], derived["publicKeyMultibase"]
        )
        assert result["valid"] is True

    @pytest.mark.parametrize("broken", ["key", "message", "signature"])
    def test_changing_any_one_of_the_three_breaks_it(
        self, client: TestClient, derived: dict, broken: str
    ) -> None:
        """Key, message, signature: change any one and it fails."""
        other = client.post("/api/keys/derive", json={"passphrase": "somebody else"}).json()
        signed = client.post(
            "/api/keys/sign",
            json={"private_scalar_hex": derived["privateScalarHex"], "message": "10000.0012 ohm"},
        ).json()

        message = "10000.0012 ohm"
        signature = signed["signature"]["multibase"]
        public_key = derived["publicKeyMultibase"]

        if broken == "key":
            public_key = other["publicKeyMultibase"]
        elif broken == "message":
            message = "10000.0013 ohm"
        else:
            signature = signature[:-1] + ("2" if signature[-1] == "1" else "1")

        result = self._verify(client, message, signature, public_key)
        assert result["valid"] is False
        assert result["reason"]

    def test_a_malformed_key_or_signature_is_reported_not_raised(
        self, client: TestClient, derived: dict
    ) -> None:
        """A verifier meets these as untrusted input and must answer, not crash."""
        assert self._verify(client, "x", "znonsense", derived["publicKeyMultibase"])["valid"] is False
        assert self._verify(client, "x", "z11111", "not-a-key")["valid"] is False

    @pytest.mark.parametrize("scalar", ["zz", "0" * 64, f"{P256.n:064x}"])
    def test_unusable_private_keys_are_refused(self, client: TestClient, scalar: str) -> None:
        """Zero and the group order are not private keys."""
        assert (
            client.post("/api/keys/sign", json={"private_scalar_hex": scalar}).status_code == 400
        )


class TestIssueAsReader:
    """Three ways to sign a real certificate with your own key, three failures."""

    def _issue(self, client, derived, mode):
        """Sign the METAS certificate in one of the three modes."""
        return client.post(
            "/api/keys/issue",
            json={"private_scalar_hex": derived["privateScalarHex"], "mode": mode},
        ).json()

    def test_signing_as_yourself_proves_the_maths_and_nothing_else(
        self, client: TestClient, derived: dict
    ) -> None:
        """The signature is perfect. Nobody has heard of you."""
        data = self._issue(client, derived, "honest")
        assert data["proof"] == "pass"
        assert data["recognition"] == "fail"
        assert data["report"]["outcome"] == "rejected"

    def test_impersonating_fails_on_the_proof_and_passes_recognition(
        self, client: TestClient, derived: dict
    ) -> None:
        """The subtlest of the three, and the reason both checks exist.

        Recognition asks whether the issuer the credential *names* is recognised, and
        METAS is. Only the proof check binds that claim to a key. Either check on its
        own would let this through.
        """
        data = self._issue(client, derived, "impersonate")
        assert data["proof"] == "fail"
        assert data["recognition"] == "pass"
        assert "controlled by" in data["report"]["failureSummary"][0]["detail"]

    def test_claiming_the_key_identifier_too_fails_on_the_arithmetic(
        self, client: TestClient, derived: dict
    ) -> None:
        """Name the real key and the verifier fetches the real key."""
        data = self._issue(client, derived, "steal-key-id")
        assert data["proof"] == "fail"
        assert "does not verify" in data["report"]["failureSummary"][0]["detail"]

    def test_the_three_modes_fail_differently(self, client: TestClient, derived: dict) -> None:
        """Three attempts, three distinct first failures, which is the whole section."""
        first_failures = {
            mode: self._issue(client, derived, mode)["report"]["failureSummary"][0]["id"]
            for mode in ("honest", "impersonate", "steal-key-id")
        }
        assert first_failures["honest"] == "recognition"
        assert first_failures["impersonate"] == "proof"
        assert first_failures["steal-key-id"] == "proof"
        assert (
            self._issue(client, derived, "impersonate")["report"]["failureSummary"][0]["detail"]
            != self._issue(client, derived, "steal-key-id")["report"]["failureSummary"][0]["detail"]
        )

    def test_an_unknown_mode_is_refused(self, client: TestClient, derived: dict) -> None:
        """Only the three attempts the chapter describes."""
        assert (
            client.post(
                "/api/keys/issue",
                json={"private_scalar_hex": derived["privateScalarHex"], "mode": "elsewhere"},
            ).status_code
            == 400
        )
