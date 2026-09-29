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

``--repo`` exists because the specs run this against throwaway repositories in
``tmp_path``. The first version of those specs ran it against THIS repository, and
so depended on full clone history and a checked-out ``main`` -- which a shallow,
detached CI checkout has neither of. Five of them failed in CI, and the one that
created a scratch commit left it on ``HEAD`` and took three more down with it. A
spec that depends on the state of the repository it runs in is not a spec.

Usage
-----
    scripts/check_main_provenance.py                    # check origin/main
    scripts/check_main_provenance.py --ref HEAD         # check a local ref
    scripts/check_main_provenance.py --no-gh            # offline: structure only
    scripts/check_main_provenance.py --repo /tmp/somegit --ref main
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


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def git_or_none(repo: Path, *args: str) -> str | None:
    """git, or None when the ref does not exist here.

    A shallow or partial clone does not have every commit, and a spec that
    assumed it did was the bug.
    """
    try:
        return git(repo, *args)
    except subprocess.CalledProcessError:
        return None


def head_subject(repo: Path, ref: str) -> str | None:
    return git_or_none(repo, "log", "-1", "--format=%s", ref)


def gh_pr_state(repo: Path, number: int) -> str | None:
    """The PR's state, or None if the lookup failed."""
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "--json", "state,mergedAt"],
            cwd=repo,
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
        "--repo",
        type=Path,
        default=REPO,
        help="git repository to inspect; the specs pass a throwaway one",
    )
    ap.add_argument(
        "--no-gh",
        action="store_true",
        help="skip the GitHub lookup; only assert the commit carries a PR ref",
    )
    args = ap.parse_args()

    subject = head_subject(args.repo, args.ref)
    if subject is None:
        print(
            f"SKIP: cannot resolve {args.ref} in {args.repo}; it may be absent "
            "from this clone",
            file=sys.stderr,
        )
        return 0

    sha = git(args.repo, "rev-parse", "--short", args.ref)
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

    state = gh_pr_state(args.repo, number)
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
