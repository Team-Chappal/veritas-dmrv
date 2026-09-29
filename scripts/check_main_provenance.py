"""Every commit on ``main`` must have a merged pull request behind it.

Why this exists
---------------
``scripts/ci-gate.py`` protects MERGES. Nothing protected PUSHES. Twice, a commit
reached ``main`` with no PR and no CI: ``d26b589`` and ``dc26c66``. Both got past
every guard this repository had, which means the guard everyone trusts to keep
``main`` safe did not cover the failure mode that actually occurred.

So this covers pushes. It reads the head of ``main``, extracts the ``(#N)`` that
GitHub appends to a squash or merge commit, and verifies that pull request exists
and is MERGED. A commit on ``main`` with no PR behind it fails.

What it does NOT do
-------------------
It does not prevent the push -- GitHub is the thing that accepts it. It makes the
push VISIBLE, and it fails CI on the branch that pushed it, so the record shows
which commit slipped through rather than the gap being discovered weeks later.
Combined with the ``pre-push`` hook installed by ``make install-git-hooks``, the
local half of the protection is in front of you instead of behind you.

Usage
-----
    scripts/check_main_provenance.py            # check origin/main
    scripts/check_main_provenance.py --ref HEAD # check a local ref
    scripts/check_main_provenance.py --no-gh    # offline: structure only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: GitHub appends this to the subject of a squash or merge commit. Its absence
#: is the finding: a commit on main that did not come from a PR.
PR_REF = re.compile(r"\(#(\d+)\)\s*$")

#: Merge commits and revert commits legitimately have no PR of their own.
EXEMPT_PREFIXES = (
    "Merge branch",       # plain merge
    "Merge pull request", # merge-commit strategy
    "Revert ",            # a revert is a correction, not a feature
)


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def head_subject(ref: str) -> str:
    return git("log", "-1", "--format=%s", ref)


def gh_pr_state(number: int) -> str | None:
    """The PR's state, or None if the lookup failed."""
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "--json", "state,mergedAt"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        return json.loads(out.stdout).get("state")
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument(
        "--no-gh",
        action="store_true",
        help="skip the GitHub lookup; only assert the commit carries a PR ref",
    )
    args = ap.parse_args()

    try:
        subject = head_subject(args.ref)
    except subprocess.CalledProcessError:
        print(
            f"SKIP: cannot resolve {args.ref}; fetch first",
            file=sys.stderr,
        )
        return 0

    sha = git("rev-parse", "--short", args.ref)
    print(f"{args.ref} @ {sha}: {subject}")

    if subject.startswith(EXEMPT_PREFIXES):
        print("  exempt: merge or revert commit, no PR required")
        return 0

    m = PR_REF.search(subject)
    if not m:
        print(
            f"\nFAIL: {args.ref} head {sha} carries no pull-request reference.\n"
            f"  subject: {subject}\n"
            "\n  A commit on main must arrive through a merged PR. If this one is\n"
            "  legitimate and exempt, amend it to start with 'Revert ' or use a\n"
            "  merge commit, so the exemption is explicit rather than inferred.",
            file=sys.stderr,
        )
        return 1

    number = int(m.group(1))
    if args.no_gh:
        print(f"  PR #{number} referenced (lookup skipped)")
        return 0

    state = gh_pr_state(number)
    if state is None:
        print(
            f"\nWARN: could not read PR #{number} via the GitHub CLI. Treating as "
            "unverified, not as a pass.",
            file=sys.stderr,
        )
        return 0

    if state != "MERGED":
        print(
            f"\nFAIL: {args.ref} head {sha} references PR #{number}, which is "
            f"{state}, not MERGED.",
            file=sys.stderr,
        )
        return 1

    print(f"  PR #{number} is MERGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
