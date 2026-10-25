import os, sys, json, time, math
import pyghidra
pyghidra.start()

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

BIN = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
PROJ = os.path.abspath(sys.argv[3])

os.makedirs(PROJ, exist_ok=True)
monitor = ConsoleTaskMonitor()
with pyghidra.open_program(BIN, project_location=PROJ, analyze=True) as flat:
    program = flat.getCurrentProgram()
    print("loaded", program, program.getImageBase(), "funcs", program.getFunctionManager().getFunctionCount())

    strings = []
    for d in program.getListing().getDefinedData(True):
        v = d.getValue()
        if isinstance(v, str) and v:
            strings.append([d.getAddress().toString(), v])
    print("defined strings", len(strings))

    funcs = list(program.getFunctionManager().getFunctions(True))
    ifc = DecompInterface()
    ifc.openProgram(program)
    rows = []
    t0 = time.time()
    for i, f in enumerate(funcs):
        try:
            res = ifc.decompileFunction(f, 60, monitor)
            c = res.getDecompiledFunction().getC() if res and res.decompileCompleted() else None
        except Exception as e:
            c = "ERR " + repr(e)
        rows.append({"addr": f.getEntryPoint().toString(), "name": f.getName(), "c": c})
        if i % 250 == 0:
            print(i, round(time.time() - t0, 1))
    json.dump({"strings": strings, "functions": rows}, open(OUT, "w"))
    print("wrote", OUT, len(rows))
