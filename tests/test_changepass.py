"""工具自身的测试。跑法：python -m unittest discover -s tests

一个检查工具最该被检查的两件事：
  · 它会不会把没变的东西报成变了（假阳性）；
  · 它会不会把变了的东西放过去（假阴性）。
两者都测，并且额外测「重放不稳定时必须拒签」——
那是本工具唯一允许在没有行为差异时也拒签的情形。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from changepass import inputs, passport, recorder  # noqa: E402


def f_ok(values: list, scale: float = 1.0) -> list:
    if len(values) == 0:
        raise ValueError("空")
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) * scale for v in values]


def f_same(values: list, scale: float = 1.0) -> list:
    """写法不同，行为相同。"""
    if not values:
        raise ValueError("空")
    a, b = min(values), max(values)
    return [0.0] * len(values) if a == b else [(v - a) / (b - a) * scale
                                               for v in values]


def f_changed(values: list, scale: float = 1.0) -> list:
    """全等输入时 0.0 变 1.0。"""
    if not values:
        raise ValueError("空")
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) * scale for v in values]


_n = {"i": 0}


def f_unstable(values: list, scale: float = 1.0) -> list:
    """每次调用结果都不同 —— 模拟未声明的外部状态依赖。"""
    _n["i"] += 1
    return [_n["i"]]


CASES = [{"args": [[1, 2, 3]], "kwargs": {}, "source": "declared"},
         {"args": [[5, 5]], "kwargs": {}, "source": "declared"},
         {"args": [[]], "kwargs": {}, "source": "declared"}]


class TestCompare(unittest.TestCase):
    def test_等价改写不报差异(self):
        base = recorder.record(f_ok, CASES)
        now = recorder.record(f_same, CASES)
        self.assertEqual(recorder.compare(base, now), [],
                         "写法不同但行为相同，不应报出任何差异")

    def test_行为改变必被检出(self):
        base = recorder.record(f_ok, CASES)
        now = recorder.record(f_changed, CASES)
        diffs = recorder.compare(base, now)
        self.assertTrue(diffs, "全等输入上 0.0→1.0 必须被检出")
        self.assertTrue(any(d.get("idx") == 1 for d in diffs),
                        "差异应落在 [5,5] 这条用例上")

    def test_异常路径也算行为(self):
        base = recorder.record(f_ok, [CASES[2]])
        self.assertIn("ValueError", base["cases"][0]["exc"] or "",
                      "抛出的异常必须被记录为行为的一部分")

    def test_重放不稳定必须拒签(self):
        rec = recorder.record(f_unstable, CASES[:1], repeats=3)
        self.assertTrue(rec["unstable"], "三遍结果不同应判为不稳定")
        p, code = passport.issue("x", {"declared": 1}, [], rec["unstable"], 3)
        self.assertEqual(code, passport.REFUSE_UNSTABLE)
        self.assertEqual(p["通行证"], "拒签")


class TestInputs(unittest.TestCase):
    def test_边界值按注解生成(self):
        cs = inputs.boundary(f_ok, limit=20)
        self.assertTrue(cs, "应能按签名补出边界值")
        self.assertTrue(all(c["source"] == "boundary" for c in cs))

    def test_只有声明用例时标记覆盖不足(self):
        p, _ = passport.issue("x", {"declared": 3, "sampled": 0, "boundary": 0},
                              [], [], 3)
        self.assertTrue(any("覆盖不足" in n for n in p["说明"]),
                        "只跑声明用例必须被标记覆盖不足")


if __name__ == "__main__":
    unittest.main(verbosity=2)
