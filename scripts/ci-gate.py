#!/usr/bin/env python3
"""Refuse to report success unless every check on a PR passed.

Written after `gh pr checks <n> | tail -3` truncated the list and hid a failing
e2e job, so a PR was merged with red CI. A gate that can be misread is not a
gate, so this one exits non-zero and names the failures.

    ./scripts/ci-gate.py 23
"""

from __future__ import annotations

import json
import subprocess
import sys

BAD_BUCKETS = {"fail", "cancel", "skipping", "pending"}
BAD_STATES = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].isdigit():
        print("usage: scripts/ci-gate.py <pr-number>", file=sys.stderr)
        return 2
    pr = argv[1]

    try:
        out = subprocess.run(
            ["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        print(f"ci-gate: could not read checks for PR #{pr}: {exc.stderr.strip()}",
              file=sys.stderr)
        return 1

    try:
        checks = json.loads(out)
    except ValueError as exc:
        print(f"ci-gate: unparseable check list for PR #{pr}: {exc}", file=sys.stderr)
        return 1

    if not checks:
        print(
            f"ci-gate: PR #{pr} reports NO checks at all.\n"
            "          That is a silent pass, which is worse than a failure.",
            file=sys.stderr,
        )
        return 1

    failing = [
        c for c in checks
        if str(c.get("bucket", "")).lower() in BAD_BUCKETS
        or str(c.get("state", "")).upper() in BAD_STATES
    ]

    for c in failing:
        print(
            f"ci-gate: FAILED  {c.get('name')}  "
            f"[{c.get('bucket')}/{c.get('state')}]",
            file=sys.stderr,
        )

    if failing:
        print(f"ci-gate: {len(failing)} of {len(checks)} checks failed on PR #{pr}."
              "  NOT SAFE TO MERGE.", file=sys.stderr)
        return 1

    print(f"ci-gate: all {len(checks)} checks passed on PR #{pr}. Safe to merge.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
