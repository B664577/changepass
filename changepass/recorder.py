"""行为录制与重放。

一次「行为」记录四样东西，缺一不可：
  返回值、抛出的异常（类型与消息）、标准输出、被声明为可观测的副作用。

只记返回值是不够的 —— 重构最容易悄悄改掉的恰恰是异常路径与打印内容。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import contextlib
import sys
import traceback
from pathlib import Path
from typing import Any, Callable


def load_target(spec: str) -> Callable:
    """`路径.py:函数名` → 函数对象。每次都重新 import，确保拿到改后的版本。"""
    if ":" not in spec:
        raise SystemExit(f"目标写法应为 路径.py:函数名，收到 {spec!r}")
    path, fn = spec.rsplit(":", 1)
    p = Path(path).resolve()
    if not p.exists():
        raise SystemExit(f"找不到 {p}")
    name = "cp_target_" + hashlib.sha1(str(p).encode()).hexdigest()[:8]
    sys.modules.pop(name, None)
    spec_ = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec_)
    sys.modules[name] = mod
    spec_.loader.exec_module(mod)
    if not hasattr(mod, fn):
        raise SystemExit(f"{p.name} 里没有 {fn}")
    return getattr(mod, fn)


def canon(obj: Any) -> str:
    """把任意返回值变成可比较的规范字符串。

    不可 JSON 序列化的对象退回 repr —— repr 不稳定的类型会在
    「重放稳定性」那一关被抓到，而不是在这里被悄悄放过。
    """
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                          default=lambda o: f"<{type(o).__name__}>{o!r}")
    except Exception:
        return repr(obj)


def observe(fn: Callable, args: list, kwargs: dict) -> dict:
    """执行一次并记录全部可观测行为。"""
    buf = io.StringIO()
    rec: dict[str, Any] = {"ret": None, "exc": None, "out": ""}
    try:
        with contextlib.redirect_stdout(buf):
            rec["ret"] = canon(fn(*args, **kwargs))
    except Exception as e:  # noqa: BLE001  —— 异常本身就是要记录的行为
        rec["exc"] = f"{type(e).__name__}: {e}"
        rec["ret"] = None
    rec["out"] = buf.getvalue()
    rec["hash"] = hashlib.sha256(
        json.dumps([rec["ret"], rec["exc"], rec["out"]],
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    return rec


def record(fn: Callable, cases: list[dict], repeats: int = 3) -> dict:
    """录制。每条用例跑 `repeats` 遍，三遍不一致即判为**重放不稳定**。

    不稳定通常意味着目标依赖真实时钟、随机数或外部状态而未被声明。
    此时签发通行证是有害的 —— 它会给一个本来就不可复现的东西背书。
    """
    out, unstable = [], []
    for i, c in enumerate(cases):
        runs = [observe(fn, c.get("args", []), c.get("kwargs", {}))
                for _ in range(repeats)]
        hs = {r["hash"] for r in runs}
        if len(hs) > 1:
            unstable.append({"idx": i, "case": c, "hashes": sorted(hs)})
        out.append({"idx": i, "case": c, "source": c.get("source", "declared"),
                    **runs[0]})
    return {"cases": out, "unstable": unstable, "repeats": repeats}


def compare(base: dict, now: dict) -> list[dict]:
    """逐条比对。返回差异列表，空列表表示行为完全一致。"""
    diffs = []
    bi = {c["idx"]: c for c in base["cases"]}
    for c in now["cases"]:
        b = bi.get(c["idx"])
        if b is None:
            diffs.append({"idx": c["idx"], "why": "改后多出一条用例，基线里没有"})
            continue
        if b["hash"] == c["hash"]:
            continue
        where = []
        for k, label in (("ret", "返回值"), ("exc", "异常"), ("out", "标准输出")):
            if b[k] != c[k]:
                where.append({"字段": label, "改前": _cut(b[k]), "改后": _cut(c[k])})
        diffs.append({"idx": c["idx"], "case": c["case"],
                      "source": c.get("source"), "差异": where})
    for idx in set(bi) - {c["idx"] for c in now["cases"]}:
        diffs.append({"idx": idx, "why": "改后少了一条用例"})
    return diffs


def _cut(v: Any, n: int = 120) -> str:
    s = "" if v is None else str(v)
    return s if len(s) <= n else s[:n] + "…"
