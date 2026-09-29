"""The push guard must actually block a push.

``ci-gate.py`` protects merges. It could not see either of the two commits that
reached ``main`` with no PR, because those were PUSHES, and a merge gate has
nothing to merge. ``scripts/check_main_provenance.py`` and the pre-push hook
cover that gap -- and, like every other spec in this repo, they are only worth
having if they fail on the real thing.

HERMETIC BY CONSTRUCTION

The first version of this file ran the guard against **this** repository, which
meant it depended on full clone history and a checked-out ``main``. CI is a
shallow, detached checkout and has neither, so five specs failed there. Worse,
one of them created a scratch commit, failed to check ``main`` back out, left the
commit on ``HEAD``, and took three further specs down with it.

A spec that depends on the state of the repository it runs in is not a spec. So
every case here builds a throwaway repository in ``tmp_path`` and asserts against
it. Nothing outside ``tmp_path`` is read, written or committed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_main_provenance.py"
HOOK = REPO / "scripts" / "hooks" / "pre-push"
ZERO = "0" * 40


def sh(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A throwaway git repository with one legitimate PR-merge commit on main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    sh("git", "config", "user.name", "sandbox", cwd=repo)
    sh("git", "config", "user.email", "sandbox@example.invalid", cwd=repo)
    (repo / "file.txt").write_text("one\n")
    sh("git", "add", "file.txt", cwd=repo)
    sh("git", "commit", "-qm", "A legitimate PR merge (#12)", cwd=repo)
    return repo


def commit(repo: Path, subject: str, filename: str = "x.txt") -> str:
    (repo / filename).write_text(subject + "\n")
    sh("git", "add", "-A", cwd=repo)
    sh("git", "commit", "-qm", subject, cwd=repo)
    return sh("git", "rev-parse", "HEAD", cwd=repo)


@pytest.fixture
def stub_gh(tmp_path: Path) -> Path:
    """A ``gh`` on PATH that always reports MERGED.

    Needed because the sandbox has no GitHub remote, so the hook's positive path
    is otherwise unreachable -- and a guard with no test that lets anything
    through cannot be told apart from one that always fails.
    """
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    (stub_dir / "gh").write_text('#!/usr/bin/env bash\necho MERGED\n')
    (stub_dir / "gh").chmod(0o755)
    return stub_dir


def run_hook_with_gh(hook_env: Path, repo: Path, stdin: str):
    env = dict(os.environ)
    env["PATH"] = f"{hook_env}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, input=stdin, capture_output=True, text=True, env=env
    )


def guard(repo: Path, ref: str = "HEAD", *extra: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--ref", ref, "--no-gh", *extra],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


def run_hook(repo: Path, stdin: str):
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, input=stdin, capture_output=True, text=True
    )


# --------------------------------------------------------------------------- #
# The guard, on a synthetic main                                               #
# --------------------------------------------------------------------------- #


def test_the_guard_rejects_a_commit_with_no_pr(sandbox: Path) -> None:
    """The exact failure: a commit that reached main with no PR behind it."""
    commit(sandbox, "Close the stage: fix the status table")
    r = guard(sandbox)
    assert r.returncode == 1, f"a no-PR commit was accepted:\n{r.stdout}{r.stderr}"
    assert "no pull-request reference" in (r.stdout + r.stderr)


def test_the_guard_accepts_a_real_pr_merge(sandbox: Path) -> None:
    """The positive case, so the guard is not simply always-fail.

    A guard that rejected everything would pass every rejection spec above while
    making the repository unusable.
    """
    r = guard(sandbox)
    assert r.returncode == 0, f"a legitimate PR merge was rejected:\n{r.stdout}{r.stderr}"


@pytest.mark.parametrize(
    "subject",
    [
        "Merge branch 'main' into feature",
        "Merge pull request #31 from someone/branch",
        'Revert "Fix the status table (#30)"',
    ],
)
def test_merge_and_revert_commits_are_exempt(sandbox: Path, subject: str) -> None:
    """Exempt means exempt, not merely mentioned.

    A merge commit carries no ``(#N)`` of its own, so if the exemption were not
    applied in the control flow the guard would block every merge.
    """
    commit(sandbox, subject)
    r = guard(sandbox)
    assert r.returncode == 0, f"{subject!r} was rejected:\n{r.stdout}{r.stderr}"


def test_exempt_commits_are_reported_as_exempt(sandbox: Path) -> None:
    commit(sandbox, "Merge pull request #7 from x/y")
    assert "exempt" in guard(sandbox).stdout


def test_absent_ref_is_a_skip_not_a_pass_or_a_crash(sandbox: Path) -> None:
    r = guard(sandbox, ref="refs/heads/not-a-branch")
    assert r.returncode == 0, "an unresolvable ref should skip, not fail"
    assert "SKIP" in r.stderr


def test_the_real_offending_subject_would_be_rejected(sandbox: Path) -> None:
    """The exact subject line that reached main without a PR, reconstructed.

    Not a reference to a commit that may or may not be in this clone -- which is
    what made the first version of this file fail in CI -- but the text itself,
    which is the thing being detected.
    """
    commit(sandbox, "Close S7: correct a status table that had already gone stale")
    r = guard(sandbox)
    assert r.returncode == 1
    assert "Close S7" in r.stdout


# --------------------------------------------------------------------------- #
# The hook                                                                    #
# --------------------------------------------------------------------------- #


def test_hook_is_valid_bash() -> None:
    r = subprocess.run(["bash", "-n", str(HOOK)], capture_output=True, text=True)
    assert r.returncode == 0, f"hook has a syntax error: {r.stderr}"


def test_hook_is_executable() -> None:
    assert os.access(HOOK, os.X_OK), "the hook is not executable"


def test_hook_blocks_a_commit_with_no_pr(sandbox: Path) -> None:
    """Driven with the ref shape a real push produces.

    The first attempt fed the hook an all-zero LOCAL sha, which the hook
    correctly reads as a branch DELETION and skips -- so it produced no output and
    the spec passed while proving nothing. A first push has a zero REMOTE sha and
    a real local one; that is the shape used here and below.
    """
    head = commit(sandbox, "A commit with no pull request behind it")
    r = run_hook(
        sandbox, f"refs/heads/main {head} refs/heads/main {ZERO}\n"
    )
    out = r.stdout + r.stderr
    assert "BLOCKED" in out, f"the hook did not block a no-PR commit:\n{out}"
    assert r.returncode == 1, "the hook allowed a no-PR commit through"


def test_hook_fails_closed_when_the_pr_cannot_be_verified(sandbox: Path) -> None:
    """A sandbox has no GitHub remote, so the PR state is unreachable.

    The hook BLOCKS -- fail closed, because the one case that matters most is a
    commit whose PR cannot be confirmed. But it must SAY that is what happened:
    an early version warned and continued when ``gh`` was unavailable while
    blocking on a genuinely unmerged PR, so the hook was advisory about exactly
    the case it exists to catch.

    "I could not check" and "the check failed" are different claims, and a
    repository with no remote must not look identical to a policy violation.
    """
    head = commit(sandbox, "A legitimate PR merge (#12)")
    r = run_hook(sandbox, f"refs/heads/main {head} refs/heads/main {ZERO}\n")
    out = r.stdout + r.stderr
    assert r.returncode == 1, "the hook let an unverifiable commit through"
    assert "could not be resolved" in out, (
        f"the hook did not distinguish unverifiable from rejected:\n{out}"
    )
    assert "not MERGED" not in out, (
        f"an unreachable PR was reported as a genuine rejection:\n{out}"
    )
    assert "gh auth status" in out, "the hook did not say how to fix the check"


def test_hook_lets_a_verified_pr_commit_through(stub_gh: Path, tmp_path: Path) -> None:
    """The positive case, with the PR genuinely confirmed as merged."""
    repo = tmp_path / "stubbed"
    repo.mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    sh("git", "config", "user.name", "s", cwd=repo)
    sh("git", "config", "user.email", "s@e.invalid", cwd=repo)
    (repo / "f.txt").write_text("x\n")
    sh("git", "add", "f.txt", cwd=repo)
    sh("git", "commit", "-qm", "A legitimate PR merge (#12)", cwd=repo)
    head = sh("git", "rev-parse", "HEAD", cwd=repo)

    r = run_hook_with_gh(
        stub_gh, repo, f"refs/heads/main {head} refs/heads/main {ZERO}\n"
    )
    out = r.stdout + r.stderr
    assert "BLOCKED" not in out, f"the hook blocked a verified PR merge:\n{out}"
    assert r.returncode == 0, f"the hook failed a verified PR merge:\n{out}"
    assert "ok " in out


def test_hook_ignores_a_branch_deletion(sandbox: Path) -> None:
    """A zero LOCAL sha is a deletion. The first skip the hook makes."""
    r = run_hook(sandbox, f"refs/heads/main {ZERO} refs/heads/main {ZERO}\n")
    assert r.returncode == 0
    assert "BLOCKED" not in r.stdout, (
        f"the hook tried to inspect a deleted branch:\n{r.stdout}"
    )


def test_hook_ignores_non_main_branches(sandbox: Path) -> None:
    head = commit(sandbox, "A commit with no pull request behind it")
    r = run_hook(
        sandbox, f"refs/heads/feature/x {head} refs/heads/feature/x {ZERO}\n"
    )
    assert r.returncode == 0
    assert "BLOCKED" not in r.stdout, (
        f"the hook inspected a non-main branch:\n{r.stdout}"
    )


def test_hook_reports_what_it_checked(stub_gh: Path, tmp_path: Path) -> None:
    """A guard that passes silently teaches the reader nothing about its scope."""
    repo = tmp_path / "counted"
    repo.mkdir()
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    sh("git", "config", "user.name", "s", cwd=repo)
    sh("git", "config", "user.email", "s@e.invalid", cwd=repo)
    # Three commits: the first is the remote's current head, so the push carries
    # TWO. Two commits would give a range of one, which is what made the earlier
    # version of this spec count 1 and read as a hook bug rather than bad
    # arithmetic in the spec.
    base = None
    for i, subject in enumerate(("Already on main (#1)", "Second merge (#2)", "Third merge (#3)")):
        (repo / f"f{i}.txt").write_text(subject + "\n")
        sh("git", "add", "-A", cwd=repo)
        sh("git", "commit", "-qm", subject, cwd=repo)
        if i == 0:
            # With a real remote sha the hook walks the range; with a zero one it
            # treats the push as a first push and checks only the head.
            base = sh("git", "rev-parse", "HEAD", cwd=repo)
    head = sh("git", "rev-parse", "HEAD", cwd=repo)
    r = run_hook_with_gh(stub_gh, repo, f"refs/heads/main {head} refs/heads/main {base}\n")
    assert "2 commit(s) checked" in r.stdout, (
        f"the hook did not say how many commits it checked:\n{r.stdout}"
    )


def test_hook_documents_the_escape_hatch() -> None:
    """An override has to be possible, or the first real emergency produces a
    force-push, which is worse than the thing the hook prevents."""
    assert "--no-verify" in HOOK.read_text()


# --------------------------------------------------------------------------- #
# The gap this closes is real                                                  #
# --------------------------------------------------------------------------- #


def test_ci_gate_only_covers_merges() -> None:
    """State the reason this file exists, and keep it true.

    If a merge gate ever grows push coverage, the pre-push hook is redundant and
    someone should know to remove it rather than maintain two guards.
    """
    gate = (REPO / "scripts" / "ci-gate.py").read_text()
    # It takes a PR NUMBER and checks that PR's statuses. There is no push
    # entry point, which is the whole reason this file exists.
    assert "argv[1].isdigit()" in gate, "ci-gate.py no longer takes a PR number"
    assert '"gh", "pr", "checks"' in gate
    assert "pre-push" not in gate, (
        "ci-gate.py appears to handle pushes now; re-evaluate whether the "
        "pre-push hook is still the right layer"
    )
