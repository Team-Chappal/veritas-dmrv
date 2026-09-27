#!/usr/bin/env python
"""
Documentation claim linter.

ZERO external dependencies — runs before `make bootstrap`, so a stale or wrong
claim in `docs/` is caught even on a clean machine.

PURPOSE
-------
Every critical defect found during the S0/S1 audit shared one shape: **a
document stated a specific number or mandate that the implementation did not
support.** Hand-written solar vectors, an allometric prefactor off by 8.72x, a
vegetation index specified three different ways, an icon library mandated that
was not installed, a Definition of Done pre-checked before any code existed.

None of these are typos. They are claims that were never checked against
anything. This script makes that class of error visible and fails CI on it.

Usage:
    python scripts/verify_docs.py
    python scripts/verify_docs.py --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

#: The consolidated brief is a derived analysis document that quotes the
#: original defects verbatim in order to document them. Linting it produces
#: only false positives, so it is excluded.
EXCLUDE = {"VERITAS-CONSOLIDATED-BRIEF.md"}


@dataclass
class Rule:
    rule_id: str
    description: str
    pattern: str
    # Files this rule applies to; empty means all docs.
    scope: tuple
    # Substrings that make a match acceptable (e.g. a correction notice).
    allow_context: tuple = ()
    severity: str = "ERROR"


RULES: list = [
    Rule(
        "SOLAR-001",
        "Hand-written solar azimuth vectors that pvlib contradicts. All four of "
        "the original 12-TESTING vectors were outside their own tolerances; the "
        "Ankara value (138.5 deg at 10:00 UTC on the June solstice) is physically "
        "impossible because solar noon there is 09:48 UTC, so azimuth must be ~188.",
        r"expected\s*_?azimuth|Documented\s+94\.2|,\s*138\.5\s*,\s*2\.5",
        scope=("12-TESTING-AND-QA-STRATEGY.md",),
        allow_context=("CORRECTION", "actual", "must be", "impossible", "off,"),
    ),
    Rule(
        "BIOMASS-001",
        "A prefactor claiming to be exp(-0.533) ~= 0.5868 for Chave allometry. "
        "That value is WRONG. Chave et al. (2014) Eq. 4 is "
        "AGB = 0.0673*(WD*H*D^2)^0.976, per the R BIOMASS package reference "
        "implementation. This rule exists because the wrong value was written "
        "into the spec, 'corrected' to a second wrong value, and only caught by "
        "external verification — see README.md.",
        r"exp\(-0\.533\)|CHAVE_B0|e\^\{-0\.533\}|0\.5868",
        scope=(),
    ),
    Rule(
        "MOIRE-001",
        "The screen-replay quarantine action. It was REMOVED because the "
        "specified threshold (gradient CV > 4.2) was measured as unachievable "
        "against genuine Moire patterns (0.63-0.94) and is exceeded by clean "
        "natural photographs (2.49). An unvalidated signal must not accuse.",
        r"QUARANTINE_SCREEN_REPLAY_MOIRE",
        scope=(),
        allow_context=(
            "CORRECTION", "removed", "must not", "no future caller",
            "was not", "until the", "That was", "immediately quarantines",
            "Superseded", "HISTORICAL", "no longer exists",
        ),
    ),
    Rule(
        "VEGIDX-001",
        "Raw Excess Green Index (2G-R-B) with a fixed threshold. Raw ExG is not "
        "shadow-invariant; the shadow-invariant standard is GLI = (2G-R-B)/(2G+R+B) "
        "with Otsu thresholding.",
        r"Excess Green Index|\\text\{ExG\}\s*=\s*2G",
        scope=(),
        allow_context=("CORRECTION", "not shadow-invariant", "previously"),
    ),
    Rule(
        "ICONS-001",
        "Phosphor Icons as the mandated icon family. The pinned package.json and "
        "every code sample use lucide-react; Phosphor was never installed.",
        r"Pinned exclusively to \*\*Phosphor",
        scope=(),
    ),
    Rule(
        "DOD-001",
        "A Definition of Done pre-checked before implementation existed. A "
        "checklist that starts complete carries no signal.",
        r"^\s*\*\s*\[x\]",
        scope=("08-PROJECT-PLAN.md",),
    ),
    Rule(
        "PHYSICS-001",
        "A solar elevation gate of 0 deg. Below ~10 deg, cast-shadow azimuth is "
        "dominated by terrain slope and cannot support an automated fraud verdict.",
        r"if elevation_deg < 0\b|elevation_deg < 0\.0",
        scope=(),
    ),
    Rule(
        "AZIMUTH-001",
        "A non-NOAA azimuth expression. cos(az) = (sin(a)sin(phi) - sin(d)) / "
        "(cos(a)cos(phi)) does not match the implementation and disagrees with "
        "pvlib; it silently swaps morning for afternoon.",
        r"\\sin\(\\alpha\)\\sin\(\\phi\)\s*-\s*\\sin\(\\delta\)",
        scope=(),
        allow_context=("CORRECTION", "previously read", "not** the NOAA"),
    ),
    Rule(
        "LATENCY-001",
        "An unbounded latency claim without the hardware or resolution it was "
        "measured on. '< 150 ms' and '< 800 ms' are only meaningful with a stated "
        "baseline.",
        r"<\s*150\s*\\?text\{ ms\}|< 150ms|<\s*800\s*\\?text\{ ms\}",
        scope=(),
        allow_context=("target", "Target", "measured", "baseline", "NFR-"),
        severity="WARN",
    ),
]


def iter_doc_lines():
    for path in sorted(DOCS.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.name in EXCLUDE:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            yield path, lineno, line


def check(verbose: bool = False) -> int:
    findings: list = []

    for rule in RULES:
        pattern = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
        for path, lineno, line in iter_doc_lines():
            if rule.scope and path.name not in rule.scope:
                continue
            # A markdown blockquote ('> ...') is a CITATION, not an assertion.
            # Correction notices quote the original wrong text verbatim in
            # order to document it; flagging those would make every correction
            # unshippable, which is the opposite of what this linter is for.
            if line.lstrip().startswith(">"):
                continue
            if not pattern.search(line):
                continue
            if any(ctx.lower() in line.lower() for ctx in rule.allow_context):
                if verbose:
                    print(f"  ~ {path.name}:{lineno}  {rule.rule_id} (allowed: correction context)")
                continue
            findings.append((rule, path, lineno, line.strip()))

    if not findings:
        print("docs: clean — no unverified claims detected")
        return 0

    by_rule: dict = {}
    for rule, path, lineno, line in findings:
        by_rule.setdefault(rule.rule_id, []).append((rule, path, lineno, line))

    errors = sum(1 for f in findings if f[0].severity == "ERROR")
    warns = len(findings) - errors
    print(f"docs: {errors} error(s), {warns} warning(s) across {len(by_rule)} rule(s)\n")
    for rule_id, items in sorted(by_rule.items()):
        rule = items[0][0]
        print(f"[{rule.severity}] {rule_id} — {rule.description}")
        for _, path, lineno, line in items:
            print(f"    {path.name}:{lineno}")
            print(f"      {line[:150]}")
        print()

    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not DOCS.exists():
        print(f"ERROR: {DOCS} does not exist", file=sys.stderr)
        return 2

    print(f"Verifying documentation claims in {DOCS}")
    return check(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
