# Storage decision

The initial 21 October Git archive stores English navigation, integrity summaries and 1,178 small screened original files for browsing. It does not store source ZIPs or a blanket source inventory with private locators. The separate 22 October closeout supplement is described below.

The reviewed evidence Release ZIP stores all 109,726 selected unique original objects (457,327,462 uncompressed object bytes), an OBJECTS.sha256 list and 147,496 provenance mappings. It is a **new curated deposit**, not a replacement/repacked original research archive. Each retained object's bytes are unchanged; the mapping preserves original archive/member/version identity.

The 232 acquired source objects remain intact outside Git in their exact Library versions and the local transfer holding area. Their original ZIP hashes are retained in the private ledger. They are not uploaded wholesale because they mix research with omitted source/model/private or unresolved material. Earlier and incomplete stages are preserved where eligible rather than replaced with successful control outcomes.

Git LFS is not configured or used. GitHub Releases were selected for the larger reviewed own-evidence collection after the storage plan was reported, preserving ordinary Git usability. Public visibility was separately authorized after an empty-history check. A later new or changed deposit must repeat source/privacy/rights screening; this decision is not blanket permission for raw archives.

## 22 October closeout

The separate local `dorabella-20261020` tree is preserved in a private, compressed `tar.zst` archive outside this repository. Its adjacent inventory records every file hash, directory and symbolic link. Full streaming verification compares every archived member against that inventory before any unpacked source is removed. This backup is local and is not an off-device backup. It retains restricted and third-party materials privately; it must not be uploaded wholesale.

The new public supplement contains screened own-research Python source and Markdown reports, without changing their bytes. Eight reports are browsable in Git. The remaining selected files and their exact paths/hashes are preserved in the separate [closeout Release](https://github.com/Cipher-Atelier/dorabella-cipher/releases/tag/archive-2026-10-22-closeout). Numeric model arrays, generated result/checkpoint data, dependencies, caches, source assets and private locators remain outside the public supplement. This is not a standalone numerical reproduction environment.

The previous Release and frozen research originals remain unchanged. The repository was already small, so no Git history rewrite or deletion of historical evidence was needed. See [closeout status](STATUS.md) for resumption and restoration notes.
