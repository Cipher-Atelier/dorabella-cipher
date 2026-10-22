# Research closeout — 22 October 2026

Active Dorabella research stopped at the owner's request so work can move to another cipher. The materials are preserved for possible future resumption. The GitHub repository remains available for changes.

**No accepted decipherment, coherent historical plaintext, key or partial letter assignments were established.** Search scores, successful software checks and synthetic-control recovery must not be presented as historical success.

## What is retained

- The earlier public archive and its 21 October reviewed-evidence Release, unchanged.
- A [supplement](reports/closeout-20261022/README.md) covering the separate 20–21 October local experiments: eight browsable original reports, plus screened code/reports and an exact-byte manifest in the closeout Release.
- A private full compressed copy of the local experiment tree, including original model arrays, outputs, dependencies and held source materials. The adjacent private inventory and verification receipt describe its exact coverage. A public [aggregate receipt](manifests/closeout-20261022-local-backup.json) identifies the backup by hash without disclosing its full inventory or location.

The public supplement deliberately omits generated numerical/checkpoint data, third-party source assets, dependencies, private locators and unselected source notes. It is not a full runnable reproduction environment. Some preserved reports and code refer to omitted files or old temporary paths. The private archive captures the local tree and its symbolic links; external link targets and files outside that tree are not included merely because a report references them.

## Returning to the work

Start with the supplement index and the final original reports. Distinguish negative results from untested cases and failed control gates. Do not transfer letters from synthetic controls or treat the minimum descriptive null rank as a solution probability.

For the full local environment, locate the private backup by its aggregate receipt, verify `SHA256SUMS.txt`, and extract into a new scratch directory, preserving the original archive. With `zstd` installed, the standard restoration command is:

```sh
mkdir restored-research
zstd -dc /path/to/dorabella-20261020-full-private.tar.zst | tar -xf - -C restored-research
```

The original top-level directory name is preserved. Review source, dependency and external-link availability before considering a numerical reproduction. Archival verification checks bytes; no research scripts, solvers, scorers, calibrations or cryptanalytic verifiers were executed during this closeout.
