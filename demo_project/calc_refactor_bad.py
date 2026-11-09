"""改写二：看起来只是「简化」，实际改掉了两处行为。预期拒签。

  · 全等输入时原来返回 0.0，这里返回 1.0；
  · 空输入时原来抛 ValueError，这里返回 []。
两处都不会被只看返回值类型的检查发现。
"""


def normalize(values: list, scale: float = 1.0) -> list:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    return [round((v - lo) / (hi - lo) * scale, 6) for v in values]
