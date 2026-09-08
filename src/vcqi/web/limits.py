"""Request limits for a demonstrator that is now reachable from anywhere.

`ARCHITECTURE.md` used to argue that `/api/keys/*` was harmless because the server bound
to localhost. Hosting removes that argument, so it is worth being precise about what the
exposure actually is, because it decides how much machinery is warranted.

It is **not** a secrecy problem. Every key in the demonstration derives from a seed
published in `config.py`, and `/api/keys/sign` signs caller-supplied bytes with a
caller-supplied key, so it is an oracle for nothing the caller did not already have.

It **is** a compute problem. `crypto/ecdsa_p256.py` is a deliberately readable
implementation: `_scalar_multiply` is naive double-and-add and every point operation
takes a modular inverse, so a scalar multiplication costs a few hundred `pow(x, -1, p)`
calls. That is milliseconds for a person and a denial of service for a loop. The same
goes for `/api/keys/derive` with `random: true`, which generates a fresh P-256 key per
request, and for `/api/verify`, which runs the whole pipeline over a credential the
caller wrote.

So: cap the body, and charge for the expensive routes. Both are plain ASGI middleware
rather than more of `app.py`, which is long enough, and neither adds a dependency.

What is deliberately not here, and why:

- **No distributed rate limiting.** The buckets are per process and vanish on restart,
  so many source addresses defeat them. Accepted: there is no data and no secret behind
  this, the worst case is that the demonstration is slow or the host restarts it, and a
  CDN in front is the proportionate answer if it ever matters.
- **No authentication.** The audience is people who should be able to open a URL.
- **Nothing done about the non-constant-time arithmetic.** It is the teaching material,
  and a timing side channel on a key published in the repository is not a finding.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, Final

__all__ = ["BodySizeLimitMiddleware", "RateLimitMiddleware", "route_cost"]

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

#: Above this many buckets the table is pruned. Sized so that ordinary traffic never
#: reaches it and a spray of forged addresses cannot grow it without bound.
_MAX_BUCKETS: Final[int] = 4096


async def _reject(send: Send, status: int, detail: str, headers: list[tuple[bytes, bytes]]) -> None:
    """Send a JSON error and nothing else.

    Written by hand rather than through Starlette's ``JSONResponse`` because these
    middlewares run outside the application and should not depend on it being reachable.

    Args:
        send: The ASGI send callable.
        status: HTTP status to report.
        detail: Message for the ``detail`` member, matching FastAPI's error shape so the
            interface's own error handling in ``static/js/api.js`` reads it.
        headers: Any additional headers to include.
    """
    body = b'{"detail":"%s"}' % detail.encode("utf-8").replace(b'"', b"'")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Refuse a request body larger than the cap, without buffering it.

    One honest caveat, which belongs here rather than in a commit message: by the time
    this sees a body chunk, uvicorn has already read those bytes off the socket. What
    this prevents is *buffering and parsing* an arbitrarily large document, which is
    where the memory and CPU would go. There is no ASGI-level way to do better, and the
    hosting provider's own limits sit in front of it.
    """

    def __init__(self, app: Any, *, max_bytes: int) -> None:
        """Wrap an application.

        Args:
            app: The ASGI application to wrap.
            max_bytes: Largest body to accept.
        """
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through, counting the body as it arrives.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # A declared length that already exceeds the cap is rejected before any of the
        # body is asked for, which is the common case for an accidental upload.
        for name, value in scope.get("headers", ()):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > self.max_bytes:
                    await _reject(
                        send,
                        413,
                        f"request body larger than {self.max_bytes} bytes",
                        [],
                    )
                    return
                break

        received = 0
        too_large = False

        async def counting_receive() -> MutableMapping[str, Any]:
            """Return the next event, refusing to yield more body than the cap allows.

            Returns:
                The ASGI event. Once the cap is passed the body is truncated and marked
                complete, so the application sees a short request and fails its own
                validation rather than being handed an unbounded document.
            """
            nonlocal received, too_large
            message = await receive()
            if message["type"] != "http.request":
                return message
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                too_large = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message: MutableMapping[str, Any]) -> None:
            """Replace the application's response when the body turned out too large.

            Args:
                message: The ASGI event the application is sending.
            """
            if too_large and message["type"] == "http.response.start":
                message = dict(message)
                message["status"] = 413
            await send(message)

        await self.app(scope, counting_receive, guarded_send)


def route_cost(path: str) -> int:
    """Return how many tokens a path costs.

    The test is not "how much work is this" but "can the caller raise it". Three routes
    can. ``/api/keys/*`` performs scalar multiplications on caller-supplied numbers,
    ``/api/verify`` runs the whole pipeline over a credential the caller wrote, whose
    size and nesting are theirs to choose, and a POST to an exchange runs that same
    pipeline over every credential in a presentation the caller composed -- which is
    ``/api/verify`` again with the count of credentials also in the caller's hands.

    Opening an exchange is charged too, and for a different reason. It costs almost
    nothing to serve and it allocates state that lives for fifteen minutes, so the thing
    being rationed there is the store rather than the CPU. It is charged lightly, because
    ``ExchangeStore`` has a ceiling and evicts oldest-first: the worst a flood achieves
    is to push out other people's exchanges, which is worth slowing and not worth
    treating as an attack on anything.

    Everything else is fixed-cost. ``/api/uncertainty``, ``/api/scope`` and
    ``/api/combine`` evaluate a model of four inputs however the sliders are set;
    ``/api/tamper/{key}`` replays one of a fixed list; the rest are dictionary lookups
    against a world built once. Charging those would throttle a reader dragging a
    slider — which the interface does on every input event — while doing nothing about
    an attacker, so they are free.

    Args:
        path: The request path.

    Returns:
        The cost in tokens, zero for anything a reader does by navigating.
    """
    if path.startswith("/api/keys/"):
        return 5
    if path.startswith("/api/verify"):
        return 3
    if path.startswith("/workflows/"):
        # ".../exchanges" opens one; ".../exchanges/{id}" takes a turn, and only the
        # turn can carry credentials to verify.
        return 1 if path.endswith("/exchanges") else 3
    return 0


class RateLimitMiddleware:
    """A token bucket per client address, charged only for POSTs that do real work.

    In-process and unshared, which is the honest choice for one container: there is no
    store to add and no dependency to take, and the alternative would be pretending to a
    guarantee this does not need. It does mean the limit multiplies if the app is ever
    run with several workers, which is one of the reasons ``main()`` runs one.
    """

    def __init__(self, app: Any, *, burst: int, per_second: float) -> None:
        """Wrap an application.

        Args:
            app: The ASGI application to wrap.
            burst: Bucket size, and so the number of cheap requests allowed at once.
                Zero disables the limiter entirely.
            per_second: Tokens added per second.
        """
        self.app = app
        self.burst = burst
        self.per_second = per_second
        self._buckets: dict[str, tuple[float, float]] = {}

    def _charge(self, client: str, cost: int, now: float) -> float:
        """Take tokens from a client's bucket, refilling it first.

        Args:
            client: The client address.
            cost: Tokens wanted.
            now: Current monotonic time.

        Returns:
            Seconds the caller should wait, or 0.0 when the request may proceed.
        """
        tokens, last = self._buckets.get(client, (float(self.burst), now))
        tokens = min(float(self.burst), tokens + (now - last) * self.per_second)
        if tokens < cost:
            self._buckets[client] = (tokens, now)
            return (cost - tokens) / self.per_second
        self._buckets[client] = (tokens - cost, now)
        return 0.0

    def _prune(self, now: float) -> None:
        """Drop buckets that have refilled, so the table cannot grow without bound.

        Args:
            now: Current monotonic time.
        """
        if len(self._buckets) <= _MAX_BUCKETS:
            return
        full = self.burst / self.per_second if self.per_second else 0.0
        self._buckets = {
            client: state
            for client, state in self._buckets.items()
            if now - state[1] < full
        }
        # Still full of live buckets: forget everything rather than grow. Being briefly
        # too permissive is a better failure than unbounded memory.
        if len(self._buckets) > _MAX_BUCKETS:
            self._buckets.clear()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Charge the request and pass it on, or refuse it.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if self.burst <= 0 or scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        cost = route_cost(scope.get("path", ""))
        if cost == 0:
            await self.app(scope, receive, send)
            return

        # uvicorn's proxy-headers handling rewrites scope["client"] from
        # X-Forwarded-For where FORWARDED_ALLOW_IPS permits, so behind the host's
        # proxy this is the real caller rather than the proxy.
        client = (scope.get("client") or ("unknown", 0))[0]
        now = time.monotonic()
        self._prune(now)
        wait = self._charge(client, cost, now)
        if wait > 0.0:
            await _reject(
                send,
                429,
                "too many requests to this endpoint; it does real cryptography",
                [(b"retry-after", str(max(1, int(wait + 0.999))).encode("ascii"))],
            )
            return
        await self.app(scope, receive, send)
