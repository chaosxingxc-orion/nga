# <experiment id> — <one-line title>

> Status: planned | running | done | void · Round: <R0/R3 round 1/...> · Date started (UTC): <>
> Pre-registration: <file §clause> · Run dir: <path on cephfs> · Code: <path + git commit>

## 1. Purpose

What question this run answers, and which decision it feeds. Name the defect-registry row
(survey §2.2.4) the measure points at, and the gate it feeds, or state that it feeds none.

## 2. Hypothesis

Stated **before** the run, both directions: what we expect, and what falls if the result is
reversed. Include the unconstrained optimum of the measure and the degenerate solution that
would satisfy it trivially, plus the discrimination counterpart that seals it
(CLAUDE.md §4 rules 1-2).

## 3. Setup

Model and revision; data files with sha256 and row counts; prompt version; recipe (or a pointer to
the pre-registered clause, since the recipe is frozen there); seeds; chips and image; launch command.
Anything that differs from the pre-registration is listed here as a declared difference, not left
implicit.

## 4. Results

Every rate with its n. Accuracies with tie counts. Flip rates with dropped-pair count and C-branch
rate. Throughput **per chip** with the chip count stated. Degenerate baselines beside every trained
number. Reference (Kev) figures quoted as a reference, never as a target, with the declared
differences named.

Suspicious-success checks: any rate of exactly 0.0 or 1.0, any metric identical across cells, and
any cell below the minimum sample count is explained **before** the number is reported.

## 5. Verdict

Which pre-registered decision line passed, failed or is void, and why. What this run may **not**
claim. Open questions it leaves, and the next run that would settle them.
