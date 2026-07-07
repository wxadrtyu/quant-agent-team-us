"""下跌压力测试 — 在风控启用下检验策略极端回撤承受力。

三种场景:
  1. historical: 用A股历史急跌段作为路径替换
  2. synthetic_shock: 在持仓期注入单日 -8%/-10% 跳空
  3. bootstrap: 对日收益做 fat-tail block-bootstrap 重采样

设计原则: 压力测试是验证层，不影响HPO选参。仅在部署前运行，超限策略进review。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from .risk_overlay import RiskOverlay, default_live_overlay, apply_trailing_stop, position_scales


@dataclass
class StressResult:
    """单个策略在单个压力场景下的测试结果"""
    scenario: str           # historical / synthetic_shock / bootstrap
    base_mdd: float         # 无压力MDD
    stress_mdd: float       # 压力下MDD
    base_return: float      # 无压力收益
    stress_return: float    # 压力下收益
    stop_trigger_rate: float  # 止损触发比例
    survived: bool          # stress_mdd <= mdd_limit

    def summary(self) -> str:
        flag = "PASS" if self.survived else "FAIL"
        return (f"[{self.scenario}] {flag} "
                f"ret {self.base_return:+.1%}→{self.stress_return:+.1%}, "
                f"MDD {self.base_mdd:.1%}→{self.stress_mdd:.1%}, "
                f"止损触发率 {self.stop_trigger_rate:.0%}")


# ── 场景1: 历史急跌段 ──

# A股历史急跌段 (收盘价pct_chg)
HISTORICAL_SHOCKS = {
    "2024-09-24急涨急跌": [
        # 2024-09-24~10-08: 政策刺激暴涨后回落
        +0.045, +0.032, +0.028, +0.085, +0.041, -0.058, -0.032, +0.015,
    ],
    "2025-04-07关税冲击": [
        # 2025-04-07~04-11: 关税冲击连续下跌
        -0.072, -0.018, +0.012, -0.035, -0.028,
    ],
    "2024-01~02微盘股崩盘": [
        # 2024-01-29~02-05: 微盘股连续跌停
        -0.038, -0.045, -0.052, -0.061, -0.038, -0.025,
    ],
}


def apply_historical_shock(path: Sequence[float], shock_returns: Sequence[float]) -> List[float]:
    """将历史急跌段的日收益率叠加到价格路径上。

    从路径中段开始注入，保持起点和终点不变。
    """
    if len(path) < 3 or len(shock_returns) == 0:
        return list(path)

    n = len(path)
    inject_start = n // 3  # 从1/3处开始注入
    inject_len = min(len(shock_returns), n - inject_start - 1)

    stressed = list(path)
    for i in range(inject_len):
        idx = inject_start + i
        # 用前一日价格 * (1 + shock_return) 替换
        stressed[idx] = stressed[idx - 1] * (1.0 + shock_returns[i])

    # 重新计算注入后的后续路径 (保持相对比例)
    if inject_start + inject_len < n:
        old_seg_start = path[inject_start + inject_len - 1]
        new_seg_start = stressed[inject_start + inject_len - 1]
        ratio = new_seg_start / old_seg_start if old_seg_start > 0 else 1.0
        for i in range(inject_start + inject_len, n):
            stressed[i] = path[i] * ratio

    return stressed


# ── 场景2: 合成冲击 ──

def apply_synthetic_shock(path: Sequence[float], shock_pct: float = -0.08) -> List[float]:
    """在路径中点注入单日跳空冲击 (默认-8%)。"""
    if len(path) < 3:
        return list(path)

    mid = len(path) // 2
    stressed = list(path)

    # 注入跳空
    old_mid = stressed[mid]
    stressed[mid] = stressed[mid - 1] * (1.0 + shock_pct)

    # 后续路径按比例调整
    if mid + 1 < len(path):
        ratio = stressed[mid] / old_mid if old_mid > 0 else 1.0
        for i in range(mid + 1, len(path)):
            stressed[i] = stressed[i] * ratio

    return stressed


# ── 场景3: Bootstrap ──

def block_bootstrap_path(path: Sequence[float], block_size: int = 5,
                         n_simulations: int = 200, seed: int = 0) -> List[List[float]]:
    """对价格路径做 block-bootstrap 重采样，生成多条替代路径。

    返回 n_simulations 条重采样路径，取MDD的95分位。
    """
    if len(path) < block_size * 2:
        return [list(path)]

    rng = np.random.RandomState(seed)
    # 转为日收益率
    returns = np.diff(np.array(path, dtype=float))
    n = len(returns)

    # 构造重叠块
    blocks = []
    for i in range(n - block_size + 1):
        blocks.append(returns[i:i + block_size])

    if not blocks:
        return [list(path)]

    all_paths = []
    for _ in range(n_simulations):
        # 随机拼接块直到长度>=n
        sampled = []
        while len(sampled) < n:
            block = blocks[rng.randint(len(blocks))]
            sampled.extend(block)
        sampled = sampled[:n]

        # 重建价格路径
        boot_path = [path[0]]
        for r in sampled:
            boot_path.append(boot_path[-1] * (1.0 + r))
        all_paths.append(boot_path)

    return all_paths


# ── 压力测试主入口 ──

def run_drawdown_stress(
    stock_paths: List[Tuple[str, List[float], float]],  # [(code, path, entry_price), ...]
    risk: Optional[RiskOverlay] = None,
    mdd_limit: float = 0.20,
    scenarios: Tuple[str, ...] = ("historical", "synthetic_shock", "bootstrap"),
    n_bootstrap: int = 200,
    seed: int = 0,
) -> List[StressResult]:
    """对一组持仓路径运行下跌压力测试。

    参数:
        stock_paths: 每只股票的 (code, 日收盘价路径, 入场价)
        risk: 风控层 (默认用 default_live_overlay)
        mdd_limit: MDD约束线
        scenarios: 要运行的场景
        n_bootstrap: bootstrap重采样次数
        seed: 随机种子

    返回: 每个场景的 StressResult 列表
    """
    risk = risk or default_live_overlay()
    results = []

    # 基准: 正常带风控
    base_returns = []
    base_stop_count = 0
    for code, path, entry_price in stock_paths:
        exit_price, stopped = apply_trailing_stop(path, entry_price, risk)
        ret = exit_price / entry_price - 1.0 if entry_price > 0 else 0.0
        base_returns.append(ret)
        if stopped:
            base_stop_count += 1

    base_return = float(np.mean(base_returns)) if base_returns else 0.0
    base_mdd = _calc_portfolio_mdd([p for _, p, _ in stock_paths])
    base_stop_rate = base_stop_count / len(stock_paths) if stock_paths else 0.0

    # 场景1: 历史急跌
    if "historical" in scenarios:
        worst_mdd = base_mdd
        worst_ret = base_return
        worst_stop_rate = base_stop_rate

        for shock_name, shock_returns in HISTORICAL_SHOCKS.items():
            stress_returns = []
            stress_stop_count = 0
            stress_mdds = []

            for code, path, entry_price in stock_paths:
                stressed_path = apply_historical_shock(path, shock_returns)
                exit_price, stopped = apply_trailing_stop(stressed_path, entry_price, risk)
                ret = exit_price / entry_price - 1.0 if entry_price > 0 else 0.0
                stress_returns.append(ret)
                if stopped:
                    stress_stop_count += 1
                stress_mdds.append(_calc_path_mdd(stressed_path))

            avg_ret = float(np.mean(stress_returns)) if stress_returns else 0.0
            avg_mdd = float(np.mean(stress_mdds)) if stress_mdds else 0.0
            stop_rate = stress_stop_count / len(stock_paths) if stock_paths else 0.0

            # 取最差的历史场景
            if avg_mdd > worst_mdd:
                worst_mdd = avg_mdd
                worst_ret = avg_ret
                worst_stop_rate = stop_rate

        results.append(StressResult(
            scenario="historical",
            base_mdd=base_mdd, stress_mdd=worst_mdd,
            base_return=base_return, stress_return=worst_ret,
            stop_trigger_rate=worst_stop_rate,
            survived=worst_mdd <= mdd_limit,
        ))

    # 场景2: 合成冲击
    if "synthetic_shock" in scenarios:
        for shock_pct in [-0.08, -0.10]:
            stress_returns = []
            stress_stop_count = 0
            stress_mdds = []

            for code, path, entry_price in stock_paths:
                stressed_path = apply_synthetic_shock(path, shock_pct)
                exit_price, stopped = apply_trailing_stop(stressed_path, entry_price, risk)
                ret = exit_price / entry_price - 1.0 if entry_price > 0 else 0.0
                stress_returns.append(ret)
                if stopped:
                    stress_stop_count += 1
                stress_mdds.append(_calc_path_mdd(stressed_path))

            avg_ret = float(np.mean(stress_returns)) if stress_returns else 0.0
            avg_mdd = float(np.mean(stress_mdds)) if stress_mdds else 0.0
            stop_rate = stress_stop_count / len(stock_paths) if stock_paths else 0.0

            results.append(StressResult(
                scenario=f"synthetic_shock_{abs(shock_pct)*100:.0f}%",
                base_mdd=base_mdd, stress_mdd=avg_mdd,
                base_return=base_return, stress_return=avg_ret,
                stop_trigger_rate=stop_rate,
                survived=avg_mdd <= mdd_limit,
            ))

    # 场景3: Bootstrap
    if "bootstrap" in scenarios:
        all_boot_mdds = []
        all_boot_returns = []
        all_boot_stops = 0
        total_paths = 0

        for code, path, entry_price in stock_paths:
            boot_paths = block_bootstrap_path(path, block_size=5,
                                               n_simulations=n_bootstrap, seed=seed)
            for bp in boot_paths:
                exit_price, stopped = apply_trailing_stop(bp, entry_price, risk)
                ret = exit_price / entry_price - 1.0 if entry_price > 0 else 0.0
                all_boot_returns.append(ret)
                all_boot_mdds.append(_calc_path_mdd(bp))
                if stopped:
                    all_boot_stops += 1
                total_paths += 1

        if all_boot_mdds:
            p95_mdd = float(np.percentile(all_boot_mdds, 95))
            p95_ret = float(np.percentile(all_boot_returns, 5))  # 5分位收益(最差)
            stop_rate = all_boot_stops / total_paths if total_paths > 0 else 0.0
        else:
            p95_mdd = base_mdd
            p95_ret = base_return
            stop_rate = 0.0

        results.append(StressResult(
            scenario="bootstrap_p95",
            base_mdd=base_mdd, stress_mdd=p95_mdd,
            base_return=base_return, stress_return=p95_ret,
            stop_trigger_rate=stop_rate,
            survived=p95_mdd <= mdd_limit,
        ))

    return results


def _calc_path_mdd(path: Sequence[float]) -> float:
    """计算单条价格路径的MDD"""
    if not path or len(path) < 2:
        return 0.0
    peak = path[0]
    max_dd = 0.0
    for p in path:
        peak = max(peak, p)
        dd = (peak - p) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


def _calc_portfolio_mdd(paths: List[List[float]]) -> float:
    """计算组合MDD (取所有路径MDD的平均值作为近似)"""
    if not paths:
        return 0.0
    mdds = [_calc_path_mdd(p) for p in paths]
    return float(np.mean(mdds)) if mdds else 0.0
