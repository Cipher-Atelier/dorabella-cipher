# Manifests and integrity

- [artifacts.json](artifacts.json): four recovered legacy originals, exact source context, byte counts and SHA-256.
- [git-original-objects.json](git-original-objects.json): the 1,178 screened original objects browsable in Git, their hashes and sizes.
- [deposit-summary.json](deposit-summary.json): aggregate reviewed-deposit coverage, without private source locators.
- [fresh-embedded-checks.json](fresh-embedded-checks.json): 196/196 checksum assertions freshly matched to downloaded members across six source archives, including nested ZIPs.
- [exclusions.json](exclusions.json): the explicit prohibited British Library source image and derivative rule. The supplied image hash is restriction metadata, not evidence of redistribution.
- [SHA256SUMS.txt](SHA256SUMS.txt): every Git payload file except this checksum list and Git internals. From the repository root: `shasum -a 256 -c manifests/SHA256SUMS.txt`.
- [assembly-20261021-SHA256SUMS.txt](assembly-20261021-SHA256SUMS.txt): unchanged checksum list from the original assembly, applicable to commit `16cec6a`, before the closeout navigation updates.
- [closeout-20261022-public-objects.json](closeout-20261022-public-objects.json): exact relative paths, sizes and hashes of the screened local-experiment code/report supplement; not an inventory of the full private source tree.
- [closeout-20261022-release.json](closeout-20261022-release.json): supplement asset size, SHA-256 and complete member-verification counts.
- [closeout-20261022-local-backup.json](closeout-20261022-local-backup.json): aggregate receipt for the privately held full local backup, without private retrieval locators or a private member listing.

The reviewed evidence Release adds OBJECTS.sha256 for every selected original byte object and PROVENANCE.jsonl for every retained archive/member/version occurrence. Its asset hash and exact size are recorded in release-asset.json after packaging. Source ZIPs and the complete 233-object source inventory remain external with exact archive hashes and private retrieval identities in the local ledger; they are not public payloads.

A missing hash is never guessed. Embedded research-stage hashes are preserved historical records; freshly computed transfer hashes and archive checks have separate identity. A hash establishes bytes, not scientific correctness, rights or a decipherment.
