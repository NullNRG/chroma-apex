// SPDX-License-Identifier: MIT
// P/Invoke facade. Requires chroma_apex.dll / libchroma_apex.so on loader path.
using System;
using System.Runtime.InteropServices;
namespace ChromaApex {
  [StructLayout(LayoutKind.Sequential)]
  public struct Stats {
    public ulong Count;
    public uint Passes;
    public uint Path;
    public ulong ScratchBytesPeak;
  }
  public static class Apex {
    [DllImport("chroma_apex", CallingConvention=CallingConvention.Cdecl)]
    private static extern int apx_order_f64([In] double[] keys, UIntPtr length, [Out] uint[] order, out Stats stats);
    [DllImport("chroma_apex", CallingConvention=CallingConvention.Cdecl)]
    private static extern int apx_order_i64([In] long[] keys, UIntPtr length, [Out] uint[] order, out Stats stats);
    public static uint[] Order(double[] keys) {
      if(keys==null)throw new ArgumentNullException(nameof(keys));
      var permutation=new uint[keys.Length];
      var status=apx_order_f64(keys,(UIntPtr)(ulong)keys.Length,permutation,out _);
      if(status!=0)throw new InvalidOperationException($"APEX failed: {status}");
      return permutation;
    }
    public static uint[] Order(long[] keys) {
      if(keys==null)throw new ArgumentNullException(nameof(keys));
      var permutation=new uint[keys.Length];
      var status=apx_order_i64(keys,(UIntPtr)(ulong)keys.Length,permutation,out _);
      if(status!=0)throw new InvalidOperationException($"APEX failed: {status}");
      return permutation;
    }
    public static T[] SortedBy<T>(T[] records,Func<T,double> metric) {
      if(records==null)throw new ArgumentNullException(nameof(records));
      if(metric==null)throw new ArgumentNullException(nameof(metric));
      var keys=new double[records.Length];for(int i=0;i<keys.Length;i++)keys[i]=metric(records[i]);
      var ix=Order(keys);var result=new T[records.Length];for(int i=0;i<result.Length;i++)result[i]=records[ix[i]];
      return result;
    }
  }
}
