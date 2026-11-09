"""改写二：只把 hi - lo 提成了变量 span。看起来毫无风险。

实际上改了行为：原版在 hi == lo 时**先返回**，这一版**先算减法**。
碰上 [None] 这类输入，原版返回 [0.0]，这一版抛 TypeError。

这是本工具最值得被看见的一类命中 —— 没有任何人读 diff 会觉得这里有问题，
它也不会被只看返回值类型的检查发现。
"""


def normalize(values: list, scale: float = 1.0) -> list:
    if len(values) == 0:
        raise ValueError("values 不能为空")
    lo = min(values)
    hi = max(values)
    span = hi - lo
    if span == 0:
        return [0.0] * len(values)
    out = []
    for v in values:
        out.append(round((v - lo) / span * scale, 6))
    return out
