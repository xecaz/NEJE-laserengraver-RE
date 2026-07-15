#!/usr/bin/env python3
"""Find and disassemble methods in NEJE exe that touch SerialPort."""
import dnfile
from dnfile.enums import MetadataTables
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.cil.body import CilMethodBody
from dncil.clr.token import Token, StringToken

pe = dnfile.dnPE("NEJE_V4.2_EN.exe")

# Build token -> name maps
memberrefs = {}
mr_table = pe.net.mdtables.MemberRef
for i, row in enumerate(mr_table.rows):
    parent = ""
    try:
        parent = row.Class.row.TypeName
    except Exception:
        pass
    memberrefs[(0x0A << 24) | (i + 1)] = f"{parent}::{row.Name}"

methods = {}
md_table = pe.net.mdtables.MethodDef
typedefs = pe.net.mdtables.TypeDef
# map method index -> owning type
method_owner = {}
for ti, trow in enumerate(typedefs.rows):
    try:
        for ref in trow.MethodList:
            method_owner[str(ref.row.Name)] = trow.TypeName
    except Exception:
        pass

class Reader(CilMethodBodyReaderBase):
    def __init__(self, pe, row):
        self.offset = pe.get_offset_from_rva(row.Rva)
        self.pe = pe
    def read(self, n):
        d = self.pe.get_data(self.pe.get_rva_from_offset(self.offset), n)
        self.offset += n
        return d
    def tell(self):
        return self.offset
    def seek(self, offset):
        self.offset = offset
        return self.offset

def us(tok):
    try:
        return pe.net.user_strings.get(tok.rid).value
    except Exception:
        return "?"

hits = []
for i, row in enumerate(md_table.rows):
    if not row.Rva:
        continue
    try:
        body = CilMethodBody(Reader(pe, row))
    except Exception:
        continue
    text = []
    interesting = False
    for ins in body.instructions:
        op = str(ins.opcode)
        arg = ""
        if isinstance(ins.operand, StringToken):
            arg = repr(us(ins.operand))
        elif isinstance(ins.operand, Token):
            name = memberrefs.get(ins.operand.value)
            if name:
                arg = name
                if "SerialPort" in name or "Port" in name:
                    interesting = True
            else:
                arg = f"tok:{ins.operand.value:08x}"
        elif ins.operand is not None:
            arg = str(ins.operand)
        text.append(f"    {op} {arg}")
    if interesting:
        hits.append((i + 1, method_owner.get(str(row.Name), "?"), row.Name, text))

print(f"{len(hits)} methods touch SerialPort")
for rid, owner, name, text in hits:
    print(f"\n===== {owner}::{name} (method {rid}) =====")
    print("\n".join(text))
