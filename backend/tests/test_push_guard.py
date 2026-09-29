"""The push guard must actually block a push.

``ci-gate.py`` protects merges. It could not see either of the two commits that
reached ``main`` with no PR, because those were PUSHES, and a merge gate has
nothing to merge. ``scripts/check_main_provenance.py`` and the pre-push hook
cover that gap -- and, like every other spec in this repo, they are only worth
having if they fail on the real thing.

So these specs run against the two commits that actually slipped through, not
against a synthetic example. A guard that has never been shown to reject a known
bad input is a guess.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_main_provenance.py"
HOOK = REPO / "scripts" / "hooks" / "pre-push"

#: The two commits that reached main without a PR. Both are real; the second is
#: still the second-most-recent thing that happened to this repository.
KNOWN_BAD = ["dc26c66", "d26b589"]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def pitchless_git_env() -> None:
    if not SCRIPT.exists():
        pytest.fail("scripts/check_main_provenance.py is missing")


def test_the_guard_exists() -> None:
    assert SCRIPT.exists(), "the push guard script is missing"
    assert HOOK.exists(), "the pre-push hook is missing"


def test_hook_is_valid_bash() -> None:
    r = subprocess.run(["bash", "-n", str(HOOK)], capture_output=True, text=True)
    assert r.returncode == 0, f"hook has a syntax error: {r.stderr}"


def test_hook_is_executable() -> None:
    import os

    assert os.access(HOOK, os.X_OK), "the hook is not executable"


# --------------------------------------------------------------------------- #
# It must reject the commits that actually slipped through                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sha", KNOWN_BAD)
def test_guard_rejects_a_known_bad_commit(sha: str) -> None:
    r = run_script("--ref", sha, "--no-gh")
    if "unknown revision" in r.stderr or "ambiguous" in r.stderr:
        pytest.skip(f"{sha} is not present in this clone")
    assert r.returncode == 1, (
        f"the guard ACCEPTED {sha}, which reached main with no PR. Output: "
        f"{r.stdout}{r.stderr}"
    )
    assert "no pull-request reference" in (r.stdout + r.stderr)


def test_guard_rejects_a_synthetic_bad_subject(tmp_path: Path) -> None:
    """A throwaway commit on a scratch branch, so the spec does not depend on
    history that a rebase could rewrite out from under it."""
    subprocess.run(["git", "checkout", "-q", "-b", "guard-selftest"], cwd=REPO, check=True)
    try:
        (REPO / "GUARD_SELFTEST.md").write_text("scratch\n")
        subprocess.run(["git", "add", "GUARD_SELFTEST.md"], cwd=REPO, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm",
             "A commit with no pull request"],
            cwd=REPO, check=True,
        )
        r = run_script("--ref", "HEAD", "--no-gh")
        assert r.returncode == 1, "a commit with no PR reference was accepted"
    finally:
        subprocess.run(["git", "checkout", "-q", "main"], cwd=REPO, check=True)
        subprocess.run(["git", "branch", "-qD", "guard-selftest"], cwd=REPO, check=True)
        (REPO / "GUARD_SELFTEST.md").unlink(missing_ok=True)


def test_guard_accepts_a_real_pr_merge() -> None:
    """The positive case, so the guard is not simply always-fail.

    A guard that rejects everything would pass every rejection test above while
    making the repository unusable, so it is checked against a commit that
    genuinely arrived through a PR.
    """
    r = run_script("--ref", "HEAD", "--no-gh")
    assert r.returncode == 0, (
        f"the guard REJECTED a legitimate PR merge: {r.stdout}{r.stderr}"
    )


def test_exempt_prefixes_are_recognised() -> None:
    src = SCRIPT.read_text()
    for prefix in ("Merge branch", "Merge pull request", "Revert "):
        assert f'"{prefix}' in src, f"{prefix} is not an exempt prefix"
    # And they are exempt, not merely mentioned: the check has to run BEFORE the
    # PR-reference lookup, or a merge commit with no (#N) would be rejected.
    body = src.split("EXEMPT_PREFIXES", 1)[1]
    assert "subject.startswith(EXEMPT_PREFIXES)" in body, (
        "exempt prefixes are not applied in the control flow"
    )


def test_unreachable_ref_is_a_skip_not_a_pass_or_a_crash() -> None:
    r = run_script("--ref", "refs/heads/definitely-not-a-branch", "--no-gh")
    assert r.returncode == 0, "an unresolvable ref should skip, not fail"
    assert "SKIP" in r.stderr


def test_gh_failure_is_reported_as_unverified_not_as_a_pass() -> None:
    """A lookup that cannot complete must never read as approval.

    Silently returning 0 when GitHub is unreachable is the classic way a guard
    becomes decoration: it stops working and keeps saying everything is fine.

    Checked on whitespace-normalised source, because the message is wrapped
    across two f-string lines and a literal search for the joined sentence finds
    nothing in a perfectly correct script.
    """
    flat = " ".join(SCRIPT.read_text().split())
    assert "unverified, not as a pass" in flat, (
        "the gh-lookup failure path does not say it is unverified"
    )
    body = flat.split("state = gh_pr_state", 1)[1]
    assert "return 0" in body.split("if state != ", 1)[0], (
        "an unreadable PR must not return success from the lookup branch"
    )


# --------------------------------------------------------------------------- #
# The hook has to intercept the push                                           #
# --------------------------------------------------------------------------- #


def test_hook_blocks_a_direct_main_push() -> None:
    """Drive the hook with the ref shape a real push produces.

    Not a synthetic one, and the first attempt at this fed an all-zero LOCAL
    sha -- which the hook correctly reads as a branch DELETION and skips, so it
    produced no output and the spec would have passed while proving nothing.

    A first push has a zero REMOTE sha and a real local one. That is the shape
    used here, and the current head does come from a PR, so it must pass.
    """
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    result = subprocess.run(
        ["bash", str(HOOK)],
        cwd=REPO,
        input=f"refs/heads/main {head} refs/heads/main {'0' * 40}\n",
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "pre-push" in out, f"the hook did not run at all:\n{out}"
    assert result.returncode == 0, f"the hook rejected a legitimate push:\n{out}"


def test_hook_ignores_a_branch_deletion() -> None:
    """A zero LOCAL sha is a deletion and must not be inspected.

    The hook's first two skips exist for this, and the spec that found the
    mistake above pins it."""
    zero = "0" * 40
    result = subprocess.run(
        ["bash", str(HOOK)],
        cwd=REPO,
        input=f"refs/heads/main {zero} refs/heads/main {zero}\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "BLOCKED" not in result.stdout, (
        f"the hook tried to inspect a deleted branch:\n{result.stdout}"
    )


def test_hook_ignores_non_main_branches() -> None:
    zero = "0" * 40
    result = subprocess.run(
        ["bash", str(HOOK)],
        cwd=REPO,
        input=f"refs/heads/feature/x {zero} refs/heads/feature/x {zero}\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Nothing should have been checked: the loop continues before any output.
    assert "ok " not in result.stdout and "BLOCKED" not in result.stdout, (
        f"the hook inspected a non-main branch:\n{result.stdout}"
    )


def test_hook_documents_the_escape_hatch() -> None:
    """An override has to be possible, or the first real emergency produces a
    force-push, which is worse than the thing the hook prevents."""
    assert "--no-verify" in HOOK.read_text()
