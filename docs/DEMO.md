# How a judge sees this, and how you verify it

**The product is a Next.js frontend and a FastAPI backend. There is no public URL
today, which means a judge cannot use it without running it themselves. This
document is the honest answer to that, plus three deployment tiers that fix it.**

Read `DEMO-VERIFICATION.md` for what each tier actually proves. The short version:
`docker compose up` is verified, and it is the right *exit criterion* — but it is
not a *demo*, because a judge with 30 seconds and a USB port will not run it.

## The three tiers

### Tier 1 — Public URL, no backend (what a judge clicks)

Deploy the frontend alone. It works, because S6's exit criterion is that it works
with the backend **entirely absent** — and every panel is badged `Fixture` with a
reason, which is the product behaving correctly rather than degraded.

```bash
cd frontend
npx vercel --prod          # or: vercel link && vercel --prod
```

- **Set no `NEXT_PUBLIC_API_URL`.** An unset API is a supported first-class
  state; the page makes **no network requests at all** and says so.
- **What it proves:** rubric bullets 1, 2, 3, 5, 6 and the intro timeline, all
  interactive.
- **What it does not prove:** any Cloudinary call. The transformations are real
  code but are never exercised, so the panel says `Fixture` everywhere.

### Tier 2 — Public URL, live Cloudinary (the full pitch)

Same frontend, plus the backend deployed somewhere that runs a ~2 GB image
(OpenCV, SciPy, pvlib, astropy), with `CLOUDINARY_*` in the environment.

```bash
# Frontend
cd frontend && npx vercel --prod
#   NEXT_PUBLIC_API_URL = https://<your-backend-host>
# Backend (any container host; see the notes below)
docker build -f backend/Dockerfile -t veritas-backend .
docker run -p 8000:8000 -e CLOUDINARY_URL -e CLOUDINARY_API_KEY \
  -e CLOUDINARY_API_SECRET -e CLOUDINARY_CLOUD_NAME veritas-backend
```

- **What it proves:** everything, including the sponsor surface — search,
  transformations, video analysis, C2PA.
- **What it costs:** a container host and a public backend URL. **The backend
  must have CORS configured for the frontend's origin** or every panel degrades.

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
