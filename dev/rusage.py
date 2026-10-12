"""Hardware counters for some processes, from macOS's proc_pid_rusage: what dev/profile.mjs
measures with, since unlike CPU %, they hardly move with whatever else the machine is doing.

    python3 dev/rusage.py <pid> [<pid> ...]   # one JSON object: pid -> its counters

instructions: retired since the process started; cycles: CPU cycles; cpu_ns: user + system
time; energy_nj: billed energy, nanojoules; wakeups: from idle (package and interrupt);
footprint: the memory Activity Monitor shows (bytes); resident: what is in RAM (bytes).
"""

from __future__ import annotations

import ctypes
import json
import sys

RUSAGE_INFO_V4 = 4


class RusageInfoV4(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in (
        "user_time", "system_time", "pkg_idle_wkups", "interrupt_wkups", "pageins", "wired_size",
        "resident_size", "phys_footprint", "proc_start_abstime", "proc_exit_abstime", "child_user_time",
        "child_system_time", "child_pkg_idle_wkups", "child_interrupt_wkups", "child_pageins",
        "child_elapsed_abstime", "diskio_bytesread", "diskio_byteswritten", "cpu_time_qos_default",
        "cpu_time_qos_maintenance", "cpu_time_qos_background", "cpu_time_qos_utility",
        "cpu_time_qos_legacy", "cpu_time_qos_user_initiated", "cpu_time_qos_user_interactive",
        "billed_system_time", "serviced_system_time", "logical_writes", "lifetime_max_phys_footprint",
        "instructions", "cycles", "billed_energy", "serviced_energy", "interval_max_phys_footprint",
        "runnable_time")]


def counters(pid: int) -> dict | None:
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
    info = RusageInfoV4()
    if libproc.proc_pid_rusage(pid, RUSAGE_INFO_V4, ctypes.byref(info)) != 0:
        return None
    # the times are in mach absolute units: nanoseconds scaled by the timebase (125/3 on Apple silicon)
    tb = ctypes.CDLL("/usr/lib/libSystem.dylib")

    class Timebase(ctypes.Structure):
        _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]
    t = Timebase()
    tb.mach_timebase_info(ctypes.byref(t))
    return {"instructions": info.instructions, "cycles": info.cycles,
            "cpu_ns": (info.user_time + info.system_time) * t.numer // t.denom,
            "energy_nj": info.billed_energy, "wakeups": info.pkg_idle_wkups + info.interrupt_wkups,
            "footprint": info.phys_footprint, "resident": info.resident_size}


if __name__ == "__main__":
    print(json.dumps({p: counters(int(p)) for p in sys.argv[1:]}))
