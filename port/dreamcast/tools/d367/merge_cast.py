#!/usr/bin/env python3
"""merge_cast.py <out cast dir> <cast dir>... : one model_registry.py cast dir holding the descriptors of several
(copies of each <name>/ dir; catalogs, archive audits and candidate revisions merged; an archive in two audits must
agree on sha256). Paths inside the catalogs (texture packages) stay absolute to the source casts."""
import json, shutil, sys
from pathlib import Path
out = Path(sys.argv[1])
assert not out.exists(), out
cat, audit, cand = [], {}, {}
names = []
for c in map(Path, sys.argv[2:]):
    cc = json.loads((c / 'ps2-overlay/integration-bundle/catalog.json').read_text())
    for e in cc:
        assert e['name'] not in names, e['name']
        names.append(e['name'])
        shutil.copytree(c / e['name'], out / e['name'])
    cat += cc
    for k, v in json.loads((c / 'source/archive-audit.json').read_text()).items():
        assert k not in audit or audit[k]['sha256'] == v['sha256'], k
        audit[k] = v
    cand.update(json.loads((c / 'source/candidate-revisions.json').read_text()))
(out / 'ps2-overlay/integration-bundle').mkdir(parents=True)
(out / 'source').mkdir()
(out / 'ps2-overlay/integration-bundle/catalog.json').write_text(json.dumps(cat, indent=1))
(out / 'source/archive-audit.json').write_text(json.dumps(audit, indent=1))
(out / 'source/candidate-revisions.json').write_text(json.dumps(cand, indent=1))
(out / 'MERGED-FROM.json').write_text(json.dumps(dict(sources=sys.argv[2:], descriptors=names), indent=1))
print(out, names)
