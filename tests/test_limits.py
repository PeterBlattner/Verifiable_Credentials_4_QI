"""Tests for the things that had to be true before this could be hosted.

`ARCHITECTURE.md` rested the safety argument for `/api/keys/*` on the server binding to
localhost. Hosting makes that false, and these are the replacement argument in
executable form: a body cannot be arbitrarily large, the expensive routes cost tokens,
the response headers say what they should, and none of it applies by default so that
running the demonstration locally is unchanged.

That last one matters most. The default configuration disables the rate limiter
entirely, so every other test in this suite is unaffected, and a reader running
`uv run vc-demo` never meets a 429.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vcqi.config import MAX_BODY_BYTES, RATE_LIMIT_BURST
from vcqi.web.app import app
from vcqi.web.limits import BodySizeLimitMiddleware, RateLimitMiddleware, route_cost


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Return a client bound to the application as configured for local use."""
    return TestClient(app)


class TestTheDefaultsChangeNothing:
    """A reader running this on their own machine meets none of it."""

    def test_the_rate_limiter_is_off_by_default(self) -> None:
        """Zero burst, so the middleware short-circuits before it does any work."""
        assert RATE_LIMIT_BURST == 0

    def test_many_expensive_requests_all_succeed(self, client: TestClient) -> None:
        """The route that costs the most is not limited in the default configuration."""
        for _ in range(25):
            response = client.post("/api/keys/derive", json={"passphrase": "test"})
            assert response.status_code == 200


class TestBodySize:
    """A large body is refused rather than parsed."""

    def test_an_oversized_body_is_refused(self, client: TestClient) -> None:
        """Well past the cap, with a content-length the middleware can read."""
        payload = b'{"credential": "' + b"a" * (MAX_BODY_BYTES + 1024) + b'"}'
        response = client.post(
            "/api/verify", content=payload, headers={"content-type": "application/json"}
        )
        assert response.status_code == 413
        assert "larger than" in response.json()["detail"]

    def test_an_ordinary_body_is_untouched(self, client: TestClient) -> None:
        """The cap is far above anything the interface actually sends."""
        response = client.post("/api/verify", json={"name": "metas-calibration"})
        assert response.status_code == 200
        assert response.json()["outcome"] == "verified"

    def test_a_body_at_the_cap_is_rejected_without_a_declared_length(self) -> None:
        """Chunked and oversized: the counter catches what the header cannot.

        A caller that omits content-length gets past the cheap check, so the streaming
        path has to be the one that actually enforces the cap.
        """
        probe = FastAPI()

        @probe.post("/echo")
        async def echo(payload: dict) -> dict:
            """Return how much arrived, so a truncated body is visible."""
            return {"size": len(json.dumps(payload))}

        probe.add_middleware(BodySizeLimitMiddleware, max_bytes=2048)
        with TestClient(probe) as probe_client:
            body = b'{"x": "' + b"a" * 8192 + b'"}'

            def chunks():
                for start in range(0, len(body), 1024):
                    yield body[start : start + 1024]

            response = probe_client.post(
                "/echo", content=chunks(), headers={"content-type": "application/json"}
            )
        assert response.status_code == 413


class TestRateLimiting:
    """The expensive routes cost tokens; navigating the demonstration does not."""

    @staticmethod
    def _limited(burst: int, per_second: float = 1.0) -> TestClient:
        """Return a client over a tiny application with the limiter turned on.

        Args:
            burst: Bucket size.
            per_second: Refill rate.

        Returns:
            A client. Testing the middleware over a stub rather than over the real app
            keeps this about the limiter and not about the routes it protects.
        """
        probe = FastAPI()

        @probe.post("/api/keys/derive")
        async def derive() -> dict:
            """Stand in for the expensive route."""
            return {"ok": True}

        @probe.post("/api/world")
        async def cheap() -> dict:
            """Stand in for a route that should never be charged."""
            return {"ok": True}

        @probe.get("/api/keys/derive")
        async def read() -> dict:
            """Stand in for a GET, which is never charged."""
            return {"ok": True}

        probe.add_middleware(RateLimitMiddleware, burst=burst, per_second=per_second)
        return TestClient(probe)

    def test_the_bucket_empties_and_then_refuses(self) -> None:
        """A burst of ten tokens buys two requests at five each."""
        client = self._limited(burst=10)
        assert client.post("/api/keys/derive").status_code == 200
        assert client.post("/api/keys/derive").status_code == 200
        refused = client.post("/api/keys/derive")
        assert refused.status_code == 429
        assert int(refused.headers["retry-after"]) >= 1
        assert "cryptography" in refused.json()["detail"]

    def test_reading_is_never_charged(self) -> None:
        """Navigation must not be able to trip the limit.

        Someone clicking through twelve chapters issues a lot of GETs, and a
        demonstration that rate-limits its own reader is worse than one with no limiter.
        """
        client = self._limited(burst=1)
        for _ in range(50):
            assert client.get("/api/keys/derive").status_code == 200

    def test_only_the_routes_a_caller_can_make_expensive_are_charged(self) -> None:
        """The test is not how much work a route does but whether a caller can raise it.

        The slider routes evaluate a four-input model whatever the sliders say, so
        their cost is fixed and charging them would only throttle a reader dragging a
        control. The key routes multiply points on caller-supplied numbers and
        /api/verify walks a caller-supplied credential, so those two are charged.
        """
        assert route_cost("/api/keys/sign") == 5
        assert route_cost("/api/keys/derive") == 5
        assert route_cost("/api/verify") == 3
        for free in (
            "/api/uncertainty",
            "/api/scope",
            "/api/combine",
            "/api/tamper/forged-signature",
            "/api/world",
            "/static/js/app.js",
            "/",
        ):
            assert route_cost(free) == 0, free

    def test_dragging_a_slider_is_never_throttled(self) -> None:
        """The interface posts on every input event, so this must stay free.

        `sliderRow` in ui.js now serialises those calls, but the guarantee that matters
        here is the server-side one: even an undebounced drag cannot exhaust a bucket.
        """
        client = self._limited(burst=1)
        for _ in range(200):
            assert client.post("/api/world").status_code == 200

    def test_the_bucket_refills(self) -> None:
        """Waiting is enough; the limit throttles rather than banning."""
        client = self._limited(burst=5, per_second=1000.0)
        assert client.post("/api/keys/derive").status_code == 200
        assert client.post("/api/keys/derive").status_code == 429
        # At a thousand tokens a second the bucket is full again almost at once, which
        # keeps the test fast without making it depend on wall-clock sleeping.
        for _ in range(200):
            if client.post("/api/keys/derive").status_code == 200:
                break
        else:
            pytest.fail("the bucket never refilled")


class TestResponseHeaders:
    """What every response carries, and what it deliberately does not."""

    def test_the_content_security_policy_is_strict(self, client: TestClient) -> None:
        """No CDN, no font host, no analytics, so nothing has to be allowed."""
        policy = client.get("/").headers["content-security-policy"]
        assert "default-src 'none'" in policy
        assert "script-src 'self'" in policy
        # The favicon is an inline SVG data URI in index.html, and it is the only
        # reason data: appears anywhere in the policy.
        assert "img-src 'self' data:" in policy
        assert "frame-ancestors 'none'" in policy
        assert "unsafe-inline" not in policy
        assert "unsafe-eval" not in policy

    def test_no_cors_header_is_sent(self, client: TestClient) -> None:
        """Absence is the policy. Adding CORSMiddleware would only widen it."""
        for path in ("/", "/api/world", "/healthz"):
            assert "access-control-allow-origin" not in client.get(path).headers

    def test_crawlers_are_asked_off(self, client: TestClient) -> None:
        """The site names real organisations while inventing their documents."""
        assert client.get("/").headers["x-robots-tag"] == "noindex, nofollow"
        robots = client.get("/robots.txt")
        assert robots.status_code == 200
        assert "Disallow: /" in robots.text

    def test_the_usual_hardening_headers_are_present(self, client: TestClient) -> None:
        """Cheap, uncontroversial, and easy to lose in a refactor."""
        headers = client.get("/").headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        assert "camera=()" in headers["permissions-policy"]

    def test_hsts_is_not_claimed_over_plain_http(self, client: TestClient) -> None:
        """Asserting transport security on a connection that has none is noise."""
        assert "strict-transport-security" not in client.get("/").headers


class TestHealth:
    """What a host's health check sees."""

    def test_healthz_reports_ready(self, client: TestClient) -> None:
        """Status, version, and which engine computed the numbers."""
        body = client.get("/healthz").json()
        assert body["status"] == "ok"
        assert body["version"]
        assert body["engine"] in {"unclib", "linprop"}

    def test_the_warm_up_runs_and_does_not_raise(self) -> None:
        """Entering the lifespan is what a deployment does, so it is tested.

        The other tests here use TestClient without a context manager, which skips
        lifespan; this one exercises it, because a warm-up that raised would take the
        whole deployment down at startup.
        """
        with TestClient(app) as warmed:
            assert warmed.get("/healthz").json()["status"] == "ok"
