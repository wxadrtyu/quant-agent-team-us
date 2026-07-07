---
name: "live-trading-update"
description: "更新虚拟实盘Dashboard: 从live_pool_strategies表读策略→拉数据→重算盈亏→生成4-Tab HTML页面. Invoke when user asks to update live trading, refresh dashboard, or pull latest market data for the paper trading portfolio."
---

# 虚拟实盘一键更新

## 触发条件

当用户说以下任何一种时, 立即执行本skill:
- "更新实盘" / "刷新实盘" / "实盘更新"
- "拉数据更新页面" / "更新dashboard"
- "跑到今天" / "更新到最新"
- 任何涉及虚拟实盘数据刷新的请求

## 核心原则

**实盘池里有什么就实盘什么, 不截断、不筛选、不淘汰**
- 策略池来源: DuckDB `live_pool_strategies` 表 (NOT hardcoded字典)
- 表里所有 `status='active'` 的策略全部参与实盘
- 新策略加入表后自动生效, 无需改代码
- 每类不限制数量

**修改代码前必须先提交当前版本到git:**
```bash
cd g:\quant-agent-team; git add -A; git commit -m "backup before change"
```
**严禁在未提交的情况下修改已有代码, 否则无法回滚!**

**实盘HTML只能用gen_simulation_v2.py→gen_3tab_html.py流程生成, 禁止用任何其他脚本(如update_live_html.py)覆盖HTML样式!**

**只做用户要求的改动, 不要擅自改其他部分:**
- 用户说"加OOS列" → 只加OOS列, 不要改排序、布局、交互逻辑
- 用户说"改排序" → 只改排序, 不要加字段
- 任何超出用户明确要求的改动都是禁止的

**估值日必须用最新交易日, 不要用过期日期!**
- 每次更新实盘前, 先拉数据(incremental_update.py), 数据拉完后会显示 max_date
- 估值日 = 数据拉完后的 max_date (即最近交易日)
- 信号日固定 2026-06-30 (每月最后一个交易日), 估值日随时间推移自动更新
- 例如: 7/7更新 → 拉数据到7/6 → 估值日=2026-07-06
- **严禁用过期估值日(如7/3)更新实盘, 除非用户明确指定**

## 完整流程 (3步)

```
拉数据 → 读策略表重算盈亏(用最新交易日做估值日) → 生成页面
```

### Step 1: 拉数据

```bash
C:\Users\Administrator\.local\bin\python3.12.exe "g:\quant-agent-team\scripts\incremental_update.py"
```

`incremental_update.py` 会自动完成:
1. 对比 trade_cal 和 market_daily, 找出缺失的交易日
2. 用 Tushare pro.daily 拉取全市场行情 → market_daily
3. 用 AkShare 补指数数据 → index_daily
4. **重建 factor_panel** (从 market_daily 全量重算所有因子)

**跳过因子面板重建** (如果因子没变, 只补行情):
```bash
C:\Users\Administrator\.local\bin\python3.12.exe "g:\quant-agent-team\scripts\incremental_update.py" --skip-panel
```

### Step 2: 重算盈亏 + 生成页面

**一键脚本 (推荐, 自动用最新交易日做估值日):**
```bash
C:\Users\Administrator\.local\bin\python3.12.exe "g:\quant-agent-team\scripts\update_live_trading.py" --skip-fetch
```
> 注意: 不加 --mtm-date 时, 脚本会自动检测最新交易日作为估值日

**或分步执行:**
```bash
# 1. 从live_pool_strategies表读策略, 重算盈亏, 写回表+生成JSON
C:\Users\Administrator\.local\bin\python3.12.exe "c:\Users\Administrator\.trae-cn\work\6a43d6ab9a733c5abd7c4776\gen_simulation_v2.py"

# 2. 从JSON生成4-Tab HTML (自动查找最新JSON)
C:\Users\Administrator\.local\bin\python3.12.exe "c:\Users\Administrator\.trae-cn\work\6a43d6ab9a733c5abd7c4776\gen_3tab_html.py"
```

**手动指定估值日 (仅特殊情况下使用):**
```bash
C:\Users\Administrator\.local\bin\python3.12.exe "g:\quant-agent-team\scripts\update_live_trading.py" --skip-fetch --mtm-date 2026-07-06
```

## 策略池管理

**策略池在 DuckDB `live_pool_strategies` 表中维护, 不在代码里硬编码.**

### 表结构

| 列名 | 类型 | 说明 |
|------|------|------|
| sid | VARCHAR | 策略ID (如 ZZ-001, T-001) |
| category | VARCHAR | 分类 (如 N10-等权-低MDD, n7_等权_低MDD) |
| n_class | INTEGER | 持仓数分类 (30/10/7/5) |
| weighting | VARCHAR | 加权方式 (equal/HR11/等权) |
| mdd_label | VARCHAR | MDD标签 (低MDD/非低MDD) |
| mdd_limit | DOUBLE | MDD限制 (0.20=低, 1.0=非低) |
| factors | VARCHAR | 因子列表 (逗号分隔) |
| max_n | INTEGER | 最大持仓数 |
| ir | DOUBLE | 回测IR |
| status | VARCHAR | 状态 (active=启用) |
| signal_date | DATE | 信号日 |
| mtm_date | DATE | 估值日 |
| pnl | DOUBLE | 盈亏 (小数) |
| excess | DOUBLE | 超额收益 |
| hpo_oos | DOUBLE | 回测OOS总收益 (从rolling结果读取, 非HPO年化) |
| hpo_mdd | DOUBLE | 回测最大回撤 (从rolling结果读取) |
| backtest_oos | DOUBLE | 滚动回测OOS总收益 (原始值, 不被覆盖) |
| backtest_mdd | DOUBLE | 滚动回测最大回撤 (原始值, 不被覆盖) |
| stocks_json | VARCHAR | 持仓明细JSON |

### 添加新策略

向 `live_pool_strategies` 表插入一行:
```sql
INSERT INTO live_pool_strategies
(sid, category, n_class, weighting, mdd_label, mdd_limit, factors, max_n, ir, status)
VALUES
('ZZ-090', 'n5_等权_低MDD', 5, '等权', '低MDD', 0.20, 'drawdown_5d,cmf_7,ret_20d', 5, 1.189, 'active');
```

**添加前检查**: 新策略用到的因子必须在 `factor_panel.py` 中已实现, 否则运行时会报 `column not found`.

### 查看当前策略池
```bash
C:\Users\Administrator\.local\bin\python3.12.exe -c "import duckdb; con=duckdb.connect('g:/quant-agent-team/quant.duckdb',read_only=True); print(con.execute('SELECT sid,category,ir FROM live_pool_strategies WHERE status=\\'active\\' ORDER BY category,ir DESC').fetchdf().to_string()); con.close()"
```

## 输出文件

所有文件位于: `g:\quant-agent-team\reports\v51_production\live_signals\`

| 文件 | 说明 |
|------|------|
| `simulation_v2_{MMDD}_{MMDD}.json` | 策略持仓和盈亏数据 (信号日_估值日) |
| `simulation_v2_detail_{MMDD}_{MMDD}.html` | 4-Tab交互式页面 (动态加载JSON) |

## 页面结构

4个Tab (默认选中全策略):
- **全策略**: 所有策略盈亏总览(按盈亏排序) + 唯一股票汇总(按策略数排序)
- **N30**: 大持仓, 低风险 (5个模块)
- **N10**: 中持仓
- **N5**: 精选持仓, 高集中度

每个N-tab包含5个模块:
1. 策略盈亏卡片 (策略数/盈亏/平均收益/唯一股票/跑赢基准)
2. 策略盈亏总览表 (含OOS、回测MDD、盈亏迷你进度条)
3. 分类汇总表
4. 唯一股票汇总表 (按策略数排序)
5. 各策略持仓明细 (可折叠, 前3个默认展开)

## 数据约束

- **信号日**: 固定 2026-06-30 (每月最后一个交易日, 后续可改为按rebalance周期)
- **估值日**: 自动检测最新交易日 (可手动指定)
- **注意**: 信号日 ≠ 估值日, 否则P&L全为0 (无持有期)
- **回测数据截止**: 2026-06-29 (严禁用于回测)
- **7月以后的数据**: 仅用于实盘估值, 不用于回测
- **每策略本金**: ¥300,000
- **基准**: HS300 (csi300, index_daily表中index_name='csi300')
- **股票池**: HS300成分股
- **Tushare代理**: https://fastapic.stockai888.top, 限速100次/分钟

## 关键文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 一键脚本 | `g:\quant-agent-team\scripts\update_live_trading.py` | 编排脚本 |
| 数据更新 | `g:\quant-agent-team\scripts\incremental_update.py` | Tushare拉数据+重建factor_panel |
| **策略池表** | `g:\quant-agent-team\quant.duckdb` → `live_pool_strategies` | **策略池唯一数据源** |
| 因子面板 | `g:\quant-agent-team\src\quant_agent_team\factor_panel.py` | 因子计算逻辑 (新因子在这里加) |
| 模拟引擎 | `c:\Users\Administrator\.trae-cn\work\6a43d6ab9a733c5abd7c4776\gen_simulation_v2.py` | 从表读策略+盈亏计算+写回表 |
| HTML生成 | `c:\Users\Administrator\.trae-cn\work\6a43d6ab9a733c5abd7c4776\gen_3tab_html.py` | 4-Tab页面模板 |
| 操作规格 | `g:\quant-agent-team\reports\v51_production\虚拟实盘操作规格.md` | 标准操作规范 |
| 策略注册表 | `g:\quant-agent-team\reports\v51_production\strategy_registry.md` | 全部策略记录 |

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `Connection already closed` | DuckDB连接在con.close()后仍被使用 | 预取所有数据到dict后再close() |
| P&L全为0 | factor_panel缺少估值日数据 | 从market_daily取估值价 (不用factor_panel) |
| `column "xxx" not found` | 新策略用了factor_panel没有的因子 | 在factor_panel.py中添加因子计算逻辑 |
| HTML数据不显示 | JSON字段名与HTML模板不匹配 | 检查pnl/n_stocks/shares等字段映射 |
| index_daily查询为空 | index_name用了中文名 | 使用 'csi300' 而非 '沪深300' |
| 策略数不对 | 代码用了硬编码的ALL_POOLS | 确保从live_pool_strategies表读取 |
