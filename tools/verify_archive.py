import os, zipfile, json, hashlib, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(HERE, 'sam_voice_samples.zip')
ARCH = os.path.join(HERE, 'archive')

with zipfile.ZipFile(ZIP) as z:
    bad = z.testzip()
    assert bad is None, 'corrupt zip member: %s' % bad
    names = set(z.namelist())
    man = json.loads(z.read('archive/manifest.json'))
    agg = json.loads(z.read('archive/archive.json'))
    sums = {}
    for line in z.read('archive/SHA256SUMS').decode().splitlines():
        h, path = line.split('  ', 1)
        sums[path] = h

    assert len(man) == agg['units'] == 3365, len(man)
    total = 0
    hagg = hashlib.sha256()
    errors = 0
    for r in man:
        path = 'archive/units/' + r['file']
        if path not in names:
            errors += 1; print('missing', path); continue
        data = z.read(path)
        if hashlib.sha256(data).hexdigest() != r['sha256'] or len(data) != r['nsamples'] * 4:
            errors += 1; print('mismatch', path)
        if sums.get('units/' + r['file']) != r['sha256']:
            errors += 1; print('sums mismatch', path)
        hagg.update(data)
        total += r['nsamples']
    if hagg.hexdigest() != agg['archive_sha256']:
        errors += 1; print('aggregate mismatch', hagg.hexdigest(), agg['archive_sha256'])
    if total != agg['samples']:
        errors += 1; print('sample count mismatch', total, agg['samples'])

# cross-check the loose manifests shipped in the repo
for name in ('manifest.json', 'archive.json', 'SHA256SUMS'):
    a = open(os.path.join(ARCH, name), 'rb').read()
    b = zipfile.ZipFile(ZIP).read('archive/' + name)
    if a != b:
        errors += 1; print('repo copy differs:', name)

print('units', len(man), 'samples', total)
print('archive_sha256', agg['archive_sha256'])
if errors:
    print('FAIL', errors, 'errors'); sys.exit(1)
print('ARCHIVE_PARITY_OK')
