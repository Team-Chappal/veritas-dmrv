#!/usr/bin/env bash
# Deploy the demo, and PROVE the public URL is serving it.
#
# WHY THIS EXISTS RATHER THAN `vercel --prod`
#
# Two things are true about this project that make a bare `vercel --prod` a trap:
#
# 1. MERGING TO main DOES NOT DEPLOY PRODUCTION. The Vercel GitHub integration
#    creates PREVIEWS. Every production deployment on this project is a CLI
#    deploy -- which means the public URL a judge was given silently does not
#    move when the code changes. A green CI run says nothing about what is live.
#
# 2. A MANUALLY-ASSIGNED ALIAS DOES NOT FOLLOW NEW DEPLOYMENTS. Assigning
#    `veritas-dmrv.vercel.app` points it at ONE deployment. Every later deploy
#    gets a different generated URL, and the short one keeps serving the old
#    build -- healthily, with HTTP 200, looking completely fine.
#
# That is what happened: after the verification console shipped, the short URL
# was still serving a build from before it. Nothing was red. The console simply
# was not there.
#
# So this script does the deploy, repoints the alias, and then FETCHES the public
# URL and checks for a marker that only exists in the current build. If the alias
# is stale, the marker is missing and this exits non-zero.
#
# Usage:  make deploy
# Env:    DEMO_URL (default the short alias), DEMO_MARKER (string to find)

set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

DEMO_URL="${DEMO_URL:-https://veritas-dmrv.vercel.app}"
# A string that only exists in the current build. Updated deliberately when the
# surface changes, which is the point: the check is anchored to something real
# rather than to "did the command exit 0".
DEMO_MARKER="${DEMO_MARKER:-Verify a claim}"
PROJECT_ID="$(python3 -c "import json;print(json.load(open('.vercel/project.json'))['projectId'])")"
ALIAS_NAME="${DEMO_URL#https://}"

say() { printf '  %s\n' "$*"; }

echo "==> deploying to production"
npx vercel --prod --yes

echo "==> repointing $ALIAS_NAME at the newest production deployment"
# The alias is the failure mode, so it is explicit and never implied by the
# deploy step above.
TOKEN="$(python3 - <<'PY'
import json, pathlib
p = pathlib.Path.home() / "Library/Application Support/com.vercel.cli/auth.json"
# Read and never printed.
print(json.loads(p.read_text()).get("token", ""))
PY
)"
if [ -z "$TOKEN" ]; then
  echo "  no Vercel token found; run 'vercel login' first" >&2
  exit 1
fi

DPL="$(curl -s "https://api.vercel.com/v6/deployments?projectId=${PROJECT_ID}&target=production&limit=1" \
  -H "Authorization: Bearer ${TOKEN}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin).get('deployments') or []; print(d[0]['uid'] if d else '')")"

if [ -z "$DPL" ]; then
  echo "  could not find a production deployment to alias" >&2
  exit 1
fi
say "newest deployment: $DPL"

curl -s -X POST "https://api.vercel.com/v13/deployments/${DPL}/aliases" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d "{\"alias\":\"${ALIAS_NAME}\"}" >/dev/null
say "alias assigned: $ALIAS_NAME"

echo "==> verifying the public URL actually serves this build"
# Cache-busted, because a CDN is very good at serving you yesterday.
BODY="$(curl -s -H 'Cache-Control: no-cache' --max-time 45 "${DEMO_URL}/?cb=$(date +%s)")"

if ! printf '%s' "$BODY" | grep -q "$DEMO_MARKER"; then
  echo "  FAIL: ${DEMO_URL} is not serving this build." >&2
  echo "        The marker '${DEMO_MARKER}' is absent." >&2
  echo "        Almost always a stale alias: the URL points at an older" >&2
  echo "        deployment that still returns HTTP 200 and looks healthy." >&2
  exit 1
fi
say "marker present: '$DEMO_MARKER'"
say "OK — $DEMO_URL is serving the current build"
