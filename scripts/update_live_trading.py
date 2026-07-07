#!/usr/bin/env python3.12
"""一键更新虚拟实盘 — 拉数据 → 生成JSON → 生成3-Tab HTML

流程:
  1. 检查 DuckDB 最新交易日, 确定 MTM_DATE
  2. 如有缺失数据, 运行 incremental_update.py 拉取
  3. 运行 gen_simulation_v2.py 生成 JSON (信号日6/30, 估值日=最新交易日)
  4. 运行 gen_3tab_html.py 生成 3-Tab HTML
  5. 输出最终文件路径

用法:
  python scripts/update_live_trading.py                  # 全自动
  python scripts/update_live_trading.py --mtm-date 2026-07-03  # 指定估值日
  python scripts/update_live_trading.py --skip-fetch      # 跳过拉数据
"""
import subprocess, sys, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path("g:/quant-agent-team")
PYTHON = r"C:\Users\Administrator\.local\bin\python3.12.exe"
WORK_DIR = Path(r"c:\Users\Administrator\.trae-cn\work\6a43d6ab9a733c5abd7c4776")

def run(cmd, cwd=None, desc=""):
    print(f"\n{'='*60}", flush=True)
    print(f"[step] {desc}", flush=True)
    print(f"[cmd]  {cmd}", flush=True)
    print(f"{'='*60}", flush=True)
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=False)
    if result.returncode != 0:
        print(f"[error] {desc} 失败 (exit={result.returncode})", flush=True)
        sys.exit(1)
    print(f"[ok] {desc} 完成", flush=True)

def main():
    parser = argparse.ArgumentParser(description="一键更新虚拟实盘")
    parser.add_argument("--mtm-date", default=None, help="估值日 (默认: DuckDB最新交易日)")
    parser.add_argument("--signal-date", default="2026-06-30", help="信号日 (默认: 2026-06-30)")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过拉数据步骤")
    args = parser.parse_args()

    t0 = datetime.now()
    print("=" * 60, flush=True)
    print(f"虚拟实盘一键更新 | {t0.strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"信号日: {args.signal_date}", flush=True)
    print(f"估值日: {args.mtm_date or '自动检测'}", flush=True)
    print("=" * 60, flush=True)

    # Step 1: 拉数据
    if not args.skip_fetch:
        end_date = args.mtm_date.replace("-", "") if args.mtm_date else datetime.now().strftime("%Y%m%d")
        run(
            f'{PYTHON} "{ROOT / "scripts" / "incremental_update.py"}" --end {end_date}',
            cwd=str(ROOT),
            desc="拉取最新行情数据"
        )
    else:
        print("\n[skip] 跳过拉数据步骤", flush=True)

    # Step 2: 生成 JSON (gen_simulation_v2.py)
    sim_cmd = f'{PYTHON} "{WORK_DIR / "gen_simulation_v2.py"}"'
    if args.mtm_date:
        sim_cmd += f' --mtm-date {args.mtm_date}'
    if args.signal_date:
        sim_cmd += f' --signal-date {args.signal_date}'
    run(sim_cmd, cwd=str(ROOT), desc="生成实盘模拟JSON")

    # Step 3: 生成 3-Tab HTML (gen_3tab_html.py)
    run(
        f'{PYTHON} "{WORK_DIR / "gen_3tab_html.py"}"',
        cwd=str(ROOT),
        desc="生成3-Tab HTML页面"
    )

    # 输出结果
    dt = (datetime.now() - t0).total_seconds()
    live_dir = ROOT / "reports" / "v51_production" / "live_signals"
    print(f"\n{'='*60}", flush=True)
    print(f"完成! 总耗时 {dt:.0f}秒", flush=True)
    print(f"文件目录: {live_dir}", flush=True)
    print(f"{'='*60}", flush=True)

if __name__ == "__main__":
    main()
