"""演示目标：一个 10 行的归一化函数。changepass 不关心它做什么，只关心它的行为变没变。"""


def normalize(values: list, scale: float = 1.0) -> list:
    if not values:
        raise ValueError("values 不能为空")
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [round((v - lo) / (hi - lo) * scale, 6) for v in values]


def _demo_calls():
    """供语料采样扫到的真实调用点。"""
    normalize([1, 2, 3])
    normalize([0.5, 0.5], scale=2.0)
    normalize([10, -10, 0], 100.0)
