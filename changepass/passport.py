"""通行证的签发、拒签与序列化。

通行证上必须同时出现三样东西，少一样这张证就不该被采信：
  1. 输入集的**来源与规模**（只跑声明用例的，标记覆盖不足）；
  2. 行为是否逐条一致；
  3. 重放是否稳定（不稳定一律拒签，而不是签一张不可靠的证）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))

PASS, REFUSE_DIFF, REFUSE_UNSTABLE = 0, 3, 4


def issue(target: str, counts: dict, diffs: list, unstable: list,
          repeats: int) -> tuple[dict, int]:
    total = sum(counts.values())
    only_declared = counts.get("declared", 0) == total and total > 0
    notes: list[str] = []

    if unstable:
        verdict, code = "拒签", REFUSE_UNSTABLE
        notes.append(
            f"{len(unstable)} 条用例在 {repeats} 遍重放中结果不一致。"
            "这通常意味着目标依赖真实时钟、随机数或外部状态而未被声明。"
            "此时签发通行证是有害的——它会给一个本来就不可复现的东西背书。")
    elif diffs:
        verdict, code = "拒签", REFUSE_DIFF
        notes.append(f"{len(diffs)} 条用例上改前改后行为不一致，明细见下。")
    else:
        verdict, code = "签发", PASS
        notes.append("在下列输入集上，改前改后逐条一致。")

    if only_declared:
        notes.append(
            "⚠ 覆盖不足：本次输入集只有声明用例，没有语料采样与边界生成。"
            "声明用例检查的是我们想到要检查的性质，而重构的风险多在边界。")
    if total == 0:
        verdict, code = "拒签", REFUSE_DIFF
        notes.append("输入集为空，无从比对。")

    p = {
        "通行证": verdict,
        "目标": target,
        "签发时间（北京）": datetime.now(BJ).isoformat(timespec="seconds"),
        "输入集": {"合计": total, **counts, "每条重放遍数": repeats},
        "行为差异": diffs,
        "重放不稳定": unstable,
        "说明": notes,
        "边界": [
            "行为等价是**在给定输入集上**的等价，不是数学意义上的等价；"
            "输入集之外的行为本证不作任何承诺。",
            "未声明的副作用会让重放不稳定，本工具检出后拒签，不签发不可靠的证。",
            "本证只判断行为是否没变，不判断这次重构是否更好。",
        ],
    }
    p["指纹"] = hashlib.sha256(
        json.dumps({k: v for k, v in p.items() if k != "指纹"},
                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return p, code


def render(p: dict) -> str:
    L = [f"变更通行证　{p['通行证']}",
         f"目标　{p['目标']}",
         f"签发　{p['签发时间（北京）']}",
         ""]
    c = p["输入集"]
    L.append(f"输入集　合计 {c['合计']} 条"
             f"（声明 {c.get('declared',0)}／采样 {c.get('sampled',0)}"
             f"／边界 {c.get('boundary',0)}），每条重放 {c['每条重放遍数']} 遍")
    L.append("")
    for n in p["说明"]:
        L.append(("  " + n) if not n.startswith("⚠") else ("  " + n))
    if p["行为差异"]:
        L += ["", "行为差异明细："]
        for d in p["行为差异"][:10]:
            if "why" in d:
                L.append(f"  #{d['idx']}　{d['why']}")
                continue
            L.append(f"  #{d['idx']}　来源 {d.get('source','?')}　"
                     f"实参 {json.dumps(d['case'].get('args', []), ensure_ascii=False)[:70]}")
            for w in d["差异"]:
                L.append(f"      {w['字段']}：改前 {w['改前']!r} → 改后 {w['改后']!r}")
    if p["重放不稳定"]:
        L += ["", "重放不稳定的用例："]
        for u in p["重放不稳定"][:10]:
            L.append(f"  #{u['idx']}　{len(u['hashes'])} 种不同结果")
    L += ["", "边界："]
    for b in p["边界"]:
        L.append("  · " + b.replace("**", "「", 1).replace("**", "」", 1))
    L += ["", f"指纹 {p['指纹']}"]
    return "\n".join(L)


def save(p: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
