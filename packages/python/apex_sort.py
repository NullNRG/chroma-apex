"""CHROMA APEX: ctypes bindings for packed numeric stable ordering. MIT.

The pure-Python composite record helper uses cached metric projections and native
indices, not native object comparison. It does not accelerate arbitrary Python keys.
"""
from __future__ import annotations
import ctypes as c
import os
from pathlib import Path
from typing import Any, Callable, Iterable

class Stats(c.Structure):
    _fields_ = [('count',c.c_uint64),('passes',c.c_uint32),('path',c.c_uint32),('scratch_bytes_peak',c.c_uint64)]

class Apex:
    def __init__(self, lib_path: str | None = None):
        if lib_path is None:
            root=Path(__file__).resolve().parents[2]
            candidates=[root/'build'/'libchroma_apex.so',root/'build'/'libchroma_apex.dylib',root/'build'/'Release'/'chroma_apex.dll']
            lib_path=next((str(p) for p in candidates if p.exists()),None)
            if lib_path is None:
                raise FileNotFoundError('Compile the native library with: cmake -S . -B build && cmake --build build')
        self.dll=c.CDLL(str(lib_path))
        for symbol,typ in [('apx_order_f64',c.c_double),('apx_order_i64',c.c_int64),('apx_order_u64',c.c_uint64)]:
            fn=getattr(self.dll,symbol)
            fn.argtypes=(c.POINTER(typ),c.c_size_t,c.POINTER(c.c_uint32),c.POINTER(Stats))
            fn.restype=c.c_int

    def _order(self,keys: Iterable[Any],kind: str):
        values=list(keys);n=len(values)
        typ={'f64':c.c_double,'i64':c.c_int64,'u64':c.c_uint64}[kind]
        # ctypes integer conversions can silently wrap, so reject invalid ranges.
        if kind != 'f64':
            lo,hi=((-2**63,2**63-1) if kind=='i64' else (0,2**64-1))
            if any(not isinstance(x,int) or not lo <= x <= hi for x in values):
                raise ValueError('integer keys must fall within the exact 64-bit domain')
        arr=(typ*n)(*values);out=(c.c_uint32*n)();stats=Stats()
        fn=getattr(self.dll,'apx_order_'+kind)
        status=fn(arr,n,out,c.byref(stats))
        if status: raise RuntimeError(f'APEX native error {status}')
        return list(out),{'path':stats.path,'passes':stats.passes,'scratch_bytes_peak':stats.scratch_bytes_peak}

    def order_float64(self,values):return self._order(values,'f64')[0]
    def order_int64(self,values):return self._order(values,'i64')[0]
    def order_uint64(self,values):return self._order(values,'u64')[0]
    def sorted_records_by_float64(self,records,metric: Callable[[Any],float]):
        records=list(records)
        indices=self.order_float64([metric(r) for r in records])
        return [records[i] for i in indices]
