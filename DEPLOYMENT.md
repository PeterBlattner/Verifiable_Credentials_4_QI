


## Run it on the web

The demonstration argues that a verifier operates nothing. It should ask no more of its
own reader than a URL, which means not asking them to install Python first — and on a
managed machine, running an unsigned executable is often prohibited outright.

`Dockerfile` and `render.yaml` are all that is needed. There is nothing to install
locally: Render builds the image on its own builders and everything below is done in a
browser.

0. **Merge `develop` into `main` first.** `render.yaml` sets `branch: main`, and a
   blueprint has nothing to build until `main` carries the `Dockerfile`. Because `main`
   is the deployment branch, that pull request is also what publishes each new version;
   `ci.yml` runs on it, so the tests have passed on exactly that content first.
1. **Render → New → Blueprint**, and pick this repository. `render.yaml` defines the
   service, so there is no dashboard configuration to remember or reproduce. Render
   reads it, shows what it will create, and asks for confirmation.
2. **Watch the first build.** It should end with the two assertions from the Dockerfile
   in the log — that the interface reached the wheel, and that `metas_unclib` is *not*
   in the image — and then `/healthz` going green. First build is a few minutes; later
   ones reuse cached layers.
3. **Check the health endpoint** at `https://<service>.onrender.com/healthz` — for this
   deployment, <https://verifiable-credentials-4-qi.onrender.com/healthz>. It reports
   ` »engine »: « linprop »`, which is the confirmation that the deployment is computing
   with the engine it is licensed to ship, and the commit it is running. Compare that
   commit against `main`: a green dashboard says a build succeeded, not that the build
   was the one just merged. The endpoint answers only after the lifespan warm-up has
   built and signed the world, so a 200 means the process can serve rather than that a
   port opened.
4. **Settings → Custom Domains**, add the hostname, then create the DNS records below.
   Certificates are issued and renewed automatically, and HTTP is redirected to HTTPS.

| Type | Name | Value | Notes |
| — | — | — | — |
| `CNAME` | `vc` (or `www`) | `<service>.onrender.com.` | What Render wants for any non-apex name. |
| `ALIAS` / `ANAME` | `@` | `<service>.onrender.com.` | For the bare domain, if the registrar supports it. Preferred: no address is hard-coded. |
| `A` | `@` | Render’s load-balancer address | Fallback where `ALIAS` is unavailable. Take the address from the dashboard rather than from here. |
| `AAAA` | any | — | **Delete them.** Render is IPv4-only, and a stale `AAAA` is the usual reason a certificate never issues. |

Pick one canonical hostname and redirect the other, so the demonstration has one address.

Two things worth knowing before the link circulates. The free instance spins down after
about fifteen minutes idle and takes the better part of a minute to wake, which is the
wrong behaviour for a link opened live in a meeting — `plan: starter` in `render.yaml`
removes it. And crawlers are asked off by default (`VCQI_ALLOW_INDEXING=0`), because this
names METAS, BIPM and PTB/DKD while inventing their documents; allowing indexing is a
deliberate decision rather than a default.

Environment variables, all optional and all defaulting to local behaviour:

| Variable | Default | Effect |
| — | — | — |
| `VCQI_HOST` | `127.0.0.1` | Bind address. The container sets `0.0.0.0`. |
| `PORT` | `8000` | Managed hosts assign this. |
| `VCQI_PUBLIC` | `0` | Turns on the request limits, drops the API docs, and refuses to start if the interface is missing from the package. |
| `VCQI_RATE_LIMIT_BURST` | `0` (off) | Token bucket size, per client address. |
| `VCQI_RATE_LIMIT_PER_SECOND` | `1.0` | Refill rate. |
| `VCQI_MAX_BODY_BYTES` | `262144` | Largest request body parsed. |
| `VCQI_ALLOW_INDEXING` | `0` | Whether `robots.txt` and `X-Robots-Tag` invite crawlers. |
| `VCQI_ENGINE` | unset | Set to `linprop` to force the deployed uncertainty engine locally. |

`ARCHITECTURE.md` records why `/api/keys/*` is safe to expose and what changed when the
old answer — « the server binds to localhost » — stopped being true.