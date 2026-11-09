"""三类输入的生成与计数。

只跑维护者手写的用例，等于只检查「我们想到要检查的性质」。
一次重构真正的风险在边界，而边界恰恰是当初写用例的人没想到的地方。
所以输入集必须有三个来源，且在通行证上**分别计数**：

  declared  声明用例 —— 维护者手写，覆盖已知语义
  sampled   语料采样 —— 从仓库自身的调用点抽取真实实参
  boundary  边界生成 —— 按参数类型补空值、极值、异常形状

只有 declared 的通行证会被标记「覆盖不足」。
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any, Callable

# 按注解类型补的边界值。顺序即优先级，取前 N 个。
BOUNDARY: dict[str, list[Any]] = {
    "int": [0, -1, 1, 2 ** 31, -(2 ** 31)],
    "float": [0.0, -0.0, 1e-300, 1e300, float("inf"), float("nan")],
    "str": ["", " ", "0", "\n", "中文", "a" * 1000],
    "list": [[], [None], list(range(3))],
    "dict": [{}, {"k": None}],
    "bool": [True, False],
    "NoneType": [None],
}
ANY_BOUNDARY = [None, 0, "", [], {}]


def declared(path: Path) -> list[dict]:
    """读 `用例.json`。没有就返回空 —— 空不是错误，但会反映在覆盖计数上。"""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"args": c.get("args", []), "kwargs": c.get("kwargs", {}),
             "source": "declared"} for c in data]


def sampled(repo: Path, fn_name: str, limit: int = 12) -> list[dict]:
    """扫仓库里对该函数的调用点，把**字面量实参**取出来当用例。

    只取字面量：变量名在静态阶段取不到值，猜它等于编造输入。
    取不到就少取几条，并如实计数，不拿编的数去凑。
    """
    out: list[dict] = []
    for py in sorted(repo.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = getattr(f, "id", None) or getattr(f, "attr", None)
            if name != fn_name:
                continue
            try:
                args = [ast.literal_eval(a) for a in node.args]
                kwargs = {k.arg: ast.literal_eval(k.value)
                          for k in node.keywords if k.arg}
            except (ValueError, SyntaxError):
                continue      # 非字面量实参，跳过而不是猜
            out.append({"args": args, "kwargs": kwargs, "source": "sampled",
                        "from": f"{py.name}:{node.lineno}"})
            if len(out) >= limit:
                return out
    return out


def boundary(fn: Callable, limit: int = 10) -> list[dict]:
    """按签名给每个位置参数补边界值，其余参数取第一个边界值。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    params = [p for p in sig.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if not params:
        return []

    def pool(p) -> list[Any]:
        ann = p.annotation
        key = getattr(ann, "__name__", None) or str(ann)
        return BOUNDARY.get(key, ANY_BOUNDARY)

    base = [pool(p)[0] for p in params]
    out: list[dict] = []
    for i, p in enumerate(params):
        for v in pool(p):
            args = list(base)
            args[i] = v
            out.append({"args": args, "kwargs": {}, "source": "boundary",
                        "varies": p.name})
            if len(out) >= limit:
                return out
    return out


def build(repo: Path, fn: Callable, fn_name: str,
          cases_file: Path) -> tuple[list[dict], dict[str, int]]:
    cs = declared(cases_file) + sampled(repo, fn_name) + boundary(fn)
    # 去重：同一组实参只跑一次
    seen, uniq = set(), []
    for c in cs:
        k = json.dumps([c["args"], c["kwargs"]], ensure_ascii=False,
                       sort_keys=True, default=repr)
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    counts = {s: sum(1 for c in uniq if c["source"] == s)
              for s in ("declared", "sampled", "boundary")}
    return uniq, counts
