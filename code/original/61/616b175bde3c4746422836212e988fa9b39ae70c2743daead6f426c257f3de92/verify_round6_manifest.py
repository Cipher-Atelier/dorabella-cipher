"""Verify archive file hashes. This verifies integrity, not scientific correctness."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest_round6.json').read_text())
errors=[]
for rel,digest in manifest['sha256'].items():
    p=root/rel
    if not p.is_file():errors.append(f'Missing: {rel}')
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append(f'Changed: {rel}')
if errors:raise SystemExit('\n'.join(errors))
print(f"Verified {len(manifest['sha256'])} files. The manifest does not hash itself.")
