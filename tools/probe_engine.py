import ctypes, sys
from ctypes import c_void_p, c_uint, c_int, c_char_p, POINTER, byref
k32=ctypes.WinDLL('kernel32', use_last_error=True)
shl=ctypes.WinDLL('shlwapi')
k32.LoadLibraryA.argtypes=[c_char_p]; k32.LoadLibraryA.restype=c_void_p
h=k32.LoadLibraryA(os.path.join(HERE,'pack','msttssyn.dll').encode())
print('hmod',hex(h) if h else None, 'err', ctypes.get_last_error())
base=k32.GetModuleHandleA(b'msttssyn.dll')
print('base',hex(base))
data=open(os.path.join(HERE,'inv.bin'),'rb').read()
shl.SHCreateMemStream.argtypes=[c_char_p,c_uint]; shl.SHCreateMemStream.restype=c_void_p
st=shl.SHCreateMemStream(data,len(data))
print('stream',hex(st) if st else None)
loader=ctypes.CFUNCTYPE(c_void_p,c_void_p)(base+0x20f4)
inv=loader(st)
print('inv',hex(inv) if inv else None)
if inv:
    buf=ctypes.string_at(inv,0x44)
    import struct
    print('fields',struct.unpack('<17I',buf))
    rate=struct.unpack_from('<I',buf,4)[0]
    print('rate',rate)
    synth=ctypes.CFUNCTYPE(c_void_p,c_int,c_void_p,c_void_p)(base+0x19fa)
    state=ctypes.create_string_buffer(0x200)
    for unit in [1,2,3,4,5]:
        p=synth(unit,inv,ctypes.cast(state,c_void_p))
        print('unit',unit,'ret',hex(p) if p else None)
        if p:
            s=struct.unpack_from('<8i',ctypes.string_at(p,32))
            print('  struct',s)
            n,total=s[0],s[1]
            samples=ctypes.string_at(s[5], total*4) if s[5] and total>0 else b''
            import array
            a=array.array('f'); a.frombytes(samples[:len(samples)//4*4])
            print('  total',total,'first',list(a[:8]))
