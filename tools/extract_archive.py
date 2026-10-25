import ctypes, struct, os, sys, json, hashlib, time
from ctypes import c_void_p, c_uint, c_int, c_char_p

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL = os.path.join(HERE, 'pack', 'msttssyn.dll')
INV = os.path.join(HERE, 'inv.bin')
OUT = os.path.join(HERE, 'archive')
UNITS = os.path.join(OUT, 'units')
os.makedirs(UNITS, exist_ok=True)

k32 = ctypes.WinDLL('kernel32')
shl = ctypes.WinDLL('shlwapi')
k32.LoadLibraryA.argtypes = [c_char_p]
k32.LoadLibraryA.restype = c_void_p
if not k32.LoadLibraryA(DLL.encode()):
    raise OSError('LoadLibrary failed')
base = k32.GetModuleHandleA(b'msttssyn.dll')
data = open(INV, 'rb').read()
shl.SHCreateMemStream.argtypes = [c_char_p, c_uint]
shl.SHCreateMemStream.restype = c_void_p
loader = ctypes.CFUNCTYPE(c_void_p, c_void_p)(base + 0x20f4)
inv = loader(shl.SHCreateMemStream(data, len(data)))
if not inv:
    raise RuntimeError('inventory load failed')
synth = ctypes.CFUNCTYPE(c_void_p, c_int, c_void_p, c_void_p)(base + 0x19fa)
count = struct.unpack_from('<I', ctypes.string_at(inv, 0x44), 0x20)[0]
table = struct.unpack_from('<I', ctypes.string_at(inv, 0x44), 0x24)[0]
rate = struct.unpack_from('<I', ctypes.string_at(inv, 0x44), 4)[0]
print('rate', rate, 'units', count)
start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
end = int(sys.argv[2]) if len(sys.argv) > 2 else count
manifest_path = os.path.join(OUT, 'manifest.jsonl')
manifest = {}
if os.path.exists(manifest_path):
    for line in open(manifest_path):
        rec = json.loads(line)
        manifest[rec['unit']] = rec

def wav16(path, floats, rate):
    n = len(floats)
    pcm = bytearray()
    for x in floats:
        v = int(x * 32767.0)
        if v > 32767: v = 32767
        if v < -32768: v = -32768
        pcm += struct.pack('<h', v)
    hdr = b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(pcm))
    open(path, 'wb').write(hdr + bytes(pcm))

t0 = time.time()
with open(manifest_path, 'a') as mf:
    for unit in range(start, end + 1):
        state = ctypes.create_string_buffer(0x200)
        p = synth(unit, inv, ctypes.cast(state, c_void_p))
        if not p:
            raise RuntimeError('synth failed unit %d' % unit)
        nframes, total, dim, ppitch, pfeat, psamp, pgain, z = struct.unpack_from('<8i', ctypes.string_at(p, 32))
        raw = ctypes.string_at(psamp, total * 4) if total > 0 else b''
        name = 'unit_%05d' % unit
        open(os.path.join(UNITS, name + '.f32'), 'wb').write(raw)
        floats = list(struct.unpack('<%df' % total, raw)) if total else []
        wav16(os.path.join(UNITS, name + '.wav'), floats, rate)
        rec = {'unit': unit, 'nframes': nframes, 'nsamples': total, 'sha256': hashlib.sha256(raw).hexdigest(),
               'file': name + '.f32'}
        manifest[unit] = rec
        mf.write(json.dumps(rec) + '\n')
        mf.flush()
        if unit % 250 == 0:
            print(unit, 'elapsed', round(time.time() - t0, 1), flush=True)

recs = [manifest[u] for u in sorted(manifest)]
json.dump(recs, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
h = hashlib.sha256()
for rec in recs:
    h.update(open(os.path.join(UNITS, rec['file']), 'rb').read())
print('units', len(recs), 'samples', sum(r['nsamples'] for r in recs), 'archive_sha256', h.hexdigest())
json.dump({'units': len(recs), 'samples': sum(r['nsamples'] for r in recs),
           'archive_sha256': h.hexdigest(), 'rate': rate},
          open(os.path.join(OUT, 'archive.json'), 'w'), indent=1)

