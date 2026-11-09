"""changepass 命令行入口。

    python -m changepass record --target 路径.py:函数 --out .cp/base.json
    python -m changepass verify --target 路径.py:函数 --base .cp/base.json

退出码：0 签发　3 拒签（行为不一致）　4 拒签（重放不稳定）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import inputs, passport, recorder


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="changepass", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["record", "verify"])
    ap.add_argument("--target", required=True, help="路径.py:函数名")
    ap.add_argument("--out", default=".cp/base.json")
    ap.add_argument("--base", default=".cp/base.json")
    ap.add_argument("--cases", default="", help="声明用例 json，默认目标旁的 用例.json")
    ap.add_argument("--repo", default=".", help="语料采样的扫描根目录")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--passport", default=".cp/通行证.json")
    a = ap.parse_args(argv)

    path, fn_name = a.target.rsplit(":", 1)
    fn = recorder.load_target(a.target)

    if a.cmd == "verify":
        # 输入集**在录制时定死，原样重放** —— 不在 verify 时重建。
        #
        # 这不是优化，是一处必须修的设计缺陷：语料采样扫的是仓库里对该函数的
        # 调用点，而重构往往连调用点一起改。实测中目标文件被改写后
        # `_demo_calls()` 消失，采样从 3 条变 0 条，**全部索引整体错位**，
        # 于是把一次无辜的重构报成十几处差异，而且打印出来的实参
        # 与它旁边的返回值根本对不上（空列表显示返回两个元素）。
        # 「重放同一组输入」这句话要成立，输入就不能在两次之间重新计算。
        base_p = Path(a.base)
        if not base_p.exists():
            print(f"找不到基线 {base_p}，先跑 record。", file=sys.stderr)
            return passport.REFUSE_DIFF
        base = json.loads(base_p.read_text(encoding="utf-8"))
        cases = [{**c["case"], "source": c.get("source", "declared")}
                 for c in base["cases"]]
        counts = base.get("counts", {})
        rec = recorder.record(fn, cases, a.repeats)
        # 重放后把 idx 对回基线的 idx，顺序一致所以逐位对应
        for i, c in enumerate(rec["cases"]):
            c["idx"] = base["cases"][i]["idx"]
        diffs = recorder.compare(base, rec)
        p, code = passport.issue(a.target, counts, diffs, rec["unstable"], a.repeats)
        passport.save(p, Path(a.passport))
        print(passport.render(p))
        return code

    cases_file = Path(a.cases) if a.cases else Path(path).with_name("用例.json")
    cases, counts = inputs.build(Path(a.repo), fn, fn_name, cases_file)
    if not cases:
        print("输入集为空：没有声明用例、没采到调用点、也补不出边界值。", file=sys.stderr)
        return passport.REFUSE_DIFF

    rec = recorder.record(fn, cases, a.repeats)

    if a.cmd == "record":
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"target": a.target, "counts": counts, **rec},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已录制 {len(cases)} 条（声明 {counts['declared']}／"
              f"采样 {counts['sampled']}／边界 {counts['boundary']}）→ {out}")
        if rec["unstable"]:
            print(f"⚠ 其中 {len(rec['unstable'])} 条重放不稳定；"
                  "基线本身就不可复现，verify 一定会拒签。")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
