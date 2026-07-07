# 2026-03-26 Quant Research Source Map

## Research Goal

Support the first round of medium-short horizon China A-share stock-selection research under the user's KPI requirements:

- sharpe > 2
- trade_win_rate > 80%
- annualized_return > 20%
- max_drawdown < 30%

The user also requires explicit buy and sell points, so the final candidate strategies must be rule-based rather than score-only.

## Source Categories

### 1. Core momentum / trend literature

- Jegadeesh and Titman, "Profitability of Momentum Strategies: An Evaluation of Alternative Explanations"
  - https://www.nber.org/papers/w7159
  - Use: establishes the classic medium-term momentum evidence and the behavioral underreaction framing.

- Chan, Jegadeesh, and Lakonishok, "Momentum Strategies"
  - https://www.nber.org/papers/w5375
  - Use: supports the view that price and earnings news can drift gradually into returns, which helps justify trend-following candidate logic.

- Hong, Lim, and Stein, "Bad News Travels Slowly: Size, Analyst Coverage and the Profitability of Momentum Strategies"
  - https://www.nber.org/papers/w6553
  - Use: supports gradual information diffusion rather than instant efficiency; relevant when reasoning about slower-moving cross-sectional trends.

- Chabot, Ghysels, and Jagannathan, "Momentum Trading, Return Chasing, and Predictable Crashes"
  - https://www.nber.org/papers/w20660
  - Use: momentum can crash after strong runs, so any momentum-style candidate must include explicit risk gates and exit rules.

### 2. China / A-share market evidence

- "Momentum effect and contrarian effect in China's A-share market, under registration-based system"
  - https://www.sciencedirect.com/science/article/pii/S0927538X2300197X
  - Use: suggests short-term momentum can exist in A-shares, but weakens over longer horizons.

- "Does short-term momentum exist in China?"
  - https://www.sciencedirect.com/science/article/pii/S0927538X22002153
  - Use: highlights that conventional momentum in China is controversial and links weak momentum to turnover and market structure.

- "Only strong short-term contrarian effect exists in Chinese stock market: The role of the T+1 trading mechanism"
  - https://www.sciencedirect.com/science/article/pii/S1059056024006452
  - Use: strong caution that China market microstructure may favor short-horizon contrarian behavior rather than naive momentum.

- "Price overreaction to up-limit events and revised momentum strategies in the Chinese stock market"
  - https://www.sciencedirect.com/science/article/abs/pii/S0264999322001560
  - Use: suggests Chinese momentum logic may need to be conditioned on market-specific events and filtered rather than copied from US evidence.

- "Institutional ownership and momentum in the Chinese A-share market"
  - https://www.sciencedirect.com/science/article/pii/S0927538X23000860
  - Use: indicates that China momentum evidence is structurally different and can depend on investor composition and liquidity.

### 3. Volume / turnover / liquidity context

- "The Asymmetric Momentum Effect in the Chinese Class A Share Market Amid Market Swings"
  - https://link.springer.com/article/10.1007/s10690-016-9211-0
  - Use: explicitly references volume and liquidity asymmetry in China; relevant for any volume-confirmed entry logic.

- "Horse race of weekly idiosyncratic momentum strategies with respect to various risk metrics: Evidence from the Chinese stock market"
  - https://arxiv.org/abs/1910.13115
  - Use: ties momentum profitability to market state, liquidity, investor sentiment, and risk metrics.

### 4. Quant community cross-check

- BigQuant 社区: ZUFE_2025
  - https://bigquant.com/square/104d9236-a2f2-44b2-aa96-01f4eca24150
  - Use: reflects an active community preference for combining momentum, volatility, and multi-factor filtering rather than using a single factor in isolation.

- BigQuant 社区: 基于动量因子的ETF轮动策略
  - https://bigquant.com/square/1d41d766-803c-45da-9cc9-81e1cf9e5a96
  - Use: confirms that momentum-style ranking logic remains common in current domestic quant practice, though often at the ETF level.

- BigQuant 社区: 动量投资与StockRanker模型
  - https://bigquant.com/square/f75f0427-69f-4694-a93f-aae90cb22f17
  - Use: useful for implementation ideas and ranking-style decomposition, but still requires local validation before adoption.

### 5. Current market and policy context

- 东方财富: 早新闻｜这些重要消息将影响股市
  - https://finance.eastmoney.com/a/202603023657843640.html
  - Use: recent policy and market context include 两会、证监会高质量发展表述、外汇风险准备金率调整、人形机器人与具身智能标准体系等，说明市场主线和政策驱动环境在变化，不能只看旧文献。

- 东方财富财富号: 2026年3月8日周末股市复盘
  - https://caifuhao.eastmoney.com/news/20260309034144650694010
  - Use: points to a recent environment of 科技热潮、地缘扰动、监管对短线和高频量化加强约束、高位题材退潮风险，这 directly affects whether breakout / momentum logic should be used aggressively or with tighter risk filters.

## Initial Working Interpretation

1. Pure imported US-style momentum is not enough for A-shares.
   - China-specific evidence is mixed.
   - Naive medium-term momentum may fail or weaken.

2. Medium-short horizon rule-based candidates are still viable.
   - The evidence is more supportive for short-horizon / conditioned momentum than for long unfiltered momentum.
   - This aligns with the user's requirement for explicit buy/sell points.

3. Market-structure filters matter.
   - T+1 trading, price limits, liquidity heterogeneity, and retail participation imply that regime filters and risk gates are mandatory.

4. Volume / turnover should be treated as confirmation, not standalone alpha.
   - The evidence does not justify simply chasing high-volume names.
   - Better use volume expansion to confirm a setup instead of defining the whole strategy.

## Candidate Research Directions To Test Next

- Trend continuation with pullback-and-reacceleration entry
- Breakout with volume confirmation and volatility guardrails
- Short-horizon contrarian rebound after controlled oversold conditions
- Regime-switched hybrid:
  - trend logic in strong market states
  - contrarian logic in weak / range-bound market states

## Open Questions For Local Validation

- In this project's own A-share dataset, does 5-20 day trend continuation outperform short-horizon contrarian rebound after costs?
- Does volume_ratio_20d improve signal quality, or only increase crowding / gap risk?
- Which side of the user's KPI is harder to satisfy:
  - sharpe > 2
  - win rate > 80%
- Can explicit buy/sell point logic be defined tightly enough to avoid discretionary interpretation?
- Does the current 2026 policy / theme environment favor continuation trades in AI-power-grid-like main lines, or does stricter short-term regulation make short-horizon contrarian/rebound setups more robust?
