# R3 SFT round 1: code snapshot

The working copy of this code lives on cephfs, which the training and scoring containers mount:
`/mnt/cephfs/xingchao/experiments/jev/r3_code/` and `/mnt/cephfs/xingchao/experiments/jev/r1_code/`.
This directory is a snapshot synced into git at each commit (`*.py` and `*.sh` files, via tar), so
the code behind every committed result is recorded. Edit the cephfs copy, not this one.

Note: `r1_code/` holds SFT **round 1** artifacts (data conversion, scorer), i.e. part of proposal
round R3. It is not proposal round R1, of which nothing has been run.
