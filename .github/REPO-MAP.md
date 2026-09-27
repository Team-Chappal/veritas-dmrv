# Repository Map

**`j4yop/veritas-dmrv`** — VERITAS dMRV, an AI-powered impact & sustainability
media intelligence platform.

Built for **Code Cubicle 6.0 — Problem Statement 02 (Cloudinary)**.

## Where to start

| If you want to… | Read |
| :--- | :--- |
| Understand the problem and what it answers | `docs/VERITAS-CONSOLIDATED-BRIEF.md` |
| See what is being built, in order | `EXECUTION-PLAN.md` |
| Check a claim before trusting it | `scripts/verify_docs.py` + `docs/03-SYSTEM-DESIGN.md` |
| Run anything | `README.md` → `make bootstrap && make test` |

## Status

| Stage | Scope | State |
| :-- | :--- | :--- |
| **S0** | Repo, pinned deps, CI, doc linter, Docker targets | done |
| **S1** | Solar ephemeris, allometry, VM0047, forgery signals, pHash dedup, mock server | done — 105 tests, 94% coverage |
| **S2** | SIFT/MAGSAC++ homography, TPS fallback, radiometric, GLI+Otsu | next |
| **S3** | Auto-tagging, semantic discovery, grounded summaries | planned |
| **S4** | Cloudinary schema, transformation engine, scale corpus | planned |
| **S5** | REST API layer | planned |
| **S6** | Next.js console, PWA | scaffolded (shell only) |
| **S7** | Playwright, Docker, load test, pitch | planned |

## Design commitments

- **No hand-written physics.** Every solar fixture is generated from `pvlib`.
  `make fixtures-check` fails CI if the committed file is stale.
- **Abstention is a feature.** Below 10° of solar elevation the shadow azimuth
  is terrain-dominated, so the detector declines to accuse and routes to human
  review.
- **Proxies are labelled as proxies.** The crown-projection DBH estimate is
  never presented as a field survey.
- **Heuristics are labelled as heuristics.** Only signals measured to separate
  their controls may auto-quarantine. Screen-replay detection is advisory and
  explicitly unvalidated.
- **LLMs write prose, never verdicts.**
- **Credential absence is a supported state.** No Cloudinary key is required for
  any stage; a CI job enforces this.
- **Docs are linted like code.**

## The audit trail matters more than the features

Four substantive defects were found by checking claims instead of reading them,
and two of the findings were about the *checking itself*:

1. Every hand-written solar test vector was outside its own tolerance; one was
   physically impossible by 49°. The demo's flagship fixture cleared the fraud
   threshold by 2.56°.
2. The design document's solar azimuth derivation contradicted the code beside
   it — the math was wrong, the code was right.
3. A "correction" to the Chave allometry coefficient was itself wrong and had to
   be withdrawn after checking against the R `BIOMASS` reference implementation.
4. The screen-replay Moiré threshold was unachievable by the phenomenon it
   claims to detect, and was *inverted* — a clean natural photograph scored
   higher than a genuine Moiré pattern.

Each is documented where it happened, with the reasoning, rather than quietly
fixed. `README.md` §3 and the consolidated brief §9.1 carry the full record.
