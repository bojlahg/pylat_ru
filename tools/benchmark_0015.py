"""Deterministic, Java-free Task 0015 performance baseline generator."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

from pylat_ru import LanguageToolRU, LEVEL_PICKY


SUITE_VERSION = "1.0"
INPUTS = {
    "short_clean": "Это короткое корректное русское предложение. " * 3,
    "short_errors": "Ученик решил задать тест учителю. Это  тест,а потом потом ответ.",
    "short_spelling": "Каждя семя счаслива по своему, но эта опечатка совем необычна.",
    "medium": ("В начале осени ученики вернулись в школу. Они обсуждали книги, задачи и новые планы. " * 22),
    "long": ("Исследователь записал наблюдение, проверил результат и подготовил краткое объяснение. " * 125),
    "picky": "Один два три четыре пять.",
    "configured_speller": "The quick brown fox. Каждый ученик прочитал текст.",
}


def rss_bytes() -> int | None:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            counters = Counters(); counters.cb = ctypes.sizeof(counters)
            ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
            get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), wintypes.DWORD]
            get_memory.restype = wintypes.BOOL
            if not get_memory(handle, ctypes.byref(counters), counters.cb):
                return None
            return int(counters.WorkingSetSize)
        except Exception:
            return None
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * (1 if sys.platform == "darwin" else 1024))
    except Exception:
        return None


def stats(samples: list[float], chars: int) -> dict[str, float | int]:
    ordered = sorted(samples)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    median = statistics.median(samples)
    return {"iterations": len(samples), "median_seconds": median, "min_seconds": min(samples),
            "max_seconds": max(samples), "p95_seconds": p95,
            "characters_per_second": chars / median if median else 0.0}


def measure(callable_object: object, warmups: int, repeats: int, chars: int) -> dict[str, float | int]:
    function = callable_object  # keep timing body visually small
    for _ in range(warmups):
        function()  # type: ignore[operator]
    samples = []
    for _ in range(repeats):
        started = time.perf_counter(); function()  # type: ignore[operator]
        samples.append(time.perf_counter() - started)
    return stats(samples, chars)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--soak-iterations", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("compat/performance_baseline_0015.json"))
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 0 or args.soak_iterations < 1:
        parser.error("counts must be positive (warmups may be zero)")

    memory = {"before_construction_rss_bytes": rss_bytes()}
    construction_samples = []
    for _ in range(args.repeats):
        started = time.perf_counter(); LanguageToolRU()
        construction_samples.append(time.perf_counter() - started)
    construction = stats(construction_samples, 0)

    tool = LanguageToolRU()
    configured = LanguageToolRU(rule_config={"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}, "TOO_LONG_SENTENCE": {"maxWords": 4}})
    memory["after_construction_rss_bytes"] = rss_bytes()
    tool.check(INPUTS["short_clean"])
    memory["after_warmup_rss_bytes"] = rss_bytes()

    timings = {}
    for name, text in INPUTS.items():
        current = configured if name == "configured_speller" else tool
        level = LEVEL_PICKY if name == "picky" else "DEFAULT"
        repeats = min(args.repeats, 2) if name == "long" else args.repeats
        timings[name] = measure(lambda c=current, t=text, level=level: c.check(t, level=level), args.warmups, repeats, len(text))

    workload = [INPUTS["short_clean"], INPUTS["short_errors"], INPUTS["short_spelling"], INPUTS["picky"]]
    soak_start_rss = rss_bytes(); started = time.perf_counter()
    for index in range(args.soak_iterations):
        tool.check(workload[index % len(workload)], level=LEVEL_PICKY if index % len(workload) == 3 else "DEFAULT")
    soak_seconds = time.perf_counter() - started
    soak_end_rss = rss_bytes(); memory["after_bounded_soak_rss_bytes"] = soak_end_rss

    payload = {
        "schema_version": "1.0", "task": "0015", "benchmark_suite_version": SUITE_VERSION,
        "source_tree_baseline": "a80dfcfe019ee1cd6ffd26feee2a9313f60c195f",
        "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
        "platform": platform.platform(), "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "logical_cpu_count": os.cpu_count(),
        "inputs": {name: {"code_points": len(text), "utf8_bytes": len(text.encode("utf-8")), "sha256": __import__("hashlib").sha256(text.encode()).hexdigest()} for name, text in INPUTS.items()},
        "warmup_count": args.warmups, "repeat_count": args.repeats,
        "construction": construction, "warm_checks": timings, "memory": memory,
        "bounded_soak": {"iterations": args.soak_iterations, "seconds": soak_seconds,
                         "rss_before_bytes": soak_start_rss, "rss_after_bytes": soak_end_rss,
                         "rss_delta_bytes": None if soak_start_rss is None or soak_end_rss is None else soak_end_rss - soak_start_rss,
                         "result": "PASS"},
        "notes": ["Wall-clock values are a local regression baseline, not a cross-machine SLA.",
                  "RSS is peak RSS on Unix and working-set RSS on Windows; those domains are not directly comparable.",
                  "Construction samples are in an already-imported process and may benefit from immutable resource caches."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
