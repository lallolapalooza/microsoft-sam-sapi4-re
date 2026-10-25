import ctypes, struct, json, hashlib, os
from ctypes import c_void_p, c_uint, c_int, c_char_p

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
k32 = ctypes.WinDLL('kernel32')
shl = ctypes.WinDLL('shlwapi')
k32.LoadLibraryA.argtypes = [c_char_p]
k32.LoadLibraryA.restype = c_void_p
assert k32.LoadLibraryA(os.path.join(HERE, 'pack', 'msttssyn.dll').encode())
base = k32.GetModuleHandleA(b'msttssyn.dll')
data = open(os.path.join(HERE, 'inv.bin'), 'rb').read()
shl.SHCreateMemStream.argtypes = [c_char_p, c_uint]
shl.SHCreateMemStream.restype = c_void_p
loader = ctypes.CFUNCTYPE(c_void_p, c_void_p)(base + 0x20f4)
inv = loader(shl.SHCreateMemStream(data, len(data)))
synth = ctypes.CFUNCTYPE(c_void_p, c_int, c_void_p, c_void_p)(base + 0x19fa)
man = {r['unit']: r for r in json.load(open(os.path.join(HERE, 'archive', 'manifest.json')))}
assert len(man) == 3365
h = hashlib.sha256()
bad = 0
for u in range(1, 3366):
    st = ctypes.create_string_buffer(0x200)
    p = synth(u, inv, ctypes.cast(st, c_void_p))
    s = struct.unpack_from('<8i', ctypes.string_at(p, 32))
    raw = ctypes.string_at(s[5], s[1] * 4)
    r = man[u]
    d = hashlib.sha256(raw).hexdigest()
    if s[0] != r['nframes'] or s[1] != r['nsamples'] or d != r['sha256']:
        bad += 1
        print('MISMATCH', u, s[0], s[1], d, r)
    h.update(raw)
print('units', 3365, 'mismatches', bad)
print('archive_sha256', h.hexdigest())
assert bad == 0
print('ENGINE_PARITY_OK')
