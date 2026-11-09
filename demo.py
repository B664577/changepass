"""一条命令跑完整演示：录一次基线，验两次改写。

预期：
  改写一　换写法、求值顺序不变　　　　　　　　→ 签发，退出码 0
  改写二　只把 hi-lo 提成变量 span　　　　　　→ 拒签，退出码 3
  改写三　看似简化，实则改了两处行为　　　　　→ 拒签，退出码 3

改写二是本工具最值得被看见的一类命中：没有任何人读 diff 会觉得这里有问题。
原版在 hi == lo 时先返回，改版先算减法，于是 [None] 这类输入上
原版返回 [0.0]、改版抛 TypeError。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "demo_project" / "calc.py"
BACKUP = HERE / ".cp" / "calc_原件.py"
BASE = HERE / ".cp" / "base.json"


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "changepass", *args],
                       cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    BASE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET, BACKUP)
    bar = "=" * 78
    try:
        print(bar)
        print("第 1 步　录基线（改之前）")
        print(bar)
        code, out = run(["record", "--target", "demo_project/calc.py:normalize",
                         "--out", str(BASE), "--repo", "demo_project"])
        print(out.rstrip())
        if code != 0:
            return code

        for tag, src, want in (
                ("改写一：换写法，求值顺序保持不变", "calc_refactor_ok.py", 0),
                ("改写二：只把 hi-lo 提成变量——看起来毫无风险",
                 "calc_refactor_subtle.py", 3),
                ("改写三：看似简化，实则改了两处行为",
                 "calc_refactor_bad.py", 3)):
            print("\n" + bar)
            print(f"第 2 步　{tag}　→ 验证并签发")
            print(bar)
            shutil.copy2(HERE / "demo_project" / src, TARGET)
            code, out = run(["verify", "--target", "demo_project/calc.py:normalize",
                             "--base", str(BASE), "--repo", "demo_project"])
            print(out.rstrip())
            print(f"\n[退出码 {code}　预期 {want}　"
                  + ("符合" if code == want else "**不符**") + "]")
    finally:
        shutil.copy2(BACKUP, TARGET)      # 演示不留痕，还原原件
    print("\n" + bar)
    print("演示结束，目标文件已还原。")
    print("拒签不是失败，是本工具存在的理由——一个从不拒签的通行证等于没有。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
