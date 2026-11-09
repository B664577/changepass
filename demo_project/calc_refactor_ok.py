"""改写一：换了写法，行为真的保持不变。预期签发。

关键在于保住了原版的求值顺序：hi == lo 的判断在减法之前。
"""


def normalize(values: list, scale: float = 1.0) -> list:
    if len(values) == 0:
        raise ValueError("values 不能为空")
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.0] * len(values)
    out = []
    for v in values:
        out.append(round((v - lo) / (hi - lo) * scale, 6))
    return out
