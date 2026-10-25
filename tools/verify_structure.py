import olefile, struct, json, hashlib, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VCE = os.path.join(HERE, 'pack', 'sam.vce')
ARCH = os.path.join(HERE, 'archive')
inv = olefile.OleFileIO(VCE).openstream('Inventory').read()
pos = 0x1c
groups = (6, 11, 13)
arrays = []
for gi, cnt in enumerate(groups):
    for k in range(cnt):
        rows, cols = struct.unpack_from('<II', inv, pos)
        data = struct.unpack_from('<%df' % (rows * cols), inv, pos + 8)
        arrays.append({'group': gi, 'rows': rows, 'cols': cols, 'pos': pos, 'data': data})
        pos += 8 + rows * cols * 4
assert pos == 0x8490c, hex(pos)
count, dlen = struct.unpack_from('<II', inv, pos)
table_start = pos + 8
offs = list(struct.unpack_from('<%dI' % (count + 1), inv, table_start))
ds = table_start + (count + 1) * 4
area = dlen - (count + 1) * 4
assert ds + area == len(inv)

def s8(b):
    return b - 256 if b >= 128 else b

def decode_pitch(data, n, base=0.0):
    out = []
    i = 0
    for _ in range(n):
        c = s8(data[i])
        if c == 0x7f:
            v = base + 127.0
            while s8(data[i]) == 0x7f:
                v += s8(data[i + 1])
                i += 1
            out.append(v)
            i += 1
        elif c == -0x80:
            v = -128.0 - base
            while s8(data[i]) == -0x80:
                v += s8(data[i + 1])
                i += 1
            out.append(v)
            i += 1
        else:
            out.append(c - base if c < 1 else base + c)
            i += 1
    return out, i

man = json.load(open(os.path.join(ARCH, 'manifest.json')))
by_unit = {r['unit']: r for r in man}
assert len(man) == count == 3365
assert [r['unit'] for r in man] == list(range(1, count + 1))

bad = 0
tot = 0
h = hashlib.sha256()
for u in range(1, count + 1):
    a = offs[u]
    b = offs[u + 1] if u + 1 < len(offs) else area
    rec = inv[ds + a:ds + b]
    n = struct.unpack_from('<I', rec, 0)[0]
    pitches, used = decode_pitch(rec[4:], n)
    prev_unvoiced = True
    extra = 0
    for v in pitches:
        if v > 0:
            extra += 11 if prev_unvoiced else 13
            prev_unvoiced = False
        else:
            prev_unvoiced = True
    exp_len = 4 + used + 6 * n + 4 * n + extra
    if exp_len != len(rec):
        bad += 1
        print('layout mismatch unit', u, len(rec), exp_len)
    nsamp = sum(abs(int(v)) for v in pitches)
    r = by_unit[u]
    if r['nframes'] != n or r['nsamples'] != nsamp:
        bad += 1
        print('meta mismatch unit', u, r, n, nsamp)
    raw = open(os.path.join(ARCH, 'units', r['file']), 'rb').read()
    if len(raw) != nsamp * 4 or hashlib.sha256(raw).hexdigest() != r['sha256']:
        bad += 1
        print('file mismatch unit', u)
    h.update(raw)
    tot += nsamp
    # codebook indices must be in range
    ipos = 4 + used
    for f in range(n):
        for ai in range(6):
            idx = rec[ipos + f * 6 + ai]
            rows = arrays[ai]['rows']
            if idx >= rows:
                bad += 1
                print('index out of range unit', u, f, ai, idx, rows)
print('units', count, 'samples', tot, 'bad', bad)
print('archive_sha256', h.hexdigest())
print('expected      ', json.load(open(os.path.join(ARCH, 'archive.json')))['archive_sha256'])
assert h.hexdigest() == json.load(open(os.path.join(ARCH, 'archive.json')))['archive_sha256']
print('STRUCTURAL_PARITY_OK')
