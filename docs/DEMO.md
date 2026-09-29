# How a judge sees this, and how you verify it

**The product is a Next.js frontend and a FastAPI backend. There is no public URL
today, which means a judge cannot use it without running it themselves. This
document is the honest answer to that, plus three deployment tiers that fix it.**

Read `DEMO-VERIFICATION.md` for what each tier actually proves. The short version:
`docker compose up` is verified, and it is the right *exit criterion* — but it is
not a *demo*, because a judge with 30 seconds and a USB port will not run it.

## Tier 0 — a folder of files (no server, no host, no Node)

The single most robust option, and the one to reach for when the network is the
thing you do not trust.

The app is **already fully static** — `next build` reports *"prerendered as
static content"*. So it can be exported to a directory that serves from
anything:

```bash
make demo-export
cd frontend/out && python3 -m http.server 3200
# http://localhost:3200  — 1.1 MB, no Node required to SERVE it
```

Upload `frontend/out/` to any static host, or hand a judge the folder and a
`python3 -m http.server` command. Verified on 2026-09-29: index, service worker
and manifest all serve 200 from a plain file server, and no `localhost:8000`
appears anywhere in the bundle.

Production is untouched — the export is opt-in via `VERITAS_STATIC_DEMO=1`
inside `next.config.mjs`. Two earlier approaches were abandoned and are recorded
in that file: `next build` has no `--config` flag, and Next 15's programmatic API
does not expose `build()`. Neither is worth a second config file that can drift
from the first.

## The three tiers

### Tier 1 — Public URL, no backend (what a judge clicks)

Deploy the frontend alone. It works, because S6's exit criterion is that it works
with the backend **entirely absent** — and every panel is badged `Fixture` with a
reason, which is the product behaving correctly rather than degraded.

```bash
cd frontend && npx vercel --prod
```

**DEPLOYED 2026-09-29:** **https://veritas-dmrv.vercel.app**
— `HTTP 200`, 83,787 bytes, 220 ms, service worker and manifest both 200, all six
panels present in the served HTML, and no API URL anywhere in the delivered
bundle. Verified by fetching the deployment, not by trusting the CLI's success
message.

### The URL was long because the project was named `frontend`

Vercel generated `frontend-<random>-<team>.vercel.app`. Renaming the project to
`veritas-dmrv` and assigning the alias gives the short form above.

**The short URL was initially unreachable to a judge.** It answered `302` to a
Vercel login, because the project carried `ssoProtection:
all_except_custom_domains` — Vercel Authentication, on by default on the
account.

That is the worst possible order to discover it in: the long URL was public and
the short one was not. A better-looking link that nobody outside the team can
open is worse than a long link that works, and no amount of checking the long one
would have found it.

Disabling authentication is correct **here**, because the bundle is a public
static artefact with fixture data and no secret in it. It is **not** correct for
a build with real credentials behind it — that is the Tier 2 caveat, and it is
worth stating plainly: a short public URL is not a substitute for not leaking
keys.

**`vercel.json` must be in `frontend/`, not the repo root.** It was committed at
the root and Vercel ignored every line of it without a word — `vercel build`
simply reported *"Detected Next.js (Build Command: next build, Output Directory:
Next.js default)"*, which is the *default*, not the committed config. A config in
the wrong directory is not a build failure; it is a build that quietly uses
somebody else's idea of the build command. A spec now pins the location.

**Known local-only wrinkle:** `vercel build` on this machine fails with
`EALLOWSCRIPTS` during `npm ci`. That is the user's `~/.npmrc` carrying an
`allow-scripts=` list, which the Vercel CLI turns into a flag npm 12 rejects in a
project-scoped install. Plain `npm ci` in the same directory is fine, and the
deployed build runs on Vercel's own infrastructure — so it is a pre-flight
artefact and not a project defect. Worth knowing before someone chases it.

- **Set no `NEXT_PUBLIC_API_URL`.** An unset API is a supported first-class
  state; the page makes **no network requests at all** and says so.
- **To re-point a deployed build at a different backend, set
  `window.__VERITAS_API_URL__` before the bundle runs** (a one-line inline
  script). `NEXT_PUBLIC_*` is inlined at build time, so without this a wrong
  backend URL means a new deploy. Tier 1 and Tier 2 are then the same artefact
  with one value changed, which is why a demo and a deployment do not drift.
- **What it proves:** rubric bullets 1, 2, 3, 5, 6 and the intro timeline, all
  interactive.
- **What it does not prove:** any Cloudinary call. The transformations are real
  code but are never exercised, so the panel says `Fixture` everywhere.

### Tier 2 — Public URL, live Cloudinary (the full pitch)

Same frontend, plus the backend deployed to a container host. `fly.toml` and
`render.yaml` are committed; either works.

```bash
fly launch --no-deploy --config fly.toml --copy-config
fly secrets set CLOUDINARY_URL=... CLOUDINARY_API_KEY=... \
                  CLOUDINARY_API_SECRET=... CLOUDINARY_CLOUD_NAME=... \
                  CORS_ALLOW_ORIGINS=https://veritas-dmrv.vercel.app \
                  RATE_LIMIT_PER_MINUTE=600
fly deploy

# then, in the Vercel project, set NEXT_PUBLIC_API_URL to the Fly URL and redeploy
```

**Measured cold start: 0.87 s to serving.** pvlib is the cost (0.94 s to
import); astropy is lazy. That is why a machine that stays warm is preferred over
one that scales to zero — a demo should not open with a ten-second wait.

**`CORS_ALLOW_ORIGINS` IS NOT OPTIONAL.** The default is `*`, which on a laptop
is a convenience and on a deployed machine is an unauthenticated public API that
anybody can script against, driving this deployment's Cloudinary quota. The
mutating routes carry JWT scopes; **the read routes deliberately do not, because
they are the demo surface a judge is meant to poke** — so CORS is the only
control on them, which is exactly why it moved from a hardcoded literal to
`Settings.cors_allow_origins` with 9 specs.

**Raise the rate limit.** `RATE_LIMIT_PER_MINUTE` defaults to 60. One page load
is ~6 calls, so 60/min is **ten page loads a minute** — and several judges
opening the link at once is the expected case here, not the abusive one.

### The security model, stated once

An earlier note in this document said authentication should be re-enabled on the
Vercel project when the backend goes live. **That is wrong, and following it
would break the demo.**

- The **frontend stays public.** It is a static bundle. Putting auth on it means
  a judge gets a login page instead of the product, which is the thing this
  whole tier exists to provide.
- The **backend is restricted by CORS**, to the frontend's origin only, plus JWT
  on mutating routes and rate limiting on everything.
- **Credentials never leave the backend.** They are host environment variables.
  A frontend bundle with a Cloudinary key in it is the one mistake that makes
  every other control decorative.

The real risk in Tier 2 is not the URL being public. It is a credential ending
up in the bundle, which is why `NEXT_PUBLIC_*` is the only place any URL goes and
why the deployment spec greps the built bundle for a backend URL.

### Tier 3 — One command, no hosting (best for a live stage)

Publish the image to GHCR, then a judge runs one line:

```bash
docker run -p 3000:3000 -p 8000:8000 ghcr.io/<owner>/veritas-demo:latest
```

`make publish-demo` builds and pushes it; `.github/workflows/publish-demo.yml`
does it on every tagged release. No clone, no build, no account.

- **What it proves:** the whole stack, exactly as verified locally.
- **What it needs:** Docker on the judge's machine.

## What to do in the room, in order

1. **Lead with the running product, not the market hook.** Slides 1–3 of
   `docs/14-HACKATHON-PITCH-DECK-AND-PRESENTATION.md` are the demo, and they
   open with rubric 3 and 5 because those *show* something working.
2. **If the network dies, say so and press the Demo Cache toggle.** Every panel is
   badged `Fixture`; the interface is designed so a degraded demo is visibly
   degraded, and a presenter who hides that is contradicting their own product.
3. **If a panel is badged `Fixture`, say it out loud.** The pitch's claims-audit
   table is the same discipline.
4. **Never promise an EUDR Article 9 dossier.** The validator is not implemented.
   The pitch says this explicitly, and `test_pitch_claims.py` enforces it.

## Deploying, and why `vercel --prod` alone is a trap

**`make deploy`.** Not `npx vercel --prod`, for two reasons that have nothing to
do with Vercel being difficult:

**1. Merging to `main` does not deploy production.** The GitHub integration
creates *previews*. Every production deployment on this project is a CLI one,
which means the URL a judge was given **silently does not move when the code
changes** — and a green CI run says nothing about what is live. That is a
property of the setup, not a bug, and it has to be designed around.

**2. A manually-assigned alias does not follow new deployments.** Assigning
`veritas-dmrv.vercel.app` points it at *one* deployment. Every later deploy gets
a fresh generated URL, and the short one keeps serving the old build — **with
HTTP 200, looking completely healthy.**

That is exactly what happened. The verification console shipped, the new build
had it, the generated URL served it, and the short URL a judge had been given
served a build from *before* it. Nothing was red anywhere. The console was simply
not there, and the failure mode was a perfectly healthy page missing the one
thing it exists to demonstrate.

So `scripts/deploy_demo.sh` deploys, **repoints the alias explicitly**, and then
**fetches the public URL and looks for a marker that only exists in the current
build**. A stale alias exits non-zero with the reason. The marker is
`Verify a claim`, and a spec asserts that string still exists in the source — so
renaming the console makes the deploy fail for the *right* reason instead of
silently.

Verified by running it: with a marker that cannot exist, it fails and says the
URL is not serving this build.

## What a judge actually does with it

One box, near the top: **type a claim, get a verdict.** Latitude, longitude, the
time a photograph claims, and the bearing its shadow points. Press *Verify*.

It runs **entirely in the browser** — the deployed site has no backend, so the
solar arithmetic is computed client-side with the NOAA algorithm, cross-checked
against ten committed pvlib vectors to within **0.089° of azimuth and 0.007° of
elevation**. Two independent implementations agreeing is the reason to believe a
number shown to a judge.

The output is a verdict, the geometry behind it, and an audit receipt. Three
outcomes, all first-class:

| Preset | What it shows |
| :-- | :-- |
| A genuine capture | Consistent — 2° off, inside the 12° tolerance |
| A timestamp edited by six hours | The shadow is 173° from where it must be |
| A case it refuses to judge | **The shadow reading is perfect (0.0° off) and the verdict is still withheld**, because at 5° of elevation a correct shadow is not evidence |

That third one is the most valuable thing on the page. A verification tool that
only answers yes or no invites the reading that it is accusing; this one declines
to answer when answering would be a guess.

The presets are the **committed pvlib vectors**, not numbers chosen to look good,
so the console, the screenshot and the audit receipt cannot disagree.

### What it deliberately does not claim

The receipt's last line says it: *shadow coherence is one consistency check. A pass
is not proof of authenticity.* It checks whether the light in the frame could have
been cast the way the metadata says — nothing else. A "consistent" result is not a
finding that a photograph is real.

## The honest state of the demo surface

| Surface | Tier 1 (no backend) | Tier 2 (live) | Verified how |
| :-- | :-- | :-- | :-- |
| Timeline (intro bullet) | works | works | 16 e2e |
| Portfolio grid (1) | works | works | 13 e2e + 500-asset load test |
| Hotspot video (2) | works | works | 14 e2e |
| Split slider (3) | works | works | 16 e2e |
| Campaign studio (4) | works, PDF plan-gated | works, PDF plan-gated | 13 e2e; `f_pdf` is paid-plan |
| Semantic search (5) | works, lexical | works, lexical | 15 e2e |
| Provenance (6) | works, all Fixture | works, live | 9 e2e + 19 live harness checks |
| Webhook signature | not shown | unconfirmed | documented scheme, never observed live |

The one surface a judge could break is the **webhook signature**: it is
implemented to Cloudinary's documented scheme but has never been confirmed
against a real notification, because that needs a publicly reachable callback
URL. If a judge asks, the answer is the honest one, and it is in
`docs/RUBRIC-TRACEABILITY.md` §3.
