# syntax=docker/dockerfile:1.7
# The `syntax` line above must stay first. It pins the Dockerfile frontend, and this file
# needs a version that supports two things the built-in one only supports depending on
# which Docker the builder happens to be running: heredocs in RUN, used below to assert
# what reached the image, and --mount=type=cache. Pinning it makes the build behave the
# same on a laptop, on a GitHub runner and on Render's builders.

# The demonstrator as a container.
#
# There is nothing exotic here, and that is the point: it used to look like it would need
# Mono and a 900 MB image, because metas_unclib is a pythonnet wrapper over .NET
# assemblies. It does not, because the METAS UncLib licence covers one designated
# computer and forbids redistribution "incorporated into a software package", so a
# deployed copy computes with src/vcqi/domain/linprop.py instead and this image carries
# no proprietary code at all. See ARCHITECTURE.md.
#
# The base install therefore has no compiled dependency beyond cryptography's wheel: no
# compiler, no system package, no numpy. Roughly 150 MB.

# ---------------------------------------------------------------- dependencies
FROM python:3.11-slim-bookworm AS builder

# Pinned to the version used locally, and copied in rather than installed so that the
# official Python image stays in charge of the interpreter.
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies before source, so editing a chapter does not re-resolve anything.
# --frozen: a lockfile that has drifted from pyproject.toml fails the build rather than
# being silently re-resolved into something nobody reviewed.
# No --extra: metas-unclib and GTC both stay out, which for metas-unclib is the whole
# reason this image can exist.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# hatchling packages src/vcqi wholesale, so the interface should be inside the venv --
# but the local checkout is an editable install, so that had never actually been
# exercised. Fail here, loudly, rather than serving a blank page from a mispackaged
# image. app.py refuses to start without these too; this catches it a stage earlier.
RUN /app/.venv/bin/python - <<'PY'
import pathlib
import vcqi.web
root = pathlib.Path(vcqi.web.__file__).parent / "static"
for required in ("index.html", "js/app.js", "js/chapters.js", "css/app.css"):
    assert (root / required).is_file(), f"missing from the wheel: {required}"
# The chapter prose is markdown rather than Python, so nothing about it being importable
# proves it shipped. Without it every migrated chapter falls back to a descriptor that no
# longer carries a title, and the reader gets a blank heading and a column of red markers
# on the landing page -- which is the caution statement.
import vcqi.web.content as content
assert "cautions" in content.chapter_ids(), "the chapter prose did not reach the wheel"
import vcqi.domain.unclib_blobs as blobs
assert blobs.BLOBS_PATH.is_file(), "the committed UncLib blobs did not reach the wheel"
print("interface and blobs present")
PY

# Nothing licensed may end up in the image. If this ever succeeds, the build is
# redistributing METAS UncLib and must not be pushed.
RUN if /app/.venv/bin/python -c "import metas_unclib" 2>/dev/null; then \
        echo "FATAL: metas_unclib is in the image; it may not be redistributed" >&2; \
        exit 1; \
    fi; \
    echo "confirmed: no licensed dependency in the image"

# ---------------------------------------------------------------- runtime
FROM python:3.11-slim-bookworm AS runtime

# Note there are no comments *inside* these ENV blocks. Whether a comment line within a
# backslash continuation is stripped or swallowed into the value has varied between
# Dockerfile frontends, and an environment variable that silently ends up holding a
# sentence is a memorably confusing way to fail. The comments sit above the blocks.

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Bind to every interface, because the host's proxy is what reaches this, and take the
# port from the environment, because a managed host assigns it.
ENV VCQI_HOST=0.0.0.0 \
    PORT=8000

# Turn on the limits in web/limits.py, and with them drop the API docs, whose Swagger UI
# loads from a CDN that this app's own Content-Security-Policy forbids.
ENV VCQI_PUBLIC=1

# A reader clicking through the keys and issuing chapters spends about 85 tokens; 150
# with 5/s refill leaves them a wide margin while holding a script to roughly one
# expensive request a second.
ENV VCQI_RATE_LIMIT_BURST=150 \
    VCQI_RATE_LIMIT_PER_SECOND=5.0 \
    VCQI_MAX_BODY_BYTES=262144

# So uvicorn rewrites scope["client"] from X-Forwarded-For and the rate limiter charges
# the caller rather than the host's proxy.
ENV FORWARDED_ALLOW_IPS=*

WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder --chown=root:root /app/.venv /app/.venv

USER app
EXPOSE 8000

# Render uses its own health-check path, but this makes `docker run` self-verifying in
# CI and locally. The start period covers the lifespan warm-up, which builds the world
# before the port opens.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz',timeout=4).status==200 else 1)"]

# The existing console script. It reads VCQI_HOST and PORT from the environment, so
# there is nothing host-specific in the command.
CMD ["vc-demo"]
