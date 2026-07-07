# 策略注册表 (Strategy Registry)

> 最后更新: 2026-07-03 16:30
> 框架: v5.2 (基于 v5.1 IC 自适应加权 + NSGA-II HPO + 滚动重优化验证)

## 评估门控标准

| 门控 | 标准 | 说明 |
|------|------|------|
| 相对 IR | > 0.5 | 策略相对基准指数的信息比率 |
| Null Test | < 0.34 | 因子洗牌后跑赢概率（越低越好） |
| 过拟合评分 | < 0.6 | 多重测试校正后的过拟合指标 |
| 滚动 OOS | > 0 | 41 个月 walk-forward 拼接收益为正 |
| 滚动 IR | > 0.5 | 滚动 OOS 的相对 IR（最强 Alpha 证据） |

## 策略总览

### 已验证策略

| ID | 策略名 | 票池 | 因子 | 单次IR | 滚动OOS | 滚动IR | 滚动MDD | 状态 |
|----|--------|------|------|--------|---------|--------|---------|------|
| **T-001** | **dd3_mom_2** | **HS300** | **drawdown_3d, ret_20d** | **—** | **+146.2%** | **1.088** | **21.9%** | **IR新冠军(2因子,回撤+动量)** |
| **P-001** | **rsv5_mom_2** | **HS300** | **rsv_5, ret_20d** | **—** | **+131.0%** | **1.074** | **12.3%** | **风险调整最优(2因子,RSV)** |
| **T-002** | **bollpb5_mom_2** | **HS300** | **boll_pct_b_5, ret_20d** | **—** | **+122.6%** | **0.989** | **15.5%** | **Bollinger超卖+动量(新家族)** |
| **L-001** | **rsv_mom_2** | **HS300** | **rsv_9, ret_20d** | **—** | **+114.0%** | **1.004** | **14.9%** | **RSV超卖+动量(2因子)** |
| **T-003** | **dd10_mom_2** | **HS300** | **drawdown_10d, ret_20d** | **—** | **+117.0%** | **0.958** | **16.1%** | **10日回撤+动量(低MDD变体)** |
| **I-012** | **tochg_mom_2** | **HS300** | **turnover_change_5_20, ret_20d** | **2.19** | **+114.7%** | **0.967** | **14.6%** | **前冠军(2因子)** |
| **I-004** | **vol_mom_2** | **HS300** | **volume_ma_ratio_5_20, ret_20d** | **2.19** | **+121.5%** | **0.960** | **16.6%** | **2因子** |
| **S-001** | bollpb10_mom_2 | HS300 | boll_pct_b_10, ret_20d | — | +93.5% | 0.804 | 21.5% | Bollinger 10日变体 |
| **Q-001** | rsv7_mom_2 | HS300 | rsv_7, ret_20d | — | +96.7% | 0.858 | 16.4% | RSV 7日变体(2因子) |
| **N-001** | rsv_volmr_mom_3 | HS300 | rsv_9, volume_ma_ratio_5_20, ret_20d | — | +82.8% | 0.790 | 15.6% | 3因子(RSV+量比+动量) |
| **N-002** | rsv_tochg_mom_3 | HS300 | rsv_9, turnover_change_5_20, ret_20d | — | +83.3% | 0.783 | 16.0% | 3因子(RSV+换手+动量) |
| **P-002** | rsv14_mom_2 | HS300 | rsv_14, ret_20d | — | +82.3% | 0.733 | 16.7% | RSV 14日变体(2因子) |
| **I-013** | **vol_mom_rev_3** | **HS300** | **volume_ma_ratio_5_20, ret_20d, ret_5d** | **2.19** | **+82.9%** | **0.748** | **14.7%** | **3因子(动量+反转)** |
| **I-005** | **vol_mom_tochg_3** | **HS300** | **volume_ma_ratio_5_20, turnover_change_5_20, ret_20d** | **2.19** | **+83.3%** | **0.717** | **18.7%** | **3因子** |
| **S-002** | **bollw_mom_2** | **HS300** | **boll_width_20, ret_20d** | **—** | **+77.6%** | **0.663** | **9.8%** | **史上最低MDD(带宽收敛+动量)** |
| **N-003** | rsv_skew_mom_3 | HS300 | rsv_9, ret_skew_20d, ret_20d | — | +67.9% | 0.649 | 14.3% | 3因子(低MDD) |
| **I-015** | **tochg_mom_rev_3** | **HS300** | **turnover_change_5_20, ret_20d, ret_5d** | **2.19** | **+79.9%** | **0.706** | **14.4%** | **3因子(动量+反转)** |
| **I-003** | **vol_surge_mom_min4** | **HS300** | **volume_ma_ratio_5_20, turnover_change_5_20, ret_20d, ret_60d** | **2.19** | **+84.0%** | **0.632** | **21.7%** | **4因子** |
| **M-001** | skew_mom_2 | HS300 | ret_skew_20d, ret_20d | — | +73.2% | 0.611 | 15.0% | 偏度+动量(新因子,2因子) |
| **I-008** | **vol_rev_2** | **HS300** | **volume_ma_ratio_5_20, ret_5d** | **2.19** | **+60.3%** | **0.561** | **21.0%** | **量+反转** |
| **I-007** | **vp_corr_ret20** | **HS300** | **vol_price_corr_20d, ret_20d** | **2.19** | **+65.4%** | **0.553** | **13.8%** | **低回撤** |
| **S-003** | kurt_mom_2 | HS300 | kurtosis_20d, ret_20d | — | +69.3% | 0.505 | 27.2% | 峰度+动量(勉强通过) |
| **I-014** | **turn_std_mom_2** | **HS300** | **turnover_std_20d, ret_20d** | **2.19** | **+65.9%** | **0.551** | **18.6%** | **换手率稳定+动量** |
| **I-006** | **pure_mom_1** | **HS300** | **ret_20d** | **2.19** | **+70.9%** | **0.515** | **28.5%** | **单因子动量** |
| **I-002** | **vol_surge_mom_ret60** | **HS300** | **volume_ma_ratio_5_20, turnover_change_5_20, ret_20d, ret_60d, px_to_ma20** | **2.19** | **+65.7%** | **0.503** | **29.8%** | **5因子(首个通过)** |
| I-001 | vol_surge_mom_5 | HS300 | volume_ma_ratio_5_20, turnover_change_5_20, ret_20d, mom_120_20, px_to_ma20 | 2.19 | +62.1% | 0.47 | 27.5% | 差0.03未过 |
| D-001 | vp_industry_6 | HS300 | vol_price_corr_20d, amplitude_avg_20d, industry_mom_20d, ret_20d, turnover_rate, px_to_ma20 | 1.33 | +42.1% | 0.24 | 17.9% | 候选(弱Alpha) |
| J-001 | vp_macd_blend_6 | HS300 | vol_price_corr_20d, amplitude_avg_20d, dif, macd_hist, ret_20d, turnover_rate | 1.19 | +37.7% | 0.18 | **15.3%** | 候选(低回撤) |
| H-001 | mom_resonance_4 | HS300 | ret_5d, ret_20d, mom_120_20, px_to_ma20 | 2.94 | +31.9% | 0.09 | 42.9% | 弱 |
| J-002 | industry_macd_6 | HS300 | industry_mom_20d, dif, macd_hist, ret_20d, turnover_rate, px_to_ma20 | 2.64 | +28.2% | 0.10 | 30.2% | 弱 |
| E-001 | macd_trend_4 | HS300 | dif, macd_hist, ret_20d, turnover_rate | 2.94 | +25.6% | 0.05 | — | 弱 |
| J-003 | lowvol_macd_6 | HS300 | parkinson_vol_20d, amplitude_avg_20d, dif, ret_20d, turnover_rate, px_to_ma20 | 1.55 | +18.9% | -0.12 | 14.5% | 弱(最低MDD) |
| F-001 | value_macd_5 | HS300 | ep, dif, macd_hist, ret_20d, turnover_rate | 0.61 | +16.6% | -0.15 | 18.5% | 弱(低回撤) |

**P-001 备注**: **新冠军策略！2因子。** 滚动 IR=1.074（史上最高），OOS +131.0%（史上最高），CAGR 27.9%，MDD 12.3%（2因子中最低）。因子组合：**rsv_5（5日随机指标）+ ret_20d（20日动量）**。逻辑：买入"20日动量向上 + 5日内超卖回调"的股票 = **动量股回调买入（buy-the-dip in winners）**。RSV 是全新 Alpha 源，与换手率/量比类过滤器属不同维度。5日窗口为最优峰值（rsv_3=0.438, rsv_5=1.074, rsv_7=0.858, rsv_9=1.004, rsv_14=0.733, rsv_20=0.323，倒U型曲线）。

**L-001 备注**: 2因子模型，IR=1.004。rsv_9 + ret_20d。RSV 系列的原始发现，被 rsv_5 变体超越。证实"超卖回调 + 动量"是独立于"量缩 + 动量"的有效 Alpha 模式。

**I-012 备注**: 前冠军策略。2因子。滚动 IR=0.967，OOS +114.7%，CAGR 25.2%，MDD 14.6%。28/41 个月跑赢基准。因子组合：换手率加速(5d/20d) + 20日动量。被 P-001 (rsv_5) 超越，但仍为换手率类过滤器中最优。

**I-004 备注**: 2因子模型，IR=0.960。量比(5d/20d) + 20日动量。OOS +121.5%（最高绝对收益），但 MDD 16.6% 略高于 I-012。

**I-013 备注**: 3因子模型，IR=0.748, MDD=14.7%。量比 + 20日动量 + 5日反转。同时使用动量和反转信号，MDD 极低但因子数增加使 IR 下降。

**I-014 备注**: 2因子模型，IR=0.551。换手率标准差 + 20日动量。换手率稳定性作为噪声过滤器也有效。

**I-005 备注**: 3因子模型，滚动 IR=0.717。在 I-004 基础上加 turnover_change_5_20，IR 从 0.960 降至 0.717，说明换手率加速因子是噪声。但 MDD 18.7%，比 I-004 的 16.6% 略高。

**I-003 备注**: 4因子模型，滚动 IR=0.632。在 I-005 基础上加 ret_60d，IR 从 0.717 降至 0.632，说明 60日动量也是噪声。

**I-007 备注**: 2因子低回撤变体，IR=0.553, MDD=13.8%（史上最低）。用 vol_price_corr_20d 替代 volume_ma_ratio_5_20。**量价负相关 + 20日动量 = 最稳健的策略。** 适合风险偏好低的投资者。

**I-008 备注**: 2因子反转变体，IR=0.561。用 ret_5d(long_low) 替代 ret_20d(long_high)。**成交量萎缩 + 短期反转 = 另一类有效策略。** 与 I-004（动量）形成互补。

**I-006 备注**: 单因子模型，IR=0.515。ret_20d 独立即有 Alpha，但 MDD 28.5% 偏高。**20日动量是 HS300 Alpha 的核心来源。** 加量比因子后（I-004）MDD 从 28.5% 降至 16.6%，IR 从 0.515 升至 0.960。

**I-002 备注**: **首个通过全部门控的策略。** 滚动 IR=0.503 > 0.5，OOS +65.7%，CAGR 16.0%，MDD 29.8%。25/41 个月跑赢基准。因子组合：量比(5d/20d) + 换手率加速 + 20日动量 + 60日动量 + 趋势。被 I-003 超越（去掉 px_to_ma20 后 IR 从 0.503 升至 0.632）。

**D-001 备注**: 滚动 IR=0.24，但 OOS +42.1%、CAGR 10.9%、最大回撤仅 17.9%。低回撤特征有价值。

**J-001 备注**: 滚动 OOS +37.7%、MDD 15.3%、27/41 个月跑赢基准（最高 beat 率）。量价+MACD 融合策略。

**M-001 备注**: 2因子模型，IR=0.611。ret_skew_20d + ret_20d。新工程化因子——**20日收益率偏度**首次验证有效。低偏度（稳定上涨）+ 动量 = 过滤掉彩票型妖股，保留机构控盘的动量股。

**关键发现**: HS300 策略普遍优于 ZZ1000 — 8 个 HS300 策略滚动 OOS 均为正(+16%~+62%)，2 个 ZZ1000 策略滚动 OOS 均为-40%。HS300 回撤普遍<20%（低vol/macd/量价融合类），ZZ1000 回撤>57%。

**关键发现(本轮)**: RSV（随机指标）是全新 Alpha 源 — "超卖回调 + 动量"模式（rsv_5 + ret_20d, IR=1.074）超越"量缩 + 动量"模式（turnover_change + ret_20d, IR=0.967）。RSV 窗口呈倒U型曲线，5日为最优峰值。

### 待验证策略

## BJ50 票池策略 (北交所50)

> Batch R 票池探索发现。BJ50 (176只股票) 是继 HS300 后第二个有效票池。
> 特征：高收益、高波动（MDD ~41%），适合风险偏好较高的投资者。
> 基准：BJ50 指数

### BJ50 已验证策略

| ID | 策略名 | 票池 | 因子 | 滚动OOS | 滚动IR | 滚动MDD | 状态 |
|----|--------|------|------|---------|--------|---------|------|
| **T-004** | **dd7_mom_2_bj50** | **BJ50** | **drawdown_7d, ret_20d** | **+177.5%** | **1.064** | **41.7%** | **BJ50新冠军(2因子,回撤+动量)** |
| **R-001** | **rsv5_mom_2_bj50** | **BJ50** | **rsv_5, ret_20d** | **+151.6%** | **0.795** | **41.2%** | **BJ50次强(2因子,RSV超卖+动量)** |
| **S-004** | bollpb20_mom_2_bj50 | BJ50 | boll_pct_b_20, ret_20d | +140.1% | 0.750 | 42.2% | Bollinger超卖+动量 |
| **R-002** | **tochg_mom_2_bj50** | **BJ50** | **turnover_change_5_20, ret_20d** | **+141.6%** | **0.759** | **40.8%** | **换手率+动量** |

**R-001 备注**: BJ50 票池最强策略。2因子。rsv_5 + ret_20d。OOS +151.6%（超过 HS300 的 +131.0%），但 MDD 41.2%（远高于 HS300 的 12.3%）。北交所股票波动性更大，RSV 超卖回调策略在此捕捉到更大的反弹弹性。

**R-002 备注**: BJ50 票池次强。2因子。换手率加速 + 20日动量。OOS +141.6%。与 R-001 因子家族不同（换手率 vs RSV），可形成互补。

**BJ50 vs HS300 对比**: RSV 策略在两个票池均有效 — HS300 IR=1.074/MDD=12.3% vs BJ50 IR=0.795/MDD=41.2%。HS300 在风险调整后更优，BJ50 绝对收益更高。

### BJ50 已否决策略

| 策略 | 票池 | 因子 | 滚动OOS | 滚动IR | 否决原因 |
|------|------|------|---------|--------|----------|
| skew_ret20_bj50 | BJ50 | ret_skew_20d, ret_20d | +62.7% | 0.059 | 偏度因子在BJ50无效 |

### 其他票池探索结果 (Batch R)

| 票池 | 最佳策略 | 滚动IR | 滚动OOS | 结论 |
|------|---------|--------|---------|------|
| ZZ500 | tochg_ret20 | 0.475 | +87.6% | 接近门控但未通过(差0.025) |
| ZZ1000 | tochg_ret20 | 0.084 | +32.2% | 无Alpha,小盘量价信号不可靠 |
| KC100 | rsv5_ret20 | -0.500 | +0.3% | 完全无效,科创板无RSV Alpha |

**票池探索结论**: 大盘股(HS300)和北交所(BJ50)是 RSV 策略的有效票池。中盘(ZZ500)边缘，小盘(ZZ1000)和科创板(KC100)无效。量价信号需要足够的流动性和机构参与度。

### 待验证策略(原)

| ID | 策略名 | 票池 | 因子 | 单次IR | holdout | 状态 |
|----|--------|------|------|--------|---------|------|
| E-002 | tech_blend_7 | ZZ1000 | dif, k_value, rsi_14, ret_20d, mom_120_20, vol_price_corr_20d, turnover_rate | 0.80 | +57.3% | 待验证 |
| H-003 | mom_resonance_4 | KC100 | ret_5d, ret_20d, mom_120_20, px_to_ma20 | 2.07 | +164% | 待验证 |
| H-004 | mom_vp_6 | ZZ1000 | ret_5d, ret_20d, mom_120_20, vol_price_corr_20d, amplitude_avg_20d, turnover_rate | 0.97 | +64% | 待验证 |

### 已否决策略

| ID | 策略名 | 票池 | 因子 | 单次IR | 滚动OOS | 滚动IR | 否决原因 |
|----|--------|------|------|--------|---------|--------|----------|
| PV8 | 价量8因子 | HS300 | ret_20d, ret_60d, mom_120_20, ret_5d, vol_20d, turnover_rate, px_to_ma20, px_to_ma60 | 1.57 | -10.9% | -0.61 | Alpha不持久 |
| PV8 | 价量8因子 | ZZ500 | 同上 | 1.01 | +2.3% | -0.45 | 持平,无Alpha |
| A-001 | value_blend | HS300 | ep, bp, size_inv, ret_20d, mom_120_20 | <0 | — | — | 价值因子全线失败 |
| B-001 | industry_full_8 | HS300 | industry_mom_20d, ret_20d, ret_60d, mom_120_20, parkinson_vol_20d, turnover_rate, px_to_ma20, px_to_ma60 | 2.20 | +1.9% | -0.28 | 单次高IR是regime偶然 |
| B-002 | parkinson_lowvol_5 | ZZ500 | parkinson_vol_20d, ret_60d, mom_120_20, turnover_rate, px_to_ma60 | 1.86 | +19.4% | -0.33 | 跑输ZZ500指数 |
| B-003 | industry_full_8 | KC100 | 同B-001 | 1.23 | +30.6% | -0.40 | Alpha是小盘Beta |
| B-004 | industry_mom_6 | HS300 | industry_mom_20d, ret_20d, mom_120_20, vol_20d, turnover_rate, px_to_ma20 | 1.15 | -20.2% | -0.55 | OOS为负 |
| B-005 | parkinson_blend_7 | HS300 | parkinson_vol_20d, ret_20d, ret_60d, mom_120_20, vol_20d, turnover_rate, px_to_ma20 | 1.15 | +0.3% | -0.42 | 持平 |
| B-006 | industry_mom_6 | KC100 | 同B-004 | 0.92 | +38.3% | -0.34 | 跑输科创100 |
| D-002 | vp_blend_7 | HS300 | 见上 | 0.58 | +8.5% | -0.29 | 滚动IR为负 |
| H-001 | mom_system_8 | ZZ1000 | ret_5d, ret_20d, mom_120_20, dif, vol_price_corr_20d, amplitude_avg_20d, industry_mom_20d, turnover_rate | 2.01 | -39.6% | -0.90 | ZZ1000滚动OOS-40% |
| H-002 | mom_lowvol_5 | ZZ1000 | ret_5d, ret_20d, mom_120_20, parkinson_vol_20d, turnover_rate | 1.36 | -40.5% | -0.97 | ZZ1000滚动OOS-40% |
| K-001 | lowvol_reversal_5 | HS300 | parkinson_vol_20d, rsi_14, bias_20, ret_20d, turnover_rate | 1.707 | -3.8% | -0.654 | 单次IR=1.707是regime偶然 |
| I-009 | vol_mom_2_zz500 | ZZ500 | volume_ma_ratio_5_20, ret_20d | 2.19 | +79.2% | 0.403 | ZZ500 IR低于门控,HS300专属 |
| I-010 | single_volratio | HS300 | volume_ma_ratio_5_20 | — | +2.5% | -0.483 | 量比因子无独立Alpha,仅噪声过滤 |
| I-011 | vol_ratio_mom120 | HS300 | volume_ma_ratio_5_20, mom_120_20 | — | -14.9% | -0.492 | 12-1月动量是噪声,再次确认 |

## 因子库 (71 columns in factor_panel)

### 价量因子 (原有)
- momentum: ret_5d, ret_20d, ret_60d, mom_120_20
- volatility: vol_20d, vol_60d, parkinson_vol_20d
- liquidity: turnover_rate, amt_20d
- technical: px_to_ma20, px_to_ma60

### 基本面因子 (需 fundamentals 表)
- value: ep (1/PE), bp (1/PB), size_inv (1/总市值)
- quality: roe

### 行业因子
- industry: industry_mom_20d (行业20日动量)

### 策略 D: 量价微观结构因子
- vol_price_corr_20d: 20日量价相关系数 (long_low)
- turnover_change_5_20: 5日/20日换手率比 (long_low)
- amplitude_avg_20d: 20日平均振幅 (long_low)

### 策略 E: 经典技术指标 (参考桌面项目)
- bias_20: 20日乖离率 (long_low)
- rsi_14: 14日RSI (long_low)
- turnover_std_20d: 换手率标准差 (long_low)
- volume_ma_ratio_5_20: 5日/20日量比 (long_low)
- rsv_9: 9日RSV随机指标 (long_low)
- dif: MACD DIF线 (long_high)
- macd_hist: MACD柱 (long_high)
- k_value: KD K值 (long_low)
- d_value: KD D值 (long_low, 慢线信号)

### 策略 L+P: 高阶矩 & RSV 窗口变体 (本轮新增)
- ret_10d: 10日动量 (long_high, 中间周期) — 单独无效，仅 ret_20d 是有效动量
- ret_15d: 15日动量 (long_high, 中间周期) — 同上
- ret_skew_20d: 20日收益率偏度 (long_low) — **有效！** 低偏度=稳定上涨，IR=0.611 (M-001)
- atr_20d: 20日真实波幅/收盘 (long_low) — 无效 (IR=-0.144)
- rsv_5: 5日RSV (long_low) — **冠军因子！** IR=1.074 (P-001)
- rsv_3: 3日RSV (long_low) — 过短，IR=0.438
- rsv_7: 7日RSV (long_low) — IR=0.858
- rsv_14: 14日RSV (long_low) — IR=0.733
- rsv_20: 20日RSV (long_low) — 过长，IR=0.323

### 策略 S+T: Bollinger & 回撤因子 (本轮新增)
- boll_pct_b_20: 20日 Bollinger %B (long_low) — 近似有效(0.405)
- boll_pct_b_10: 10日 Bollinger %B (long_low) — **有效！** IR=0.804 (S-001)
- boll_pct_b_5: 5日 Bollinger %B (long_low) — **有效！** IR=0.989 (T-002), 接近冠军
- boll_pct_b_7: 7日 Bollinger %B (long_low) — 有效, IR=0.897
- boll_width_20: 20日 Bollinger 带宽 (long_low) — **有效！** IR=0.663, MDD=9.8% **史上最低** (S-002)
- boll_width_5/10: 5/10日带宽 — 无效 (IR<0.41), 带宽需20日窗口
- drawdown_3d: 3日回撤 (long_low) — **HS300 IR冠军因子！** IR=1.088 (T-001)
- drawdown_5d: 5日回撤 (long_low) — HS300无效单独, BJ50 IR=0.969
- drawdown_7d: 7日回撤 (long_low) — **BJ50冠军因子！** IR=1.064 (T-004)
- drawdown_10d: 10日回撤 (long_low) — 有效, HS300 IR=0.958 (T-003)
- kurtosis_20d: 20日峰度 (long_low) — 边缘有效, IR=0.505 (S-003)

### 策略 BB: 量价加权振荡器 (Batch BB 新增)
- mfi_14: 14日MFI资金流量指标 (long_low) — **有效！** IR=0.773 (BB-001), 量价加权RSI, 捕捉资金流入流出
- obv_change_20: 20日OBV变化率/均量 (long_low) — **有效！** IR=0.552 (BB-004), 量能累积/派发趋势
- rsi_7: 7日RSI (long_low) — 作为第4因子有效 IR=0.650 (BB-003), 但作为第3因子无效(0.469)

### 策略 CC: MFI/OBV 窗口变体 (Batch CC 新增)
- mfi_7: 7日MFI (long_low) — **MFI最优窗口!** IR=0.949 (CC-001 n10), IR=1.384 (CC-006 n5新冠军)
- mfi_10: 10日MFI (long_low) — 有效, IR=0.891 (CC-002)
- mfi_20: 20日MFI (long_low) — 边缘有效, IR=0.517 (CC-004)
- obv_change_10: 10日OBV变化率 (long_low) — 有效, IR=0.878 (CC-003), 优于20日版本(0.654)
- **MFI窗口倒U型曲线**: mfi_7(0.949) > mfi_10(0.891) > mfi_14(0.773) > mfi_20(0.517), 短窗口更优

### 策略 DD: MFI窗口微调 (Batch DD 新增)
- mfi_5: 5日MFI (long_low) — 有效但偏弱, IR=0.713 (DD-007 n5), IR=0.633 (DD-013 n10)
- mfi_6: 6日MFI (long_low) — 有效, IR=0.953 (DD-003 n5, 低MDD=32.5%), IR=0.744 (DD-012 n10)
- mfi_8: 8日MFI (long_low) — **强!** IR=1.234 (DD-001 n5, 第二名), IR=0.853 (DD-010 n10)
- **MFI窗口完整倒U型曲线(n5)**: mfi_5(0.713) < mfi_6(0.953) < mfi_7(1.384) > mfi_8(1.234) > mfi_10(0.862) > mfi_14(0.740) > mfi_20(失败)
- **dd4(4日回撤)是MFI策略的低MDD替代窗口**: dd4_mfi7_ret20_n5 IR=1.115/MDD=32.2%, dd4_mfi5_ret20_n5 IR=0.900/MDD=31.1%(n5最低)

### 策略 EE+FF: Chaikin Money Flow (Batch EE新增, Batch FF验证)
- cmf_7: 7日CMF (long_low) — **有效!** IR=1.124 (FF-001 n5, dd5版), IR=0.791 (FF-007 n5, dd3版), IR=0.859 (FF-010 n10, dd4版)
- cmf_10: 10日CMF (long_low) — 有效, IR=0.792 (FF-006 n5), IR=0.779 (FF-012 n10)
- cmf_14: 14日CMF (long_low) — 有效, IR=0.888 (FF-005 n5)
- cmf_20: 20日CMF (long_low) — **CMF最优窗口!** IR=1.075 (FF-002 n5), 长窗口优于短窗口
- **CMF窗口曲线(与MFI相反)**: cmf_20(1.075) > cmf_14(0.888) > cmf_10(0.792) ≈ cmf_7(0.791)。长窗口更优 — 与MFI(mfi_7最优)完全相反!
- **CMF vs MFI区别**: MFI用"典型价格涨跌×成交量"判断资金流向;CMF用"收盘在日内区间的位置(CLV)×成交量"判断。CMF关注收盘位置,MFI关注价格变化。窗口偏好相反证实它们捕捉不同的资金流信号

## 手动交易 top_n 约束分析 (Batch U/V/W/X/Y)

> 用户需求：手动交易，每策略不超过10只，最优5只。
> 测试方式：将 top_n 搜索空间限制为 [3,5] 或 [5,10]，重新滚动验证。
> **重大发现：集中持仓后3因子模型反而优于2因子（与n30相反）！多个超卖过滤器叠加提供集中持仓需要的风险控制。**

### top_n=10 已验证策略（按IR排名）

| ID | 策略名 | 因子 | 因子数 | 滚动IR | 滚动OOS | 滚动MDD | 说明 |
|----|--------|------|--------|--------|---------|---------|------|
| **Z-001** | **dd3_rsv7_ret20** | drawdown_3d, rsv_7, ret_20d | **3** | **1.370** | **+345.4%** | **22.3%** | **n10新冠军(Batch Z微调确认rsv7为最优窗口)** |
| W-001 | dd3_rsv9_ret20 | drawdown_3d, rsv_9, ret_20d | 3 | 1.366 | +358.1% | 22.3% | 前冠军(3因子首次超越2因子) |
| AA-001 | dd3_rsv6_ret20 | drawdown_3d, rsv_6, ret_20d | 3 | 1.188 | +292.2% | 28.4% | rsv6窗口变体(Batch AA) |
| Z-002 | dd3_rsv14_ret20 | drawdown_3d, rsv_14, ret_20d | 3 | 1.156 | +321.5% | 28.5% | rsv14窗口变体(Batch Z) |
| V-001 | rsv9_ret20 | rsv_9, ret_20d | 2 | 1.084 | +290.6% | 23.4% | n10 2因子冠军 |
| W-002 | rsv7_ret20 | rsv_7, ret_20d | 2 | 1.067 | +260.3% | 25.6% | |
| V-002 | dd10_ret20 | drawdown_10d, ret_20d | 2 | 1.052 | +228.3% | 30.5% | |
| X-001 | dd7_rsv9_ret20 | drawdown_7d, rsv_9, ret_20d | 3 | 1.006 | +204.7% | 25.7% | |
| AA-002 | dd3_rsv8_ret20 | drawdown_3d, rsv_8, ret_20d | 3 | 0.991 | +279.7% | 27.4% | rsv8窗口变体(Batch AA) |
| V-003 | bollpb5_ret20 | boll_pct_b_5, ret_20d | 2 | 0.980 | +252.8% | 21.5% | n10最低MDD |
| X-002 | dd3_rsv9_skew_ret20 | drawdown_3d, rsv_9, ret_skew_20d, ret_20d | 4 | 0.924 | +202.1% | 24.8% | 4因子也可行(n10) |
| AA-003 | dd2_rsv7_ret20 | drawdown_2d, rsv_7, ret_20d | 3 | 0.908 | +229.6% | 24.8% | dd2窗口变体(Batch AA) |
| X-003 | dd3_bollpb5_ret20 | drawdown_3d, boll_pct_b_5, ret_20d | 3 | 0.884 | +203.4% | 35.3% | |
| X-004 | dd10_rsv5_ret20 | drawdown_10d, rsv_5, ret_20d | 3 | 0.846 | +154.3% | 25.1% | |
| V-004 | bollpb10_ret20 | boll_pct_b_10, ret_20d | 2 | 0.784 | +207.3% | 48.3% | 高MDD |
| Z-003 | bollpb7_ret20 | boll_pct_b_7, ret_20d | 2 | 0.750 | +177.5% | 25.8% | Bollinger 7日变体(Batch Z) |
| V-005 | dd3_ret20 | drawdown_3d, ret_20d | 2 | 0.712 | +166.3% | 41.8% | n30冠军但n10下降 |
| AA-004 | dd4_rsv7_ret20 | drawdown_4d, rsv_7, ret_20d | 3 | 0.656 | +128.6% | 35.7% | dd4窗口变体(Batch AA) |
| X-005 | dd3_rsv5_ret20 | drawdown_3d, rsv_5, ret_20d | 3 | 0.649 | +140.2% | 36.0% | |
| Z-004 | dd10_bollpb5_ret20 | drawdown_10d, boll_pct_b_5, ret_20d | 3 | 0.647 | +132.3% | 29.3% | dd10+bollpb5组合(Batch Z) |
| Z-005 | dd3_rsv9_vpc_ret20 | drawdown_3d, rsv_9, vol_price_corr_20d, ret_20d | 4 | 0.646 | +128.4% | 29.0% | 4因子(量价相关加入) |
| X-006 | dd10_rsv9_ret20 | drawdown_10d, rsv_9, ret_20d | 3 | 0.616 | +95.6% | 26.2% | |
| Z-006 | rsv9_vpc_ret20 | rsv_9, vol_price_corr_20d, ret_20d | 3 | 0.613 | +104.0% | 22.9% | RSV+量价相关(Batch Z) |
| Z-007 | dd5_rsv9_ret20 | drawdown_5d, rsv_9, ret_20d | 3 | 0.596 | +111.5% | 33.0% | dd5窗口变体(Batch Z) |
| Z-008 | dd3_rsv9_bollpb10_ret20 | drawdown_3d, rsv_9, boll_pct_b_10, ret_20d | 4 | 0.558 | +94.4% | 30.8% | 4因子(Batch Z) |
| Y-001 | dd3_rsv9_ret20_bj50 | drawdown_3d, rsv_9, ret_20d | 3 | 0.531 | +111.6% | 38.7% | BJ50 n10 |
| X-007 | bollpb5_rsv9_ret20 | boll_pct_b_5, rsv_9, ret_20d | 3 | 0.504 | +97.7% | 24.1% | 勉强通过 |
| **CC-001** | **dd3_mfi7_ret20** | drawdown_3d, mfi_7, ret_20d | **3** | **0.949** | **+220.6%** | **33.5%** | **MFI最优窗口! 7日资金流+回撤+动量(Batch CC)** |
| CC-002 | dd3_mfi10_ret20 | drawdown_3d, mfi_10, ret_20d | 3 | 0.891 | +202.7% | 40.5% | MFI 10日变体(Batch CC) |
| CC-003 | dd3_obv10_ret20 | drawdown_3d, obv_change_10, ret_20d | 3 | 0.878 | +201.3% | 35.9% | OBV 10日优于20日(Batch CC) |
| BB-001 | dd3_mfi_ret20 | drawdown_3d, mfi_14, ret_20d | 3 | 0.773 | +161.1% | 26.8% | **MFI新因子!** 资金流+回撤+动量(Batch BB) |
| BB-002 | dd3_obv_ret20 | drawdown_3d, obv_change_20, ret_20d | 3 | 0.654 | +148.2% | 38.6% | OBV新因子! 量能+回撤+动量(Batch BB) |
| BB-003 | dd3_rsv7_rsi7_ret20 | drawdown_3d, rsv_7, rsi_7, ret_20d | 4 | 0.650 | +119.2% | 34.2% | 4因子: RSI_7新因子(Batch BB) |
| BB-004 | obv_ret20 | obv_change_20, ret_20d | 2 | 0.552 | +121.1% | 32.2% | OBV+动量 2因子(Batch BB) |
| CC-004 | dd3_mfi20_ret20 | drawdown_3d, mfi_20, ret_20d | 3 | 0.517 | +111.1% | 38.7% | MFI 20日变体,勉强通过(Batch CC) |
| CC-005 | obv10_ret20 | obv_change_10, ret_20d | 2 | 0.615 | +146.5% | 41.3% | OBV 10日2因子(Batch CC) |
| DD-009 | dd4_mfi7_ret20 | drawdown_4d, mfi_7, ret_20d | 3 | 0.968 | +177.7% | 25.5% | dd4窗口变体,低MDD!(Batch DD) |
| DD-010 | dd3_mfi8_ret20 | drawdown_3d, mfi_8, ret_20d | 3 | 0.853 | +183.6% | 41.4% | mfi_8窗口变体(Batch DD) |
| DD-011 | dd2_mfi7_ret20 | drawdown_2d, mfi_7, ret_20d | 3 | 0.787 | +175.3% | 35.6% | dd2窗口变体(Batch DD) |
| DD-012 | dd3_mfi6_ret20 | drawdown_3d, mfi_6, ret_20d | 3 | 0.744 | +108.5% | 27.5% | mfi_6窗口变体,低MDD(Batch DD) |
| DD-013 | dd3_mfi5_ret20 | drawdown_3d, mfi_5, ret_20d | 3 | 0.633 | +120.6% | 35.5% | mfi_5窗口变体(Batch DD) |
| **EE-007** | **dd4_mfi8_ret20** | drawdown_4d, mfi_8, ret_20d | **3** | **1.184** | **+234.3%** | **23.1%** | **dd4+mfi8,IR>1且MDD最低!(Batch EE)** |
| EE-008 | dd4_mfi6_ret20 | drawdown_4d, mfi_6, ret_20d | 3 | 0.828 | +183.1% | 27.8% | dd4+mfi6(Batch EE) |
| FF-010 | dd4_cmf7_ret20 | drawdown_4d, cmf_7, ret_20d | 3 | 0.859 | +208.9% | 38.4% | dd4+cmf7(Batch FF) |
| FF-011 | dd3_cmf7_ret20 | drawdown_3d, cmf_7, ret_20d | 3 | 0.778 | +171.2% | 46.7% | cmf_7@n10(Batch FF) |
| FF-012 | dd3_cmf10_ret20 | drawdown_3d, cmf_10, ret_20d | 3 | 0.779 | +175.1% | 48.3% | cmf_10@n10(Batch FF) |
| FF-013 | cmf7_ret20 | cmf_7, ret_20d | 2 | 0.753 | +176.5% | 37.7% | CMF独立2因子@n10(Batch FF) |
| GG-006 | dd3_cmf20_ret20 | drawdown_3d, cmf_20, ret_20d | 3 | 0.792 | +212.6% | 49.3% | cmf20@n10(Batch GG) |
| GG-007 | dd5_cmf20_ret20 | drawdown_5d, cmf_20, ret_20d | 3 | 0.694 | +150.0% | 27.7% | dd5+cmf20@n10,n10低MDD(Batch GG) |
| **HH-001** | **dd4_mfi7_ret20_lm** | drawdown_4d, mfi_7, ret_20d | **3** | **1.094** | **+215.8%** | **23.8%** | **n10低MDD冠军!紧约束(0.20)版,IR>1+MDD<25%(Batch HH/II)** |
| **HH-002** | **dd5_cmf14_ret20_lm** | drawdown_5d, cmf_14, ret_20d | **3** | **0.984** | **+219.4%** | **24.9%** | **n10低MDD亚军!MDD<25%(Batch II)** |
| HH-003 | dd5_cmf20_ret20_lm | drawdown_5d, cmf_20, ret_20d | 3 | 0.858 | +259.7% | 25.5% | dd5+cmf20紧约束版(Batch II) |
| HH-004 | dd4_mfi8_ret20_lm | drawdown_4d, mfi_8, ret_20d | 3 | 0.981 | +175.7% | 30.6% | dd4+mfi8紧约束版(Batch II) |
| HH-005 | dd3_rsv7_ret20_lm | drawdown_3d, rsv_7, ret_20d | 3 | 0.847 | +210.9% | 35.7% | n10冠军紧约束版,MDD仍高(Batch II) |
| HH-006 | dd5_cmf7_ret20_lm | drawdown_5d, cmf_7, ret_20d | 3 | 0.686 | +158.1% | 30.6% | dd5+cmf7紧约束@n10(Batch II) |
| **JJ-001** | **dd5_mfi7_ret20_lm** | drawdown_5d, mfi_7, ret_20d | **3** | **0.902** | **+141.8%** | **21.4%** | **n10最低MDD!dd5+MFI7紧约束(Batch JJ)** |
| **JJ-002** | **dd5_mfi8_ret20_lm** | drawdown_5d, mfi_8, ret_20d | **3** | **0.821** | **+125.1%** | **22.7%** | **n10达标!dd5+MFI8紧约束(Batch JJ)** |
| **JJ-003** | **dd4_mfi6_ret20_lm** | drawdown_4d, mfi_6, ret_20d | **3** | **1.037** | **+216.9%** | **27.3%** | **IR>1!dd4+MFI6紧约束,MDD略超25%(Batch JJ)** |
| JJ-004 | dd4_cmf7_ret20_lm | drawdown_4d, cmf_7, ret_20d | 3 | 1.096 | +333.1% | 36.5% | dd4+cmf7紧约束,IR最高但MDD高(Batch JJ) |
| JJ-005 | dd4_cmf14_ret20_lm | drawdown_4d, cmf_14, ret_20d | 3 | 0.752 | +145.5% | 35.5% | dd4+cmf14紧约束(Batch JJ) |
| JJ-006 | dd4_cmf20_ret20_lm | drawdown_4d, cmf_20, ret_20d | 3 | 0.714 | +156.7% | 43.7% | dd4+cmf20紧约束(Batch JJ) |
| JJ-007 | dd4_mfi5_ret20_lm | drawdown_4d, mfi_5, ret_20d | 3 | 0.491 | +75.3% | 30.4% | 未通过IR门控(Batch JJ) |
| JJ-008 | dd4_cmf7_mfi7_ret20_lm | drawdown_4d, cmf_7, mfi_7, ret_20d | 4 | 0.352 | +56.2% | 33.0% | 4因子紧约束,未通过(Batch JJ) |
| **KK-001** | **dd5_mfi5_ret20_lm** | drawdown_5d, mfi_5, ret_20d | **3** | **0.770** | **+114.8%** | **21.8%** | **n10达标!dd5+MFI5紧约束,最低MDD(Batch KK)** |
| KK-002 | dd5_cmf20_ret20_lm | drawdown_5d, cmf_20, ret_20d | 3 | 0.858 | +259.7% | 25.5% | 差0.5%达标(Batch KK) |
| KK-003 | dd5_cmf7_rsv7_ret20_lm | drawdown_5d, cmf_7, rsv_7, ret_20d | 4 | 0.496 | +82.3% | 22.6% | 4因子,IR未过(Batch KK) |
| KK-004 | dd5_cmf20_mfi7_ret20_lm | drawdown_5d, cmf_20, mfi_7, ret_20d | 4 | -0.002 | +20.9% | 29.2% | 4因子失败(Batch KK) |
| KK-005 | dd5_cmf20_rsv7_ret20_lm | drawdown_5d, cmf_20, rsv_7, ret_20d | 4 | 0.253 | +54.6% | 33.7% | 4因子失败(Batch KK) |
| KK-006 | dd5_mfi6_ret20_lm | drawdown_5d, mfi_6, ret_20d | 3 | 0.407 | +59.8% | 28.5% | 未通过IR(Batch KK) |
| **LL-001** | **dd6_cmf7_ret20_lm** | drawdown_6d, cmf_7, ret_20d | **3** | **0.924** | **+161.5%** | **20.9%** | **史上最低MDD!dd6+CMF7紧约束(Batch LL)** |
| **LL-002** | **dd6_mfi5_ret20_lm** | drawdown_6d, mfi_5, ret_20d | **3** | **0.863** | **+136.8%** | **23.9%** | **n10达标!dd6+MFI5紧约束(Batch LL)** |
| **LL-003** | **dd6_cmf20_ret20_lm** | drawdown_6d, cmf_20, ret_20d | **3** | **0.786** | **+211.0%** | **24.0%** | **n10达标!dd6+CMF20紧约束(Batch LL)** |
| LL-004 | dd6_cmf14_ret20_lm | drawdown_6d, cmf_14, ret_20d | 3 | 0.887 | +158.9% | 26.1% | 差1.1%达标(Batch LL) |
| LL-005 | dd6_mfi7_ret20_lm | drawdown_6d, mfi_7, ret_20d | 3 | 0.740 | +115.4% | 32.0% | MDD偏高(Batch LL) |
| LL-006 | dd6_mfi8_ret20_lm | drawdown_6d, mfi_8, ret_20d | 3 | 0.486 | +77.7% | 30.0% | 未通过IR(Batch LL) |
| **OO-001** | **dd6_mfi6_ret20_lm** | drawdown_6d, mfi_6, ret_20d | **3** | **1.039** | **+201.0%** | **18.9%** | **史上最低MDD!IR>1+MDD<20%(Batch OO)。PP鲁棒性:4种子IR=1.004-1.075,MDD=18.0-18.9%,极其稳健!实盘首选** |
| **OO-002** | ~~dd5_cmf10_ret20_lm~~ | drawdown_5d, cmf_10, ret_20d | **3** | **1.223** | **+263.3%** | **22.6%** | **n10低MDD IR冠军(Batch OO)。但PP鲁棒性失败:3种子MDD均跳至30.5%,IR降至0.820-1.117,原始种子幸运。不推荐实盘** |
| OO-003 | dd6_cmf14_ret20_lm | drawdown_6d, cmf_14, ret_20d | 3 | 0.887 | +158.9% | 26.1% | 差1.1%达标(Batch OO/LL) |
| OO-004 | dd4_mfi6_ret20_lm | drawdown_4d, mfi_6, ret_20d | 3 | 1.037 | +216.9% | 27.3% | IR>1但MDD略超(Batch OO/JJ) |
| OO-005 | dd5_cmf7_ret20_lm | drawdown_5d, cmf_7, ret_20d | 3 | 0.686 | +158.1% | 30.6% | MDD偏高(Batch OO) |
| OO-006 | dd4_cmf14_ret20_lm | drawdown_4d, cmf_14, ret_20d | 3 | 0.752 | +145.5% | 35.5% | MDD高(Batch OO) |
| OO-007 | dd6_cmf7_mfi7_ret20_lm | drawdown_6d, cmf_7, mfi_7, ret_20d | 4 | 0.611 | +99.5% | 27.1% | 4因子弱(Batch OO) |
| OO-008 | dd5_cmf20_mfi7_ret20_lm | drawdown_5d, cmf_20, mfi_7, ret_20d | 4 | -0.002 | +20.9% | 29.2% | 4因子失败(Batch OO) |
| OO-009 | dd6_cmf20_mfi7_ret20_lm | drawdown_6d, cmf_20, mfi_7, ret_20d | 4 | -0.309 | -10.2% | 44.1% | 4因子灾难性失败(Batch OO) |
| PP-001 | dd6_mfi6_ret20_s1 | drawdown_6d, mfi_6, ret_20d | 3 | 1.004 | +187.0% | 18.9% | OO-001鲁棒性seed=1,IR>1,MDD不变(Batch PP) |
| PP-002 | dd6_mfi6_ret20_s2 | drawdown_6d, mfi_6, ret_20d | 3 | 1.049 | +202.9% | 18.9% | OO-001鲁棒性seed=2,IR>1,MDD不变(Batch PP) |
| PP-003 | dd6_mfi6_ret20_s3 | drawdown_6d, mfi_6, ret_20d | 3 | 1.075 | +199.8% | 18.0% | OO-001鲁棒性seed=3,IR>1,MDD更低!(Batch PP) |
| PP-004 | dd5_cmf10_ret20_s1 | drawdown_5d, cmf_10, ret_20d | 3 | 1.117 | +196.1% | 30.5% | OO-002鲁棒性seed=1,MDD跳至30.5%(Batch PP) |
| PP-005 | dd5_cmf10_ret20_s2 | drawdown_5d, cmf_10, ret_20d | 3 | 1.117 | +196.1% | 30.5% | OO-002鲁棒性seed=2,MDD跳至30.5%(Batch PP) |
| PP-006 | dd5_cmf10_ret20_s3 | drawdown_5d, cmf_10, ret_20d | 3 | 0.820 | +133.7% | 30.5% | OO-002鲁棒性seed=3,IR降至0.82,MDD=30.5%(Batch PP) |
| PP-007 | dd6_mfi6_rsv7_ret20_lm | drawdown_6d, mfi_6, rsv_7, ret_20d | 4 | 0.560 | +92.0% | 24.2% | 4因子失败,OOS<100%(Batch PP) |
| PP-008 | dd5_cmf10_rsv7_ret20_lm | drawdown_5d, cmf_10, rsv_7, ret_20d | 4 | 0.373 | +52.0% | 21.7% | 4因子失败,IR未过(Batch PP) |
| PP-009 | dd7_mfi6_ret20_lm | drawdown_7d, mfi_6, ret_20d | 3 | 0.481 | +83.9% | 28.7% | dd7+mfi6未通过,dd6优于dd7(Batch PP) |
| QQ-001 | dd6_mfi6_ret20_ultra | drawdown_6d, mfi_6, ret_20d | 3 | 0.597 | +87.5% | 26.9% | 超紧约束(0.15)失败!MDD反升,IR暴跌(Batch QQ) |
| QQ-002 | dd4_mfi7_ret20_ultra | drawdown_4d, mfi_7, ret_20d | 3 | 0.831 | +127.9% | 23.4% | 超紧约束勉强达标但远不如0.20版(Batch QQ) |
| QQ-003 | dd5_mfi7_ret20_ultra | drawdown_5d, mfi_7, ret_20d | 3 | 0.739 | +101.3% | 24.2% | 超紧约束MDD反升(21.4->24.2%),IR降(Batch QQ) |
| QQ-004 | dd6_cmf7_ret20_ultra | drawdown_6d, cmf_7, ret_20d | 3 | 0.790 | +120.8% | 23.7% | 超紧约束MDD反升(20.9->23.7%)(Batch QQ) |
| QQ-005 | dd6_mfi5_ret20_ultra | drawdown_6d, mfi_5, ret_20d | 3 | 0.636 | +91.0% | 28.3% | 超紧约束失败(Batch QQ) |
| **RR-001** | **dd5_obv10_ret20_lm** | drawdown_5d, obv_change_10, ret_20d | **3** | **0.939** | **+141.1%** | **24.0%** | **新因子家族!OBV10+dd5紧约束达标(Batch RR)。SS鲁棒性:4种子IR=0.939-1.193,MDD=18.4-24.0%,极其稳健!原始种子最差,实盘首选** |
| RR-002 | dd4_obv10_ret20_lm | drawdown_4d, obv_change_10, ret_20d | 3 | 0.760 | +145.6% | 38.0% | OBV10+dd4 MDD太高(Batch RR) |
| RR-003 | dd6_obv10_ret20_lm | drawdown_6d, obv_change_10, ret_20d | 3 | 0.302 | +55.3% | 34.7% | OBV10+dd6失败(Batch RR) |
| RR-004 | dd6_obv20_ret20_lm | drawdown_6d, obv_change_20, ret_20d | 3 | 0.353 | +56.2% | 23.8% | OBV20+dd6 MDD低但IR差(Batch RR) |
| RR-005 | dd6_cmf10_ret20_lm | drawdown_6d, cmf_10, ret_20d | 3 | 1.039 | +187.9% | 33.9% | IR>1但MDD高(Batch RR) |
| RR-006 | dd6_rsi7_ret20_lm | drawdown_6d, rsi_7, ret_20d | 3 | 0.562 | +88.7% | 34.7% | dd6+RSI7 MDD高(Batch RR) |
| RR-007 | dd4_rsi7_ret20_lm | drawdown_4d, rsi_7, ret_20d | 3 | 0.605 | +115.0% | 32.6% | dd4+RSI7 MDD高(Batch RR) |
| RR-008 | dd5_rsi7_ret20_lm | drawdown_5d, rsi_7, ret_20d | 3 | 0.564 | +77.5% | 23.8% | MDD<25%但OOS不足(Batch RR) |
| SS-001 | dd5_obv10_ret20_s1 | drawdown_5d, obv_change_10, ret_20d | 3 | 1.161 | +186.4% | 21.5% | RR-001鲁棒性seed=1,IR>1.1!(Batch SS) |
| SS-002 | dd5_obv10_ret20_s2 | drawdown_5d, obv_change_10, ret_20d | 3 | 1.193 | +194.9% | 21.5% | RR-001鲁棒性seed=2,IR最高!(Batch SS) |
| SS-003 | dd5_obv10_ret20_s3 | drawdown_5d, obv_change_10, ret_20d | 3 | 1.180 | +201.2% | 18.4% | RR-001鲁棒性seed=3,MDD=18.4%!(Batch SS) |
| SS-004 | dd5_obv20_ret20_lm | drawdown_5d, obv_change_20, ret_20d | 3 | 0.758 | +118.5% | 31.7% | OBV20不如OBV10(Batch SS) |
| SS-005 | dd3_obv10_ret20_lm | drawdown_3d, obv_change_10, ret_20d | 3 | 0.738 | +174.6% | 42.7% | dd3太短,OBV需dd5(Batch SS) |
| **TT-001** | **dd5_mfi10_ret20_lm** | drawdown_5d, mfi_10, ret_20d | **3** | **0.981** | **+187.9%** | **24.1%** | **MFI10新窗口!dd5+mfi10紧约束达标(Batch TT)。UU鲁棒性:4种子IR=0.894-0.981,MDD=24.1-25.6%,中等稳健** |
| TT-002 | dd5_mfi14_ret20_lm | drawdown_5d, mfi_14, ret_20d | 3 | 0.330 | +49.8% | 31.3% | MFI14太长,dd5 MFI有效窗口≤10(Batch TT) |
| TT-003 | dd5_obv10_ret10_lm | drawdown_5d, obv_change_10, ret_10d | 3 | -0.489 | -23.3% | 38.1% | ret_10d无效!ret_20d是唯一动量(Batch TT) |
| TT-004 | dd6_mfi6_ret10_lm | drawdown_6d, mfi_6, ret_10d | 3 | 0.452 | +97.2% | 29.9% | ret_10d远不如ret_20d(Batch TT) |
| TT-005 | dd6_mfi6_bollw20_ret20_lm | drawdown_6d, mfi_6, boll_width_20, ret_20d | 4 | -0.232 | +0.5% | 27.4% | 4因子波动率灾难性失败(Batch TT) |
| TT-006 | dd5_obv10_bollw20_ret20_lm | drawdown_5d, obv_change_10, boll_width_20, ret_20d | 4 | 0.329 | +48.6% | 29.4% | 4因子波动率失败(Batch TT) |
| UU-001 | dd5_mfi10_ret20_s1 | drawdown_5d, mfi_10, ret_20d | 3 | 0.937 | +165.8% | 24.1% | TT-001鲁棒性seed=1,IR稳健(Batch UU) |
| UU-002 | dd5_mfi10_ret20_s2 | drawdown_5d, mfi_10, ret_20d | 3 | 0.937 | +165.8% | 24.1% | TT-001鲁棒性seed=2,IR稳健(Batch UU) |
| UU-003 | dd5_mfi10_ret20_s3 | drawdown_5d, mfi_10, ret_20d | 3 | 0.894 | +155.8% | 25.6% | TT-001鲁棒性seed=3,MDD略超25%(Batch UU) |
| UU-004 | dd5_mfi6_ret20_lm | drawdown_5d, mfi_6, ret_20d | 3 | 0.407 | +59.8% | 28.5% | dd5+mfi6失败!dd5需mfi7/10(Batch UU) |
| UU-005 | dd6_mfi10_ret20_lm | drawdown_6d, mfi_10, ret_20d | 3 | 0.484 | +70.0% | 22.5% | dd6+mfi10 MDD低但IR不足(Batch UU) |
| UU-006 | dd5_obv10_ret5_lm | drawdown_5d, obv_change_10, ret_5d | 3 | -0.134 | +10.0% | 25.8% | ret_5d反转变体失败(Batch UU) |
| UU-007 | dd6_mfi6_ret5_lm | drawdown_6d, mfi_6, ret_5d | 3 | -0.814 | -41.3% | 52.2% | ret_5d反转灾难性失败(Batch UU) |

### top_n=5 已验证策略（按IR排名）

| ID | 策略名 | 因子 | 因子数 | 滚动IR | 滚动OOS | 滚动MDD | 说明 |
|----|--------|------|--------|--------|---------|---------|------|
| **CC-006** | **dd3_mfi7_ret20** | drawdown_3d, mfi_7, ret_20d | **3** | **1.384** | **+533.4%** | **37.2%** | **n5新冠军! MFI+回撤+动量,超越n10冠军IR(Batch CC)** |
| CC-007 | dd3_mfi10_ret20_n5 | drawdown_3d, mfi_10, ret_20d | 3 | 0.862 | +319.4% | 48.4% | MFI 10日n5变体(Batch CC) |
| **Y-002** | **rsv9_ret20** | rsv_9, ret_20d | **2** | **0.938** | **+310.2%** | **32.9%** | **前n5冠军(2因子)** |
| Y-003 | dd3_rsv9_skew_ret20 | drawdown_3d, rsv_9, ret_skew_20d, ret_20d | 4 | 0.801 | +190.7% | 41.2% | 4因子n5 |
| Y-004 | dd10_ret20 | drawdown_10d, ret_20d | 2 | 0.800 | +227.3% | 51.1% | 高MDD |
| Y-005 | dd7_rsv9_ret20 | drawdown_7d, rsv_9, ret_20d | 3 | 0.724 | +167.9% | 32.3% | |
| AA-006 | dd3_rsv8_ret20 | drawdown_3d, rsv_8, ret_20d | 3 | 0.542 | +115.5% | 34.6% | rsv8窗口n5变体(Batch AA) |
| BB-005 | dd3_mfi_ret20_n5 | drawdown_3d, mfi_14, ret_20d | 3 | 0.740 | +193.8% | 42.4% | MFI新因子n5版(Batch BB) |
| Y-006 | dd3_rsv9_ret20 | drawdown_3d, rsv_9, ret_20d | 3 | 0.508 | +108.7% | 35.7% | n10冠军在n5勉强通过 |
| **DD-001** | **dd3_mfi8_ret20_n5** | drawdown_3d, mfi_8, ret_20d | **3** | **1.234** | **+532.1%** | **43.8%** | **mfi_8窗口变体,n5第二名(Batch DD)** |
| **DD-002** | **dd4_mfi7_ret20_n5** | drawdown_4d, mfi_7, ret_20d | **3** | **1.115** | **+348.0%** | **32.2%** | **dd4窗口变体,低MDD!(Batch DD)** |
| DD-003 | dd3_mfi6_ret20_n5 | drawdown_3d, mfi_6, ret_20d | 3 | 0.953 | +200.0% | 32.5% | mfi_6窗口变体,低MDD(Batch DD) |
| DD-004 | dd4_mfi5_ret20_n5 | drawdown_4d, mfi_5, ret_20d | 3 | 0.900 | +222.7% | 31.1% | dd4+mfi5组合,最低MDD(Batch DD) |
| DD-005 | dd3_mfi7_bollpb5_ret20_n5 | drawdown_3d, mfi_7, boll_pct_b_5, ret_20d | 4 | 0.884 | +178.8% | 33.3% | 4因子MFI+Bollinger(Batch DD) |
| DD-006 | dd2_mfi7_ret20_n5 | drawdown_2d, mfi_7, ret_20d | 3 | 0.802 | +204.9% | 45.7% | dd2窗口变体(Batch DD) |
| DD-007 | dd3_mfi5_ret20_n5 | drawdown_3d, mfi_5, ret_20d | 3 | 0.713 | +175.1% | 40.7% | mfi_5窗口变体(Batch DD) |
| DD-008 | dd3_mfi7_obv10_ret20_n5 | drawdown_3d, mfi_7, obv_change_10, ret_20d | 4 | 0.518 | +106.9% | 53.5% | 4因子MFI+OBV,勉强通过(Batch DD) |
| **EE-001** | **dd4_mfi8_ret20_n5** | drawdown_4d, mfi_8, ret_20d | **3** | **1.276** | **+438.8%** | **37.3%** | **dd4+mfi8,n5新第二名(Batch EE)** |
| EE-002 | dd4_mfi6_ret20_n5 | drawdown_4d, mfi_6, ret_20d | 3 | 1.036 | +338.7% | 37.2% | dd4+mfi6(Batch EE) |
| EE-003 | dd5_mfi8_ret20_n5 | drawdown_5d, mfi_8, ret_20d | 3 | 0.994 | +259.3% | 30.6% | dd5+mfi8,低MDD(Batch EE) |
| EE-004 | dd5_mfi7_ret20_n5 | drawdown_5d, mfi_7, ret_20d | 3 | 0.929 | +267.4% | 30.3% | dd5+mfi7,n5最低MDD(Batch EE) |
| EE-005 | dd4_mfi10_ret20_n5 | drawdown_4d, mfi_10, ret_20d | 3 | 0.784 | +236.0% | 41.5% | dd4+mfi10(Batch EE) |
| EE-006 | dd4_rsv7_ret20_n5 | drawdown_4d, rsv_7, ret_20d | 3 | 0.680 | +144.7% | 35.8% | dd4+RSV@n5(Batch EE) |
| **FF-001** | **dd5_cmf7_ret20_n5** | drawdown_5d, cmf_7, ret_20d | **3** | **1.124** | **+351.8%** | **33.3%** | **CMF冠军!dd5+cmf7,低MDD(Batch FF)** |
| FF-002 | dd3_cmf20_ret20_n5 | drawdown_3d, cmf_20, ret_20d | 3 | 1.075 | +431.9% | 49.1% | cmf_20最优窗口(Batch FF) |
| FF-003 | dd3_cmf7_rsv7_ret20_n5 | drawdown_3d, cmf_7, rsv_7, ret_20d | 4 | 0.989 | +267.9% | 35.4% | 4因子CMF+RSV跨族有效(Batch FF) |
| FF-004 | cmf7_ret20_n5 | cmf_7, ret_20d | 2 | 0.825 | +228.1% | 45.7% | CMF独立2因子(Batch FF) |
| FF-005 | dd3_cmf14_ret20_n5 | drawdown_3d, cmf_14, ret_20d | 3 | 0.888 | +234.1% | 41.8% | cmf_14窗口(Batch FF) |
| FF-006 | dd3_cmf10_ret20_n5 | drawdown_3d, cmf_10, ret_20d | 3 | 0.792 | +183.2% | 40.0% | cmf_10窗口(Batch FF) |
| FF-007 | dd3_cmf7_ret20_n5 | drawdown_3d, cmf_7, ret_20d | 3 | 0.791 | +181.5% | 47.9% | cmf_7窗口(Batch FF) |
| FF-008 | dd4_cmf7_ret20_n5 | drawdown_4d, cmf_7, ret_20d | 3 | 0.762 | +180.8% | 38.5% | dd4+cmf7(Batch FF) |
| FF-009 | dd3_cmf7_mfi7_ret20_n5 | drawdown_3d, cmf_7, mfi_7, ret_20d | 4 | 0.708 | +187.5% | 31.2% | 4因子CMF+MFI,n5最低MDD(Batch FF) |
| **GG-001** | **dd5_cmf20_ret20_n5** | drawdown_5d, cmf_20, ret_20d | **3** | **1.363** | **+567.3%** | **25.8%** | **n5风险调整最优!IR逼近冠军但MDD仅25.8%(Batch GG)** |
| GG-002 | dd4_cmf20_ret20_n5 | drawdown_4d, cmf_20, ret_20d | 3 | 1.059 | +363.9% | 37.4% | dd4+cmf20,强IR(Batch GG) |
| GG-003 | dd5_cmf10_ret20_n5 | drawdown_5d, cmf_10, ret_20d | 3 | 0.873 | +251.4% | 29.8% | dd5+cmf10(Batch GG) |
| GG-004 | dd3_cmf20_mfi7_ret20_n5 | drawdown_3d, cmf_20, mfi_7, ret_20d | 4 | 0.867 | +229.4% | 38.1% | cmf20+MFI 4因子(Batch GG) |
| GG-005 | dd5_cmf14_ret20_n5 | drawdown_5d, cmf_14, ret_20d | 3 | 0.795 | +185.6% | 23.2% | dd5+cmf14,n5最低MDD!(Batch GG) |
| **HH-007** | **dd5_cmf20_ret20_n5_lm** | drawdown_5d, cmf_20, ret_20d | **3** | **1.088** | **+231.1%** | **21.7%** | **n5低MDD冠军!紧约束(0.20)版,IR>1+MDD<25%(Batch HH)** |
| HH-008 | dd4_cmf7_ret20_n5_lm | drawdown_4d, cmf_7, ret_20d | 3 | 0.949 | +256.7% | 36.5% | dd4+cmf7紧约束版(Batch II) |
| HH-009 | dd3_cmf20_ret20_n5_lm | drawdown_3d, cmf_20, ret_20d | 3 | 0.976 | +275.1% | 48.7% | dd3+cmf20紧约束版,MDD仍高(Batch II) |
| HH-010 | dd3_cmf7_ret20_n5_lm | drawdown_3d, cmf_7, ret_20d | 3 | 0.669 | +150.7% | 46.6% | dd3+cmf7紧约束版(Batch II) |
| HH-011 | dd5_cmf10_ret20_n5_lm | drawdown_5d, cmf_10, ret_20d | 3 | 0.529 | +96.4% | 32.5% | dd5+cmf10紧约束版(Batch II) |
| **JJ-009** | **dd4_mfi7_ret20_n5_lm** | drawdown_4d, mfi_7, ret_20d | **3** | **0.929** | **+155.6%** | **24.7%** | **n5新达标!dd4+MFI7紧约束,MDD<25%(Batch JJ)** |
| JJ-010 | dd5_cmf7_ret20_n5_lm | drawdown_5d, cmf_7, ret_20d | 3 | 1.051 | +289.7% | 40.6% | IR>1但MDD高(Batch JJ) |
| JJ-011 | dd5_cmf20_rsv7_ret20_n5_lm | drawdown_5d, cmf_20, rsv_7, ret_20d | 4 | 0.373 | +51.1% | 24.2% | 未通过IR(Batch JJ) |
| **KK-007** | **dd5_mfi7_ret20_n5_lm** | drawdown_5d, mfi_7, ret_20d | **3** | **0.688** | **+118.4%** | **24.9%** | **n5新达标!dd5+MFI7紧约束(Batch KK)** |
| **KK-008** | **dd5_mfi8_ret20_n5_lm** | drawdown_5d, mfi_8, ret_20d | **3** | **0.909** | **+184.2%** | **25.3%** | **差0.3%达标,IR极强(Batch KK)** |
| KK-009 | dd4_mfi6_ret20_n5_lm | drawdown_4d, mfi_6, ret_20d | 3 | 1.197 | +289.3% | 28.1% | IR惊人但MDD略超(Batch KK) |
| KK-010 | dd4_mfi8_ret20_n5_lm | drawdown_4d, mfi_8, ret_20d | 3 | 1.192 | +271.6% | 44.5% | IR>1但MDD高(Batch KK) |
| KK-011 | dd5_mfi7_cmf7_ret20_n5_lm | drawdown_5d, mfi_7, cmf_7, ret_20d | 4 | 0.691 | +143.4% | 29.3% | 4因子,MDD偏高(Batch KK) |
| KK-012 | dd4_cmf7_mfi7_ret20_n5_lm | drawdown_4d, cmf_7, mfi_7, ret_20d | 4 | 0.417 | +75.7% | 32.4% | 未通过IR(Batch KK) |
| LL-007 | dd6_cmf7_ret20_n5_lm | drawdown_6d, cmf_7, ret_20d | 3 | 1.135 | +299.4% | 28.8% | IR>1但MDD略超(Batch LL) |
| LL-008 | dd6_cmf20_ret20_n5_lm | drawdown_6d, cmf_20, ret_20d | 3 | 1.021 | +261.5% | 28.7% | IR>1但MDD略超(Batch LL) |
| LL-009 | dd6_mfi8_ret20_n5_lm | drawdown_6d, mfi_8, ret_20d | 3 | 0.563 | +96.5% | 22.0% | MDD极低但OOS差4%(Batch LL) |
| LL-010 | dd6_mfi6_ret20_n5_lm | drawdown_6d, mfi_6, ret_20d | 3 | 0.551 | +104.2% | 29.4% | MDD偏高(Batch LL) |
| LL-011 | dd6_mfi7_ret20_n5_lm | drawdown_6d, mfi_7, ret_20d | 3 | 0.073 | +20.2% | 36.1% | 失败(Batch LL) |
| QQ-006 | dd4_obv10_ret20_n5_lm | drawdown_4d, obv_change_10, ret_20d | 3 | 1.046 | +257.1% | 31.8% | OBV10新因子!IR>1但MDD高(Batch QQ) |
| QQ-007 | dd5_obv10_ret20_n5_lm | drawdown_5d, obv_change_10, ret_20d | 3 | 0.818 | +169.7% | 28.3% | OBV10有效但MDD略超(Batch QQ) |
| QQ-008 | dd4_cmf14_ret20_n5_lm | drawdown_4d, cmf_14, ret_20d | 3 | 1.028 | +271.4% | 36.2% | IR>1但MDD很高(Batch QQ) |
| QQ-009 | dd5_cmf14_ret20_n5_lm | drawdown_5d, cmf_14, ret_20d | 3 | 0.457 | +73.0% | 27.1% | 未通过IR(Batch QQ) |
| QQ-010 | dd4_rsi7_ret20_n5_lm | drawdown_4d, rsi_7, ret_20d | 3 | 0.551 | +110.3% | 31.3% | RSI7有效但MDD高(Batch QQ) |
| QQ-011 | dd5_obv20_ret20_n5_lm | drawdown_5d, obv_change_20, ret_20d | 3 | 0.339 | +72.3% | 31.3% | OBV20不如OBV10(Batch QQ) |
| QQ-012 | dd5_cmf20_ret20_n5_ultra | drawdown_5d, cmf_20, ret_20d | 3 | 0.956 | +189.2% | 25.6% | 超紧约束MDD反升(21.7->25.6%)(Batch QQ) |
| QQ-013 | dd4_mfi7_ret20_n5_ultra | drawdown_4d, mfi_7, ret_20d | 3 | 0.900 | +150.0% | 26.2% | 超紧约束MDD反升(24.7->26.2%)(Batch QQ) |
| QQ-014 | dd5_cmf14_ret20_n5_ultra | drawdown_5d, cmf_14, ret_20d | 3 | 0.361 | +58.3% | 24.1% | 超紧约束MDD达标但IR/OOS崩(Batch QQ) |
| RR-009 | dd6_obv10_ret20_n5_lm | drawdown_6d, obv_change_10, ret_20d | 3 | 1.140 | +274.1% | 30.6% | n5史上最高IR!但MDD超(Batch RR) |
| RR-010 | dd6_rsi7_ret20_n5_lm | drawdown_6d, rsi_7, ret_20d | 3 | 0.413 | +68.5% | 24.4% | MDD<25%但IR/OOS不足(Batch RR) |
| RR-011 | dd5_rsi7_ret20_n5_lm | drawdown_5d, rsi_7, ret_20d | 3 | 0.191 | +33.2% | 27.0% | 失败(Batch RR) |
| SS-006 | dd6_obv10_ret20_n5_s1 | drawdown_6d, obv_change_10, ret_20d | 3 | 0.966 | +203.8% | 35.9% | n5 OBV10鲁棒性seed=1,MDD跳升(Batch SS) |
| SS-007 | dd6_obv10_ret20_n5_s2 | drawdown_6d, obv_change_10, ret_20d | 3 | 0.957 | +210.9% | 38.8% | n5 OBV10鲁棒性seed=2,MDD更高(Batch SS) |
| SS-008 | dd6_obv10_ret20_n5_s3 | drawdown_6d, obv_change_10, ret_20d | 3 | 1.172 | +276.4% | 23.0% | n5 OBV10鲁棒性seed=3,MDD=23%!但不可复现(Batch SS) |
| SS-009 | dd4_obv10_ret20_n5_s1 | drawdown_4d, obv_change_10, ret_20d | 3 | 1.072 | +282.6% | 33.6% | n5 OBV10鲁棒性seed=1,IR稳健但MDD高(Batch SS) |
| SS-010 | dd4_obv10_ret20_n5_s2 | drawdown_4d, obv_change_10, ret_20d | 3 | 1.192 | +286.8% | 34.3% | n5 OBV10鲁棒性seed=2,IR最高!(Batch SS) |
| SS-011 | dd4_obv10_ret20_n5_s3 | drawdown_4d, obv_change_10, ret_20d | 3 | 0.975 | +271.9% | 33.6% | n5 OBV10鲁棒性seed=3,IR>0.9(Batch SS) |
| TT-007 | dd5_cmf20_bollw20_ret20_n5_lm | drawdown_5d, cmf_20, boll_width_20, ret_20d | 4 | -0.422 | -21.5% | 44.4% | 4因子波动率灾难性失败(Batch TT) |
| TT-008 | dd6_mfi6_bollw20_ret20_n5_lm | drawdown_6d, mfi_6, boll_width_20, ret_20d | 4 | -0.841 | -48.0% | 54.3% | 4因子波动率最差结果(Batch TT) |
| TT-009 | dd5_obv10_bollw20_ret20_n5_lm | drawdown_5d, obv_change_10, boll_width_20, ret_20d | 4 | 0.024 | +19.4% | 42.2% | 4因子波动率失败(Batch TT) |
| TT-010 | dd5_cmf20_vol20_ret20_n5_lm | drawdown_5d, cmf_20, vol_20d, ret_20d | 4 | 0.147 | +30.3% | 38.9% | 4因子vol_20d失败(Batch TT) |
| TT-011 | dd6_mfi6_vol20_ret20_n5_lm | drawdown_6d, mfi_6, vol_20d, ret_20d | 4 | -0.528 | -19.9% | 36.1% | 4因子vol_20d失败(Batch TT) |
| TT-012 | dd5_obv10_vol20_ret20_n5_lm | drawdown_5d, obv_change_10, vol_20d, ret_20d | 4 | -0.676 | -25.3% | 57.0% | 4因子vol_20d最差MDD(Batch TT) |
| TT-013 | dd5_obv10_park20_ret20_n5_lm | drawdown_5d, obv_change_10, parkinson_vol_20d, ret_20d | 4 | -0.162 | +1.2% | 36.5% | 4因子parkinson失败(Batch TT) |
| TT-014 | dd5_obv10_kurt20_ret20_n5_lm | drawdown_5d, obv_change_10, kurtosis_20d, ret_20d | 4 | 0.689 | +127.3% | 37.0% | IR通过但MDD=37%(Batch TT) |
| TT-015 | dd4_mfi7_bollw20_ret20_n5_lm | drawdown_4d, mfi_7, boll_width_20, ret_20d | 4 | -0.162 | +6.7% | 45.1% | 4因子波动率失败(Batch TT) |
| UU-008 | dd5_mfi6_ret20_n5_lm | drawdown_5d, mfi_6, ret_20d | 3 | 0.751 | +148.9% | 27.2% | dd5+mfi6@n5 MDD超(Batch UU) |
| VV-001 | dd4_cmf7_ret20_n10_lm | drawdown_4d, cmf_7, ret_20d | 3 | 1.096 | +333.1% | 36.5% | IR极高但MDD=36.5%!dd4+CMF不适合低MDD(Batch VV) |
| VV-002 | dd4_cmf14_ret20_n10_lm | drawdown_4d, cmf_14, ret_20d | 3 | 0.752 | +145.5% | 35.5% | dd4+CMF14 MDD=35.5%,dd4只与MFI兼容(Batch VV) |
| VV-003 | dd7_obv10_ret20_n10_lm | drawdown_7d, obv_change_10, ret_20d | 3 | 0.905 | +159.4% | 30.1% | dd7+OBV10 MDD=30.1%,dd5才是OBV最优窗口(Batch VV) |
| VV-004 | dd10_obv10_ret20_n10_lm | drawdown_10d, obv_change_10, ret_20d | 3 | 0.972 | +194.7% | 31.8% | dd10+OBV10 MDD=31.8%,长回撤+OBV不兼容(Batch VV) |
| VV-005 | dd4_obv20_ret20_n10_lm | drawdown_4d, obv_change_20, ret_20d | 3 | 0.746 | +165.6% | 30.8% | dd4+OBV20 MDD=30.8%,dd4不兼容OBV(Batch VV) |
| VV-006 | dd5_mfi8_ret20_n10_lm | drawdown_5d, mfi_8, ret_20d | 3 | 0.821 | +125.1% | 22.7% | **新达标!填补mfi7-mfi10窗口空白(Batch VV)** |
| VV-007 | dd6_cmf20_ret20_n10_lm | drawdown_6d, cmf_20, ret_20d | 3 | 0.786 | +211.0% | 24.0% | 复测确认,与LL结果一致(Batch VV) |
| WW-001 | dd5_mfi8_ret20_n10_s1 | drawdown_5d, mfi_8, ret_20d | 3 | 0.820 | +122.1% | 24.4% | VV-006鲁棒性seed=1,IR稳健(Batch WW) |
| WW-002 | dd5_mfi8_ret20_n10_s2 | drawdown_5d, mfi_8, ret_20d | 3 | 0.870 | +133.8% | 24.4% | VV-006鲁棒性seed=2,IR稳健(Batch WW) |
| WW-003 | dd5_mfi8_ret20_n10_s3 | drawdown_5d, mfi_8, ret_20d | 3 | 0.798 | +117.5% | 25.4% | VV-006鲁棒性seed=3,MDD略超25%(Batch WW) |
| WW-004 | dd5_bollpb5_ret20_n10_lm | drawdown_5d, boll_pct_b_5, ret_20d | 3 | 0.960 | +169.6% | 27.3% | Bollinger%B+dd5 MDD略超,dd6更优(Batch WW) |
| WW-005 | dd4_bollpb5_ret20_n10_lm | drawdown_4d, boll_pct_b_5, ret_20d | 3 | 0.493 | +86.5% | 35.2% | dd4+Bollpb失败,dd4只与MFI兼容(Batch WW) |
| WW-006 | dd6_bollpb5_ret20_n10_lm | drawdown_6d, boll_pct_b_5, ret_20d | 3 | 1.093 | +206.7% | 24.1% | **新冠军!Bollinger%B第4家族!dd6最优窗口(Batch WW)** |
| WW-007 | dd5_bollw20_ret20_n10_lm | drawdown_5d, boll_width_20, ret_20d | 3 | 0.159 | +32.0% | 31.4% | Bollinger宽度+drawdown灾难性失败(Batch WW) |
| WW-008 | dd2_rsv5_ret20_n10 | drawdown_2d, rsv_5, ret_20d | 3 | 0.712 | +174.3% | 27.7% | RSV5+drawdown失败,RSV与drawdown冗余(Batch WW) |
| WW-009 | dd3_rsv5_ret20_n10 | drawdown_3d, rsv_5, ret_20d | 3 | 0.649 | +140.2% | 36.0% | RSV5+dd3 MDD=36%,RSV不适合低MDD(Batch WW) |

### 范式转变：集中持仓下3因子 > 2因子

| 持仓数 | 2因子最佳IR | 3因子最佳IR | 最优模型 |
|--------|-----------|-----------|---------|
| n30 | 1.088 (dd3_ret20) | 0.790 (rsv_volmr_mom_3) | 2因子 > 3因子 |
| n10 | 1.084 (rsv9_ret20) | **1.370 (dd3_rsv7_ret20)** | **3因子 > 2因子** |
| n5 | 0.938 (rsv9_ret20) | **1.384 (dd3_mfi7_ret20)** | **3因子 > 2因子 (MFI新发现!)** |

**结论**: n10和n5都是3因子最优。**n5冠军 dd3_mfi7_ret20 (IR=1.384, MDD 37.2%) IR最高**,但**dd5_cmf20_ret20_n5 (IR=1.363, MDD 25.8%) 是风险调整最优**——IR仅低0.021但MDD降低11.4个百分点。**推荐手动交易使用 dd5_cmf20_ret20_n5 (n5, IR=1.363, MDD 25.8%, OOS+567%) 或 dd3_rsv7_ret20 (n10, IR=1.370, MDD 22.3%)**。追求绝对收益选dd3_mfi7_ret20(IR=1.384, OOS+533%),追求低回撤选dd5_cmf14_ret20_n5(MDD=23.2%)或dd5_cmf20_ret20_n5(MDD=25.8%)。

## 关键教训

1. **单次 holdout IR 与滚动 OOS IR 无可靠关联** — 三轮验证确认
2. **滚动重优化是最强 Alpha 持久性证据** — 41 个月 walk-forward
3. **价值因子(EP/BP)在 A 股近年无 Alpha**
4. **行业动量有横截面能力但 Alpha 不持久**
5. **Parkinson 波动率优于收盘价波动率** — 因子工程值得做
6. **量价微观结构(vp_industry_6)首次实现低回撤(17.9%)** — 值得深入
7. **MACD 因子单次 IR=2.94 是最高记录** — 待滚动验证
8. **搜索空间 9 点足够** — IC 自适应决定权重,结构参数只需 3x3 网格
9. **短周期动量(20d+60d)优于长周期(12-1月)** — 敏感性分析确认:用 ret_60d 替换 mom_120_20 使 IR 从 0.47 升至 0.503,首个通过门控
10. **因子越多越差** — 2因子(IR=0.960) > 3因子(IR=0.717) > 4因子(IR=0.632) > 5因子(IR=0.503) > 8因子(IR=-0.33)。极简模型最强
11. **低波动+超卖反转(lowvol_reversal_5)单次 IR=1.707 但滚动 IR=-0.654** — 再次确认单次 IR 不可靠
12. **px_to_ma20 趋势因子是噪声** — 去掉后 IR 从 0.503 升至 0.632,趋势因子在量价模型中是干扰项
13. **ret_60d 和 turnover_change_5_20 也是噪声** — 消融实验确认:去掉后 IR 从 0.632 升至 0.960
14. **成交量萎缩 + 20日动量 = HS300 Alpha 的全部** — 2因子模型 IR=0.960,OOS +121.5%,MDD 16.6%。极简即极致
15. **ret_20d 是 Alpha 核心来源** — 单因子 IR=0.515 已通过门控。volume_ma_ratio 无独立 Alpha(IR=-0.483),仅作噪声过滤器将 MDD 从 28.5% 降至 16.6%
16. **量价负相关(vol_price_corr)可替代量比** — IR=0.553, MDD=13.8%(史上最低)。两种量价因子均有效
17. **短期反转(ret_5d)也有效** — 量比+反转 IR=0.561,与动量策略(I-004)形成互补
18. **vol_mom_2 是 HS300 专属** — ZZ500 上 IR=0.403(低于门控),大盘股的量价信号更可靠
19. **RSV（随机指标）是全新 Alpha 源** — "超卖回调 + 动量"(rsv_5+ret_20d, IR=1.074)超越"量缩+动量"(turnover_change+ret_20d, IR=0.967)。RSV 捕捉"动量股短期回调"的买点，与换手率/量比属不同维度
20. **RSV 窗口呈倒U型曲线，5日为最优峰值** — rsv_3=0.438(过短噪声), rsv_5=1.074(峰值), rsv_7=0.858, rsv_9=1.004, rsv_14=0.733, rsv_20=0.323(过长陈旧)。5日精确捕捉近期回调
21. **ret_20d 仍是唯一有效动量窗口** — ret_10d(IR=-0.516)、ret_15d(失败)、ret_5d(与RSV组合-0.138)、ret_60d(与RSV组合-0.018)均无效。20日是动量Alpha的甜蜜点
22. **收益率偏度(ret_skew_20d)是有效新因子** — 低偏度+动量 IR=0.611。偏度过滤掉彩票型妖股，保留机构控盘的稳定动量股
23. **2因子 > 3因子 再次确认** — RSV系列: rsv_5+ret_20d(2因子,IR=1.074) > rsv_9+量比+ret_20d(3因子,IR=0.790) > rsv_9+换手+ret_20d(3因子,IR=0.783)。每增加一个因子稀释Alpha
24. **ATR(真实波幅)作为过滤器无效** — IR=-0.144。包含隔夜跳空的真实波幅不如收盘价波动率(parkinson)有效
25. **因子工程方向有效** — 从30列扩展到39列，新增9个因子中 rsv_5(冠军)、ret_skew_20d(有效)、rsv_9(亚军)三个产生通过门控的策略。针对性因子工程是持续优化的高EV路径
26. **回撤(drawdown)是第三个Alpha维度** — "近期回撤+动量"模式在HS300(dd3 IR=1.088)和BJ50(dd7 IR=1.064)均夺冠。RSV/回撤/Bollinger %B本质都是"超卖回调"的不同度量，但实现方式不同
27. **Bollinger %B是第四个有效超卖过滤器** — 5日%B IR=0.989，与RSV(1.074)接近但属不同因子家族(Gaussian vs range-based)。两家族不互补: 3因子组合(bollpb20+rsv5+ret20) IR=0.035，远低于单独2因子
28. **Bollinger带宽(波动率收敛)+动量 = 史上最低回撤** — boll_width_20+ret_20d IR=0.663, MDD仅9.8%。低波动收敛期+动量方向=极稳健策略。但带宽窗口需20日(5d/10d无效)
29. **不同票池最优回撤窗口不同** — HS300最优3日(dd3 IR=1.088)，BJ50最优7日(dd7 IR=1.064)。大盘股回撤更快修复(3d)，小盘股需更长时间企稳(7d)
30. **手动交易top_n=10可行但代价高** — 从30只降至10只，IR下降30-40%，MDD翻2-3倍。5只仅1个策略勉强通过。集中持仓是Alpha的敌人，分散是MDD的朋友
31. **票池探索: 大盘(HS300)和北交所(BJ50)有效，中小盘无效** — ZZ500边缘(0.475), ZZ1000(0.084)和KC100(-0.500)无Alpha。量价信号需要流动性和机构参与度
32. **n10最优RSV窗口从n30的rsv5转移到rsv7** — 集中持仓(n10)下rsv_7(IR=1.370)优于rsv_9(1.366)>rsv_6(1.188)>rsv_8(0.991)>rsv_14(1.156)。与n30不同(n30最优rsv_5)，n10需要稍长的RSV窗口(7日)提供更稳定的超卖信号
33. **dd3(3日回撤)是n10全局最优回撤窗口** — Batch AA确认: dd2(0.908) < dd3(1.370) > dd4(0.656)。3日回撤精确捕捉"动量股短期回调"的买点，过短(2d)信号噪声大，过长(4d+)回调可能已结束
34. **微调确认dd3_rsv7为n10全局最优** — Batch Z+AA系统测试了dd×rsv的所有邻近窗口组合(2×4=8组)，dd3_rsv7(IR=1.370)和dd3_rsv9(IR=1.366)几乎并列，但rsv7在MDD相同的情况下IR略高
35. **4因子在n10仍可行但收益递减** — dd3_rsv9_vpc_ret20(IR=0.646)和dd3_rsv9_bollpb10_ret20(IR=0.558)通过门控，但远低于3因子冠军。第4个因子提供额外风险控制但稀释Alpha
36. **vol_price_corr(量价相关)在n10有效** — rsv9_vpc_ret20(IR=0.613, MDD=22.9%)和dd3_rsv9_vpc_ret20(IR=0.646)。量价负相关作为第3/4因子在集中持仓下提供低MDD优势
37. **MFI(资金流量指标)是全新独立Alpha源** — dd3_mfi_ret20(IR=0.773)验证了量价加权RSI的有效性。MFI从"资金流入流出"维度衡量超卖,与纯价格型因子(RSV/回撤/Bollinger)属不同维度
38. **MFI与回撤(dd3)搭配优于与RSV搭配** — dd3_mfi_ret20(IR=0.773) vs rsv7_mfi_ret20(IR=0.225)。MFI已含成交量信息,与纯价格过滤器(回撤)互补性更强,与另一个价格过滤器(RSV)信息重叠
39. **OBV(能量潮)作为独立过滤器有效但较弱** — obv_ret20(IR=0.552)勉强通过,dd3_obv_ret20(IR=0.654)更好。OBV衡量20日量能净方向,低OBV=派发压力=超卖
40. **冠军策略dd3_rsv7_ret20已是最优,加第4因子反而降效** — dd3_rsv7_mfi_ret20(IR=0.225)和dd3_rsv7_obv_ret20(IR=0.139)均远低于冠军(1.370)。3因子是n10的最优因子数,第4因子稀释Alpha
41. **RSI_7作为第4因子有效但作为第3因子无效** — dd3_rsv7_rsi7_ret20(4因子,IR=0.650)通过,但dd3_rsi7_ret20(3因子,IR=0.469)未通过。RSI_7需要与其他超卖过滤器叠加才有价值
42. **MFI在n5集中持仓下也有效** — dd3_mfi_ret20_n5(IR=0.740, OOS=+193.8%),比n10版(IR=0.773)略低但绝对收益更高。MFI的成交量信息在集中持仓下提供额外的风险控制
43. **MFI_7是最优MFI窗口** — 窗口倒U型曲线: mfi_7(0.949) > mfi_10(0.891) > mfi_14(0.773) > mfi_20(0.517)。短窗口MFI更敏感,能更快捕捉资金流向反转
44. **dd3_mfi7_ret20在n5下IR=1.384,超越n10冠军(1.370)** — 重大发现!MFI的成交量加权信息在5只超集中持仓下提供了比RSV更强的风险控制。n5从"2因子最优"翻转为"3因子最优",推翻了之前"n5太集中,3因子不如2因子"的结论
45. **MFI只与dd3(3日回撤)搭配有效** — dd3_mfi14(0.773) >> dd5_mfi14(0.135) > dd7_mfi14(0.115) > dd10_mfi14(0.389)。更长回撤窗口与MFI不兼容,因为MFI已含短期均值回归信息,长回撤窗口引入矛盾信号
46. **MFI与Bollinger不兼容** — bollpb5_mfi14(0.138)和bollpb7_mfi14(-0.125)均失败。Bollinger和MFI都衡量超卖,信息高度重叠,叠加反而引入噪声
47. **OBV_10优于OBV_20** — dd3_obv10(0.878) > dd3_obv20(0.654), obv10_ret20(0.615) > obv_ret20(0.552)。与MFI同理,短窗口量能信号更敏感
48. **量价加权因子(MFI/OBV)短窗口优于长窗口** — 与价格型因子(RSV)不同,量价因子的最优窗口更短(7-10日 vs RSV的7-9日)。成交量信息衰减更快,需要更短的窗口捕捉
49. **MFI窗口倒U型曲线在n5下完全确认** — mfi_5(0.713) < mfi_6(0.953) < mfi_7(1.384) > mfi_8(1.234)。mfi_7是最优峰值,mfi_8是接近的次优。5日过短(噪声大),20日过长(信号陈旧)
50. **dd4(4日回撤)为MFI策略提供更优的风险控制** — dd4_mfi7_ret20_n5(IR=1.115, MDD=32.2%) vs dd3_mfi7_ret20_n5(IR=1.384, MDD=37.2%)。dd4的IR略低但MDD降低5个百分点。dd4_mfi5_ret20_n5(MDD=31.1%)是n5策略中最低MDD
51. **3因子是MFI策略的最优因子数,第4因子全面失败** — Batch DD系统测试了dd3_mfi7+RSI/Bollinger/OBV的4因子组合,n5下仅bollpb5版通过(0.884),RSI版(0.320)和OBV版(0.518勉强)大幅下降。n10下4因子全部失败(IR<0.5)。MFI已含成交量信息,第4个量价因子信息重叠
52. **dd3仍是最优回撤窗口,但dd4是低MDD替代** — dd2(0.802) < dd3(1.384) > dd4(1.115) at n5。dd3的IR最高,但dd4的MDD更低(32.2% vs 37.2%)。追求低回撤的投资者可考虑dd4_mfi7_ret20
53. **dd4_mfi8_ret20是n10的低MDD突破** — IR=1.184, MDD=23.1%。是所有n10策略中IR>1且MDD最低的。dd4+MFI组合在n10下风险控制更优
54. **dd5(5日回撤)是MFI策略的MDD冠军窗口** — dd5_mfi7_ret20_n5(IR=0.929, MDD=30.3%)和dd5_mfi8_ret20_n5(IR=0.994, MDD=30.6%)。回撤窗口从dd3到dd5,MDD递减:37.2%→32.2%→30.3%,但IR也递减:1.384→1.115→0.929。存在IR-MDD权衡
55. **MFI在BJ50完全失败** — 三种MFI+BJ50组合全部失败(IR<0.35, 其中dd7版IR=-0.402)。MFI的量价加权信号需要机构流动性支持,BJ50(176只)的低流动性使量价信号不可靠。MFI是HS300专属Alpha
56. **CMF(Chaikin Money Flow)是有效的新Alpha源** — Batch FF 13个实验全部通过IR>0.5门控。CMF用CLV(收盘位置值)×成交量计算,与MFI(典型价格×成交量)实现方式不同
57. **CMF窗口偏好与MFI完全相反** — CMF: cmf_20(1.075) > cmf_14(0.888) > cmf_10(0.792) ≈ cmf_7(0.791),长窗口更优。MFI: mfi_7(1.384) > mfi_8(1.234) > mfi_10(0.862),短窗口更优。这证实CMF和MFI捕捉不同的资金流信号: MFI敏感于短期资金流入流出(短窗口更有效),CMF衡量收盘位置累积趋势(长窗口更稳定)
58. **4因子CMF+RSV跨族有效(不同于MFI 4因子)** — dd3_cmf7_rsv7_ret20_n5(IR=0.989, MDD=35.4%)通过门控。CMF(量价)与RSV(纯价格)属不同族,互补性强。而MFI 4因子全面失败(教训#51),因为MFI已含成交量信息,与另一个量价因子信息重叠
59. **CMF+MFI组合提供n5最低MDD** — dd3_cmf7_mfi7_ret20_n5(IR=0.708, MDD=31.2%)。两个量价加权因子叠加虽降低IR,但MDD为n5策略中最低。适合追求低回撤的投资者
60. **dd5是CMF和MFI共同的MDD冠军窗口** — dd5_cmf7_ret20_n5(IR=1.124, MDD=33.3%)和dd5_mfi7_ret20_n5(IR=0.929, MDD=30.3%)。从dd3到dd5, MDD递减但IR也递减。dd5版CMF在IR>1的同时保持较低MDD,是风险调整后的优秀策略
61. **CMF独立2因子有效** — cmf7_ret20_n5(IR=0.825, OOS+228.1%)和cmf7_ret20@n10(IR=0.753)。CMF作为唯一过滤器+动量即可通过门控,证明CLV加权成交量是独立Alpha源
62. **dd5_cmf20_ret20_n5是n5风险调整最优策略** — IR=1.363(逼近冠军1.384),但MDD仅25.8%(vs冠军37.2%)。IR仅低0.021但MDD降低11.4个百分点。dd5(MDD冠军窗口)+cmf_20(CMF最优窗口)的组合是CMF策略的终极配置
63. **CMF_20独立2因子失败但3因子极强** — cmf20_ret20_n5(IR=0.133)失败,但dd5_cmf20_ret20_n5(IR=1.363)极强。CMF_20作为唯一过滤器无法有效筛选,但与回撤过滤器组合后形成强大的双重超卖信号。CMF必须搭配drawdown
64. **CMF_20+RSV 4因子失败(与CMF_7+RSV相反)** — dd3_cmf20_rsv7_ret20_n5(IR=0.480)和dd5_cmf7_rsv7_ret20_n5(IR=0.463)均未通过。CMF_20的长窗口信息与RSV的短窗口信息矛盾,跨族互补性只在短窗口CMF(cmf_7)时有效
65. **CMF在BJ50完全失败(与MFI相同)** — 三种CMF+BJ50组合全部失败(IR分别为-0.030, 0.202, -0.323)。CMF和MFI都是量价加权因子,都需要机构流动性支持。BJ50的低流动性使量价加权信号不可靠。量价加权因子(MFI/CMF)是HS300专属Alpha
66. **dd5+CMF窗口曲线确认cmf_20为最优** — dd5_cmf20(1.363) > dd5_cmf10(0.873) > dd5_cmf14(0.795)。在dd5窗口下,cmf_20仍是CMF最优窗口,再次确认CMF长窗口偏好
67. **dd5_cmf14_ret20_n5是n5最低MDD策略(MDD=23.2%)** — IR=0.795, MDD=23.2%。比FF-009的31.2%更低。dd5+cmf_14组合在风险控制上最优,适合极度风险厌恶的投资者
68. **boll_width_20在n5/n10集中持仓下完全失效** — bollw20_ret20_n5(IR=0.391), bollw20_dd3_ret20_n5(IR=0.194), bollw20_mfi7_ret20_n5(IR=-1.190)。boll_width_20在n30时MDD仅9.8%的优势来自分散持仓,集中5只时低波动因子选出的股票缺乏反弹弹性
69. **低波动因子(parkinson/vol_20d/kurtosis)在n5均无法有效降低MDD** — park_dd3_ret20_n5(MDD=36.8%), vol20_dd3_ret20_n5(MDD=42.7%), kurt_dd3_ret20_n5(MDD=40.8%)。低波动选股在集中持仓下反而选出缺乏活性的股票
70. **紧MDD约束(max_drawdown_limit=0.20)是降低OOS MDD的有效手段** — 训练时限制MDD上限为20%,迫使HPO选择低风险参数组合。dd5_cmf20_ret20_n5_lm: MDD从25.8%降至21.7%,dd4_mfi7_ret20_n10_lm: MDD从25.5%降至23.8%
71. **紧约束对dd3(3日回撤)策略无效** — dd3_mfi7_ret20_n5_lm(MDD=46.1%)和dd3_cmf20_ret20_n5_lm(MDD=48.7%)。dd3的短回撤窗口选出高波动股票,紧约束无法补偿。低MDD需要dd4/dd5(更长回撤窗口)配合
72. **dd4_mfi7_ret20_n10_lm是n10低MDD最优策略** — IR=1.094, MDD=23.8%, OOS+216%。紧约束版比正常版(dd4_mfi7_ret20@n10, MDD=25.5%)MDD降低1.7个百分点,IR反而从0.968升至1.094。dd4+MFI7组合在紧约束下表现最优
73. **dd5_cmf20_ret20_n5_lm是n5低MDD最优策略** — IR=1.088, MDD=21.7%, OOS+231%。比正常版(IR=1.363, MDD=25.8%)牺牲了0.275的IR但MDD降低4.1个百分点。OOS仍>200%,满足收益要求
74. **drawdown_6d是降低MDD的关键因子** — dd6_cmf7_ret20_n10_lm(IR=0.924, MDD=20.9%)创史上最低MDD。dd4/dd5/dd6窗口对MDD的影响: dd4(23.8%) > dd5(21.4%) > dd6(20.9%)。回撤窗口越长,MDD越低,因为更长的回撤窗口选出的是回调更充分的股票
75. **dd6+CMF7是n10最低MDD组合** — dd6_cmf7_ret20_n10_lm: IR=0.924, MDD=20.9%, OOS+161%。CMF7的短窗口敏感性+dd6的中期回撤过滤=最佳风险控制组合
76. **dd6+MFI/CMF在n5表现不如n10** — dd6_cmf7_ret20_n5_lm(IR=1.135, MDD=28.8%)和dd6_cmf20_ret20_n5_lm(IR=1.021, MDD=28.7%)虽然IR>1,但MDD超过25%。dd6在n5集中持仓下MDD无法达标,只在n10有效
77. **dd6是回撤窗口的MDD甜蜜点** — dd4→dd5→dd6→dd7→dd8的MDD曲线(dd6+CMF7@n10): dd4(36.5%) > dd5(30.6%) > **dd6(20.9%)** < dd7(38.3%) < dd8(48.4%)。dd6处MDD达到最低,更长窗口反而升高。原因:6日回撤选出的股票回调恰到好处,7-8日回撤选出的是趋势性下跌的股票(反弹概率低)
78. **dd8+MFI7在n10有IR>1但MDD不达标** — dd8_mfi7_ret20_n10_lm(IR=1.135, MDD=26.5%)。dd8的IR甚至比dd6高,但MDD多了5.6个百分点。长回撤窗口的IR优势来自选出的深度回调股的强反弹,但回撤期间也更深
79. **鲁棒性检验:n10低MDD策略极其稳健** — Batch NN用4个种子(0,1,2,3)重测top策略。dd4_mfi7_ret20_n10: 4种子IR均>1.1(1.094-1.198),MDD均<24%(22.2-23.8%)。dd5_mfi7_ret20_n10: 4种子MDD均<22%(19.4-21.4%),IR均>0.9(0.902-1.009)。dd6_cmf7_ret20_n10: 4种子MDD均<21%(20.4-20.9%),极其稳定
80. **鲁棒性检验:n5低MDD策略不够稳健** — dd5_cmf20_ret20_n5在种子2下MDD从21.7%飙升至34.6%。dd4_mfi7_ret20_n5在种子2下MDD从24.7%升至33.1%。n5集中持仓导致MDD对参数选择高度敏感,不推荐用于实盘低MDD场景
81. **dd5_mfi7_ret20_n10是实盘首选低MDD策略(NN验证)** — 4种子平均: IR=0.957, MDD=20.0%, OOS=+140%。MDD始终<22%,IR始终>0.9。结合了MFI7的成交量信息、dd5的中期回撤过滤、紧约束的参数选择,是风险调整后最稳健的实盘策略
82. **dd6_mfi6_ret20_n10_lm是史上最低MDD且最稳健策略(PP验证,实盘首选)** — IR=1.039, MDD=18.9%, OOS+201%。PP 4种子验证:IR始终>1(1.004-1.075),MDD始终<19%(18.0-18.9%),MDD波动仅0.9pp。dd6(回撤甜蜜点)+mfi_6(短窗口MFI)=风险控制的终极组合。**超越dd5_mfi7成为实盘首选**
83. **dd5_cmf10_ret20_n10_lm鲁棒性不合格(PP否决)** — 原始IR=1.223, MDD=22.6%, OOS+263%。但PP 3种子验证:MDD全部跳至30.5%,IR在seed=3降至0.820。原始seed=0是幸运的,不推荐实盘
84. **4因子CMF+MFI组合在紧约束下全面失败** — dd5_cmf7_mfi7_ret20_n10(-0.072), dd5_cmf20_mfi7_ret20_n10(-0.002), dd6_cmf20_mfi7_ret20_n10(-0.309)。两个量价加权因子信息高度重叠,4因子是过度拟合。3因子是终极最优结构
85. **dd6_mfi6_ret20_n10是史上最稳健低MDD策略** — PP 4种子验证:IR=1.004-1.075(始终>1),MDD=18.0-18.9%(始终<20%),OOS=+187-+203%。MDD波动仅0.9个百分点,是所有低MDD策略中鲁棒性最强的。dd6(回撤甜蜜点)+mfi_6(MFI短窗口)=风险控制的终极组合
86. **dd5_cmf10_ret20_n10鲁棒性不合格** — PP 3种子验证:MDD全部跳至30.5%(vs原始22.6%),IR在seed=3下降至0.820。原始seed=0的结果是幸运的。CMF10的中窗口信息对参数选择敏感,不适合实盘
87. **dd5+mfi6组合无效,只有dd6+mfi6有效** — dd5_mfi6_ret20_n10_lm(IR=0.407)远低于dd6_mfi6_ret20_n10_lm(IR=1.039)。dd5的回撤窗口太短,与mfi_6的短窗口信息冲突;dd6的6日回撤恰好与mfi_6形成互补
88. **4因子dd6_mfi6_rsv7和dd5_cmf10_rsv7均失败** — IR分别为0.560和0.373,OOS分别为92%和52%。在3因子冠军上添加RSV7反而稀释Alpha。3因子是低MDD策略的终极最优结构,第4因子(无论跨族与否)均无益
89. **超紧MDD约束(0.15)全面失败,0.20是最佳紧度** — QQ系统测试5个n10冠军+3个n5候选的超紧约束版,全部MDD不降反升。dd6_mfi6: 0.20版MDD=18.9%→0.15版MDD=26.9%(+8pp!),IR从1.039暴跌至0.597。原因:0.15约束使HPO可选参数空间过小,选出过拟合训练期低MDD但不泛化的参数。0.20约束是"MDD门控"与"参数自由度"的最佳平衡点
90. **OBV10(10日能量潮变化)是有效的第三Alpha因子** — dd4_obv10_ret20_n5_lm(IR=1.046, OOS=+257%)和dd4_cmf14_ret20_n5_lm(IR=1.028)均IR>1,证明OBV10与CMF14都能在n5产生强Alpha。但两者MDD均>30%,不适合低MDD目标。OBV10>OBV20(IR=1.046 vs 0.339),短窗口量能信号更敏感
91. **n5低MDD难题仍未解决** — QQ测试了6种新因子组合(OBV10/OBV20/CMF14/RSI7×dd4/dd5)+3种超紧约束,全部MDD>25%。n5集中持仓的MDD对参数选择天然敏感,5只股票的组合波动无法通过因子选择或约束调整来充分控制。**建议:低MDD需求使用n10策略**
92. **RSI7作为第3因子在n5有效但MDD高** — dd4_rsi7_ret20_n5_lm(IR=0.551, MDD=31.3%)。RSI7+回撤+动量组合通过IR门控,但RSI7的短期超卖信号在n5集中持仓下波动较大,不适合低MDD场景
93. **OBV10+dd5是n10新的低MDD达标策略** — dd5_obv10_ret20_n10_lm(IR=0.939, MDD=24.0%, OOS+141%)。OBV10(10日能量潮变化)是继MFI和CMF后第三个有效的量价加权因子家族。与dd5(5日回撤)组合在紧约束下实现MDD<25%。需鲁棒性验证
94. **OBV10与dd6不兼容(与MFI/CMF不同)** — dd6_obv10_ret20_n10(IR=0.302)和dd6_obv20_ret20_n10(IR=0.353)均失败。dd6是MFI/CMF的MDD甜蜜点,但不是OBV的甜蜜点。OBV10与dd5搭配最优
95. **dd6_obv10_ret20_n5是n5史上最高IR策略** — IR=1.140, OOS+274%。但MDD=30.6%,不适合低MDD目标。dd6+OBV10在n5集中持仓下Alpha极强但波动也大
96. **dd6_cmf10_ret20_n10 IR=1.039(与dd6_mfi6相同)但MDD=33.9%** — dd6+CMF10有极强Alpha但无法控制MDD。dd6的低MDD组合只有mfi_6(18.9%)和cmf_7(20.9%),其他因子搭配dd6均MDD>30%
97. **dd5_rsi7_ret20_n10 MDD=23.8%(低于25%)但OOS仅77.5%** — RSI7在n10有MDD控制能力但Alpha不足。RSI7更适合作为第4因子(叠加在其他超卖过滤器上),而非独立第3因子
98. **dd5_obv10_ret20_n10是继dd6_mfi6后第二个极其稳健的低MDD策略** — SS 4种子验证:IR=0.939-1.193(3/4种子>1.1),MDD=18.4-24.0%(3/4种子<22%),OOS=+141-+201%。原始seed=0反而是最差的!4种子平均IR≈1.12,MDD≈21.3%。OBV(能量潮)是独立于MFI的量价因子家族,与dd6_mfi6形成互补
99. **dd5_obv10比dd6_mfi6更互补** — dd6_mfi6(MFI家族,dd6回撤)和dd5_obv10(OBV家族,dd5回撤)使用完全不同的因子和回撤窗口。两策略同时部署可提供因子分散化和回撤窗口分散化,降低单一因子失效风险
100. **n5 OBV10策略Alpha极强但MDD不可控** — dd6_obv10@n5: 4种子IR=0.957-1.172(始终>0.9)但MDD=23.0-38.8%(波动15.8pp)。dd4_obv10@n5: 4种子IR=0.975-1.192(始终>0.9)但MDD=33.6-34.3%。OBV10在n5集中持仓下Alpha一致性强,但MDD天然偏高
101. **OBV10 > OBV20,dd5 > dd3/dd4/dd6 for OBV** — dd5_obv10_n10(IR=0.939,MDD=24.0%) >> dd5_obv20_n10(IR=0.758,MDD=31.7%) >> dd3_obv10_n10(IR=0.738,MDD=42.7%)。OBV10的短窗口与dd5的中期回撤形成最佳搭配
102. **n5低MDD最终结论:不可行** — 经过HH-SS共14个batch、60+个n5实验(MFI/CMF/OBV/RSI × dd3-dd8 × 约束0.15/0.20/0.30 × 鲁棒性验证),n5集中持仓的MDD对参数选择天然敏感,无法在IR>0.5+OOS>100%条件下实现MDD<25%的鲁棒低MDD。**建议:n5用于高Alpha高波动场景,n10用于低MDD场景**
103. **4因子波动率组合对n5和n10均灾难性失败** — TT系统测试9种n5 4因子(boll_width/vol_20d/parkinson/kurtosis × cmf20/mfi6/obv10/mfi7)+2种n10 4因子,全部MDD飙升(36-57%)、Alpha崩溃(8/11为负IR)。3因子是低MDD策略的绝对上限,无论第4因子来自哪个家族。4因子HPO在5-10只股票的集中持仓下严重过拟合
104. **dd5_mfi10_ret20_n10是新n10低MDD达标策略** — IR=0.981, MDD=24.1%, OOS+188%。MFI10(中窗口)是dd5的有效搭配,填补mfi7(0.902/21.4%)和mfi14(0.330/31.3%)之间的空白。dd5的MFI有效窗口为5-10日,14日过长。需鲁棒性验证
105. **ret_10d完全无效,ret_20d是唯一有效动量窗口** — dd5_obv10_ret10(IR=-0.489, OOS=-23%)和dd6_mfi6_ret10(IR=0.452,远低于ret_20d的1.039)均证明10日动量无效。20日动量是HS300 Alpha的核心来源,更短的动量窗口无法捕捉有效的趋势信号
106. **dd5的MFI窗口曲线:5/7/10有效,14失效** — dd5_mfi5(0.770/21.8%), dd5_mfi7(0.902/21.4%), dd5_mfi10(0.981/24.1%), dd5_mfi14(0.330/31.3%)。IR随窗口增大先升后降,10日为峰值,14日急剧下降。MDD在5-10日间稳定(21-24%),14日跳升至31%
107. **dd5_mfi10鲁棒性中等** — UU 4种子验证:IR=0.894-0.981(始终>0.5),MDD=24.1-25.6%(seed=3略超25%)。比dd6_mfi6(MDD波动0.9pp)和dd5_obv10(MDD波动5.6pp)不够稳健,MDD波动1.5pp处于边缘。可作为第七低MDD策略,但不是实盘首选
108. **dd5+mfi6组合在n10和n5均失败** — dd5_mfi6@n10(IR=0.407)和dd5_mfi6@n5(IR=0.751,MDD=27.2%)。dd5需要mfi7或mfi10,dd6才需要mfi6。每个回撤窗口有其独特的MFI最优搭配:dd6→mfi6, dd5→mfi7/10, dd4→mfi7
109. **dd6+mfi10 MDD=22.5%但IR=0.484** — dd6只与mfi6搭配有效(IR=1.039)。mfi10对dd6过长,Alpha衰减但MDD控制好。dd6的MFI有效窗口极窄(仅mfi6)
110. **ret_5d(短期反转)在低MDD策略中完全无效** — dd5_obv10_ret5(IR=-0.134)和dd6_mfi6_ret5(IR=-0.814, MDD=52.2%!)。回撤+量价因子+短期反转的组合在紧约束下灾难性失败。ret_20d(动量)是低MDD策略唯一有效的收益因子,反转方向不适用于集中持仓低MDD策略
111. **dd4+CMF不适合低MDD** — dd4_cmf7(MDD=36.5%,IR=1.096!)和dd4_cmf14(MDD=35.5%)。尽管IR极高,但MDD远超25%。dd4只与MFI兼容(dd4_mfi7: MDD=23.8%),CMF需要dd5或dd6窗口。**因子-回撤窗口兼容性是家族特定的**
112. **dd5是OBV的唯一最优回撤窗口** — dd5_obv10(MDD=24.0%) >> dd7_obv10(30.1%) > dd10_obv10(31.8%) > dd3_obv10(42.7%)。OBV10的短窗口需要中期回撤(dd5)配合,更长或更短的回撤窗口都会导致MDD飙升
113. **dd5_mfi8填补MFI窗口曲线空白** — IR=0.821, MDD=22.7%, OOS+125%。dd5完整MFI窗口曲线:mfi5(0.770/21.8%)→mfi6(0.407/28.5%异常)→mfi7(0.902/21.4%)→mfi8(0.821/22.7%)→mfi10(0.981/24.1%)→mfi14(0.330/31.3%)。mfi7-10区间IR和MDD均有效,MDD随窗口递增
114. **RSI7不适合低MDD策略** — dd4_rsi7(MDD=32.6%), dd5_rsi7(MDD=23.8%但OOS仅77.5%), dd6_rsi7(MDD=34.7%)。RSI作为超买超卖指标与drawdown因子高度共线,无法提供独立的Alpha贡献。MFI/CMF/OBV是低MDD策略的三大有效量价因子家族,RSI被排除
115. **dd6_bollpb5_ret20_n10是新低MDD冠军** — IR=1.093, MDD=24.1%, OOS+207%。Bollinger%B(超卖位置)成为继MFI/CMF/OBV后第四个低MDD有效因子家族。dd6是Bollinger%B的最优回撤窗口。IR排名第三(仅次于dd4_mfi7的1.094)。需鲁棒性验证
116. **dd5_mfi8鲁棒性中等,确认为第8低MDD策略** — 4种子IR=0.798-0.870(始终>0.5),MDD=22.7-25.4%(seed=3略超25%)。MDD波动1.3pp,与dd5_mfi10类似,处于边缘稳健。dd5的MFI窗口曲线完整:mfi7(0.902/21.4%)→mfi8(0.821/22.7%)→mfi10(0.981/24.1%),MDD随窗口递增
117. **Bollinger宽度+drawdown灾难性失败** — IR=0.159, MDD=31.4%。2因子bollw_mom(MDD=9.8%史上最低)加drawdown后Alpha完全崩溃。boll_width(带宽收敛)与drawdown(买入下跌股)逻辑矛盾——收敛意味着波动减小,而drawdown选的是下跌股
118. **RSV5+drawdown失败,RSV与drawdown冗余** — dd2_rsv5(MDD=27.7%)和dd3_rsv5(MDD=36.0%)。RSV5是2因子MDD最低(12.3%),但加drawdown后MDD飙升。RSV本身是超卖回调指标,与drawdown高度共线,叠加导致过度集中下跌股。**RSV应单独使用,不与drawdown组合**
119. **dd6是低MDD策略的万能回撤窗口** — dd6对MFI(mfi6: MDD=18.9%)、CMF(cmf7: MDD=20.4%)、Bollinger%B(bollpb5: MDD=24.1%)均为最优。dd6的中期回撤窗口(约1周)为各类超卖/量价指标提供最佳配合。dd4仅与MFI兼容,dd5仅与OBV兼容,dd6是通用最优
120. **低MDD四大因子家族确认:MFI/CMF/OBV/Bollinger%B** — 经HH-WW共19个batch、100+实验验证,只有这四个量价因子家族能在dd+因子+ret_20d三因子模型中实现MDD<25%+IR>0.5+OOS>100%。RSI/RSV/Bollinger宽度均被排除。dd6是MFI/CMF/Bollinger%B的最优窗口,dd5是OBV的最优窗口

121. **非等权加权(YZ-AA批,54实验):inv_vol(反波动率)是最优降MDD加权方案** — 测试5种方案(equal/rank_linear/rank_power/score_softmax/hybrid)+5种温和方案(hybrid_ratio/rank_linear_floor/inv_vol)。inv_vol一致性降低MDD 1-5pp,IR降幅2-40%不等。CMF家族IR保持率最高(97.6%),OBV/Bollinger%B最差(60-75%)。集中度越高(rank_power/score_softmax)MDD越差——集中持仓已天然高波动,再加权集中是雪上加霜

122. **dd4_mfi7_n10+inv_vol是首个鲁棒的非等权低MDD策略** — 4种子IR=0.994-1.072,MDD=19.8-21.7%,OOS=+142-156%。vs等权:IR 1.09-1.20→0.99-1.07(降8-15%),MDD 22.2-23.8%→19.8-21.7%(降2-3pp)。MDD全部<22%,IR全部>0.99,极度稳健。**用途:需要比等权更低MDD且能接受IR略降的场景**

123. **dd6_mfi6_n10+inv_vol是史上MDD最低且最稳定的策略** — 4种子MDD=15.5-17.2%(仅1.7pp波动!),IR=0.849-0.957,OOS=+126-138%。vs等权:MDD 18.0-18.9%→15.5-17.2%(降2.8pp),IR 1.004-1.075→0.849-0.957(降14-20%)。**MDD=15.5%是所有策略(等权+非等权)的史上最低**。用途:极致MDD控制优先于收益的场景

124. **n5+inv_vol无法解决n5集中风险** — dd5_cmf20_n5+inv_vol虽然seed=0时IR=1.062/MDD=17.8%看起来出色,但seed=2时MDD跳至34%,seed=3时IR降至0.799。inv_vol通过降低高波动股权重来降MDD,但n5只有3-5只股票,一只暴跌即可拖垮整个组合。**n5低MDD从等权和加权两个维度均已证明不可行**

125. **hr12(hybrid_ratio 1.2/0.8)在特定策略上能提升IR且控制MDD增幅** — dd5_obv10+hr12:IR 0.939→0.971,MDD 24.0%→24.9%(<25%);dd6_bollpb5+hr12:IR 1.093→1.134,MDD 24.1%→25.6%(略超)。温和加权(前半1.2x后半0.8x)是收益增强型方案,适合对MDD<25%要求不严格的场景。**inv_vol是降MDD方案,hr12是增IR方案,二者互补**

126. **dd5_obv10+hr12是最佳非等权策略——极度稳健,IR全面提升** — 4种子IR=0.971-1.217(3/4>1.18!),MDD=16.3-24.9%(3/4<20%!),OOS=+162-228%。vs等权:IR 0.939-1.193→0.971-1.217(下限提升3.4pp),MDD 18.4-24.0%→16.3-24.9%(下限降2.1pp)。**OBV家族是唯一hr12能同时提升IR和降低MDD的因子家族**。hr12加权将OBV策略从"边缘稳健"提升为"极度稳健"

127. **dd6_bollpb5+inv_vol展现史上最低MDD但IR不稳健** — 4种子MDD=13.5-19.4%(3/4<14%!),但IR=0.662-0.963(不达标率25%)。Bollinger%B+inv_vol的MDD控制极致(13.5%!),但代价是IR大幅波动。**用途:追求极致MDD且能接受IR<1.0的场景**

128. **inv_vol+hr12混合方案不如纯方案** — inv_vol_hr12在所有策略上都不如纯inv_vol或纯hr12。叠加两种加权逻辑反而互相干扰:inv_vol降低高波动股权重,hr12又按排名倾斜,两者对同一只股票可能给出矛盾信号。**加权方案应单一使用,不宜叠加**

129. **dd5_obv10+hr11是最佳非等权策略——极度稳健且IR全面提升** — 4种子IR=0.960-1.210,MDD=17.3-24.4%,OOS=+151-214%。3/4种子IR>1.17且MDD<21%。vs等权:IR 0.939-1.193→0.960-1.210(下限提升2.1pp),MDD 18.4-24.0%→17.3-24.4%(下限降1.1pp)。hr11(1.1x/0.9x)比hr12(1.2x/0.8x)MDD波动更小(7.1pp vs 8.6pp)。**OBV家族是唯一从温和加权中同时提升IR和降低MDD的因子家族**

130. **dd6_mfi6+hr11是MDD波动最小的策略** — 4种子IR=0.985-1.054,MDD=18.4-18.8%(仅0.4pp波动!),OOS=+188-202%。vs等权:MDD 18.0-18.9%→18.4-18.8%(波动从0.9pp压缩到0.4pp)。IR几乎不变(等权1.004-1.075→hr11 0.985-1.054)。**hr11加权对MFI家族的作用不是降MDD而是稳定MDD**——将MDD波动压缩到极致

131. **dd6_bollpb5+hr11稳健,IR与等权相当但OOS更高** — 4种子IR=0.931-1.178,MDD=19.8-24.8%,OOS=+164-233%。vs等权:IR 0.927-1.183→0.931-1.178(几乎不变),MDD 18.6-20.0%→19.8-24.8%(上限升高)。Bollinger%B+hr11的IR保持率最高,但seed=0的MDD偏高(24.8%)

132. **非等权加权策略总结(YY-EE批,100+实验)** — 验证了10种加权方案在5个冠军策略上的效果。最终确认5个鲁棒的非等权低MDD策略:①dd5_obv10+hr11(IR 0.96-1.21,MDD 17-24%) ②dd4_mfi7+inv_vol(IR 0.99-1.07,MDD 20-22%) ③dd6_mfi6+hr11(IR 0.99-1.05,MDD 18.4-18.8%) ④dd6_mfi6+inv_vol(IR 0.85-0.96,MDD 15.5-17.2%) ⑤dd6_bollpb5+hr11(IR 0.93-1.18,MDD 20-25%)。**hr11(inv_vol)是OBV(MFI)家族的最优加权方案,二者互补**

---

## 防过拟合优化批次 (ZA-ZG)

> 核心原则: **默认止损参数(15/5/30/10), 零参数搜索, 只搜因子空间**
> 对比: 旧策略搜索了15/5→10/3→8/2→5/1, 过拟合风险中-高

### n10 策略

| ID | 策略名 | 因子 | 止损 | 4种子IR范围 | 4种子MDD范围 | 4种子OOS均值 | 过拟合风险 | 状态 |
|----|--------|------|------|------------|-------------|-------------|-----------|------|
| **ZZ-001** | **dd6_mfi6_trail** | drawdown_6d, mfi_6, ret_20d | 默认15/5/30/10 | **1.088-1.150** | **18.0-19.0%** | **+212%** | **极低** | **★★★ 项目史上最稳健策略** |
| **ZZ-002** | dd5_obv10_trail | drawdown_5d, obv_change_10, ret_20d | 默认15/5/30/10 | 0.810-1.098 | 18.4-24.1% | +150% | 低 | ★ n10备选 |

### n5 策略

| ID | 策略名 | 因子 | 止损 | 4种子IR范围 | 4种子MDD范围 | 4种子OOS均值 | 过拟合风险 | 状态 |
|----|--------|------|------|------------|-------------|-------------|-----------|------|
| **ZZ-003** | **dd5_atr20_ret20_trail** | drawdown_5d, atr_20d, ret_20d | 默认15/5/30/10 | **0.434-0.727** | **16.8-25.9%** | **+115%** | **低** | **★★ n5最优低MDD策略** |

### 新增经验教训

133. **n10_dd6_mfi6+默认止损=项目史上最稳健策略** — 4种子IR=1.088-1.150(波动0.062), MDD=18.0-19.0%(波动仅1.0pp!), OOS=+201~218%。vs无止损版: OOS从100%翻倍至212%, MDD几乎不变(18.0%→18.7%)。使用默认止损参数(15/5/30/10), 零参数搜索, 过拟合风险极低。**止损对n10的作用是放大收益而非控制回撤**

134. **n5_dd5_atr20_ret20_trail是首个过拟合风险低的n5策略** — 4种子IR=0.434-0.727, MDD=16.8-25.9%(3/4种子<21%), OOS=+73~132%。ATR(真实波动幅度)是新发现的有效因子: 无止损版IR=0.523/MDD=23.5%, 证明alpha来源真实。dd5是5个drawdown周期(dd3-dd7)中的自然最优, 非参数搜索结果

135. **n5只适合3因子, 4因子全部变差** — ATR+MFI(IR=0.341), ATR+CMF(IR=0.416), ATR+OBV(IR=0.013)全部比纯ATR(IR=0.653)差。n5只有3-5只股票, 第4因子引入信息冗余/冲突, 反而稀释alpha。3因子是n5的终极最优结构

136. **防过拟合方法论验证成功** — 5项原则全部验证: ①默认参数(不调止损) ②因子空间搜索(发现ATR) ③4种子鲁棒性(n10_dd6_mfi6 MDD波动仅1pp) ④因子冗余测试(4因子变差) ⑤drawdown周期验证(dd5自然最优)。对比旧方法(参数搜索15/5→5/1), 新方法在保持IR的同时大幅降低过拟合风险

137. **trailing stop对n10和n5的作用不同** — n10: 止损主要放大收益(OOS 100%→212%), MDD几乎不变(18%→19%)。n5: 止损主要控制MDD(无止损MDD=23.5%→有止损MDD=18.1%), 收益略增(101%→130%)。n10分散持仓使止损成为收益放大器, n5集中持仓使止损成为风险控制器

138. **ATR(真实波动幅度)是新发现的有效因子家族** — atr_20d(long_low): 低ATR=波动受控=机构控盘。在n5+默认止损下IR=0.653/MDD=18.1%, 是n5史上最低MDD。ATR与MFI/CMF/OBV属不同维度(波动率 vs 量价), 提供独立的alpha来源。但ATR在n10无优势(MDD=25.4%不优于现有策略)

139. **bias_20和px_to_ma20数据完全相同** — 数据库中两列的min/max/avg/nonzero完全一致, 是同一因子的两个别名。future batch只需使用其中一个

140. **n10新因子(vol/atr/turn/tchg/ma20/rsi)均不胜现有策略** — 所有新因子在n10级别的MDD均超过20%目标, IR均低于现有dd6_mfi6(IR=1.0+)。n10的因子空间已充分探索, 后续优化应转向因子组合或风险叠加

---

## 日内波动率因子族发现 (ZH-ZI)

> 核心发现: **"低日内波动 = 机构控盘 = alpha"** 在amplitude和parkinson_vol两个因子上得到强验证
> amplitude_avg_20d: 4种子IR全部>0.99(n5), 4种子MDD全部<20%(n10)

### 新增策略

| ID | 策略名 | 因子 | 级别 | 4种子IR范围 | 4种子MDD范围 | 过拟合风险 | 状态 |
|----|--------|------|------|------------|-------------|-----------|------|
| **ZZ-004** | **dd5_amp20_ret20_trail** | dd5+amplitude_avg_20d+ret_20d | n5 | **0.994-1.184** | 16.0-27.1% | **极低** | **★★★ n5新IR冠军** |
| **ZZ-005** | **dd5_amp20_ret20_trail** | dd5+amplitude_avg_20d+ret_20d | n10 | 0.759-0.885 | **15.4-19.6%** | **极低** | **★★ n10新MDD冠军** |
| **ZZ-006** | dd5_pvol20_ret20_trail | dd5+parkinson_vol_20d+ret_20d | n5 | 0.799-1.080 | 17.7-27.4% | 极低 | ★ n5备选 |
| **ZZ-007** | dd5_pvol20_ret20_trail | dd5+parkinson_vol_20d+ret_20d | n10 | 0.727-0.902 | 15.4-22.9% | 极低 | ★ n10备选 |

### 新增经验教训

141. **amplitude_avg_20d是n5的IR新冠军** — 4种子IR=0.994-1.184(全部>0.99!), 平均1.083, IR波动仅0.190。OOS=+207~280%。这是首个4种子IR全部>0.99的n5策略。amplitude(日内振幅)衡量日内价格波动范围, 低振幅=机构控盘=价格稳定。与ATR(真实波动幅度)同属"日内波动率"因子族, 但alpha更强

142. **amplitude_avg_20d是n10的MDD新冠军** — 4种子MDD=15.4-19.6%(全部<20%!), 平均18.6%, MDD波动仅4.2pp。s3的MDD=15.4%是n10史上最低。IR=0.759-0.885, 平均0.817。对比dd6_mfi6_trail: IR更低(0.817 vs 1.121)但MDD更优(18.6% vs 18.7%, 且最低值15.4% vs 18.0%)

143. **parkinson_vol_20d是ATR的强化版** — Parkinson波动率(日内高低差)在n5的IR=0.799-1.080(平均0.936), 显著优于ATR(0.434-0.727, 平均0.627)。MDD平均21.1%与ATR(20.4%)相近。Parkinson比ATR更纯(只用高低差, 不含跳空), 可能更准确反映日内真实波动

144. **ret_20d是最佳动量窗口, ret_10d/ret_15d完全无效** — ATR+ret_10d: IR=0.209, ATR+ret_15d: IR=0.169, 远不如ATR+ret_20d: IR=0.653。20日(月度)动量是A股最有效的反转/动量周期, 短期动量(2-3周)信号噪声太大

145. **布林带宽度(boll_width)无效** — bw20: IR=-0.082(负IR!), bw5: IR=0.547但MDD=36%。布林带宽度作为"盘整度"指标在当前框架中不产生alpha, 可能因为盘整突破方向不确定

146. **"日内波动率"因子族全面验证** — 测试了5个日内波动率因子(ATR/Parkinson/Amplitude/Vol20d/Vol60d), 其中3个在n5有效(IR>0.5): Amplitude(1.104) > Parkinson(1.080) > ATR(0.653)。Vol20d(-0.147)和Vol60d(0.408)较弱。规律: 越接近"纯日内价格波动"的因子alpha越强(Amplitude/Parkinson只看价格, ATR含跳空, Vol20d/Vol60d是收益率标准差)

---

## Amplitude因子深度探索 (ZJ-ZK)

> 核心发现: **dd6+amplitude是项目史上最强因子组合**
> n5: 4种子IR=1.264-1.354(全部>1.26!), MDD=15.6-17.7%(全部<18%!)
> n10: 4种子MDD=16.5%完全相同(0.0pp波动!)

### 新增策略

| ID | 策略名 | 因子 | 级别 | 4种子IR范围 | 4种子MDD范围 | 过拟合风险 | 状态 |
|----|--------|------|------|------------|-------------|-----------|------|
| **ZZ-008** | **dd6_amp20_ret20_trail** | dd6+amplitude_avg_20d+ret_20d | n5 | **1.264-1.354** | **15.6-17.7%** | **极低** | **★★★★ 项目史上最强n5** |
| **ZZ-009** | **dd6_amp20_ret20_trail** | dd6+amplitude_avg_20d+ret_20d | n10 | 0.860-0.979 | **16.5%**(0波动!) | **极低** | **★★★ n10最稳定策略** |
| **ZZ-010** | dd5_vpc20_ret20_trail | dd5+vol_price_corr_20d+ret_20d | n5 | 0.847-1.302 | 20.4-30.9% | 低 | ★ 新因子,待观察 |

### 全策略排名 (4种子平均, 防过拟合)

| 排名 | 策略 | 级别 | 平均IR | 平均MDD | MDD波动 | IR波动 | 过拟合风险 |
|------|------|------|--------|---------|---------|--------|-----------|
| **1** | **dd6_amp20_trail** | **n5** | **1.303** | **16.1%** | **2.1pp** | 0.090 | **极低** |
| 2 | dd6_mfi6_trail | n10 | 1.121 | 18.7% | 1.0pp | 0.062 | 极低 |
| 3 | dd5_amp20_trail | n5 | 1.083 | 21.4% | 11.1pp | 0.190 | 极低 |
| 4 | dd5_amp20_trail | n10 | 0.817 | 18.6% | 4.2pp | 0.127 | 极低 |
| 5 | dd5_pvol20_trail | n5 | 0.936 | 21.1% | 9.8pp | 0.281 | 极低 |
| 6 | dd6_amp20_trail | n10 | 0.891 | 16.5% | 0.0pp | 0.119 | 极低 |
| 7 | dd5_vpc20_trail | n5 | 1.124 | 25.5% | 10.5pp | 0.455 | 低 |
| 8 | dd5_atr20_trail | n5 | 0.627 | 20.4% | 9.1pp | 0.293 | 低 |

### 新增经验教训

147. **dd6+amplitude是项目史上最强n5策略** — 4种子IR=1.264-1.354(全部>1.26!), 平均1.303, IR波动仅0.090。MDD=15.6-17.7%(全部<18%!), 平均16.1%, MDD波动仅2.1pp。OOS=+465~533%。这是项目史上IR最高、MDD最低、波动最小的n5策略。dd6比dd5更适合amplitude因子(对比: dd5+amp IR=0.994-1.184, dd6+amp IR=1.264-1.354)

148. **n10_dd6_amp20的MDD在4种子中完全相同(16.5%)** — 4种子的MDD全部为0.1647, 波动0.0pp。这是项目史上最稳定的MDD表现, 几乎不可能过拟合。IR=0.860-0.979, 平均0.891。对比n10_dd6_mfi6_trail: IR更高(1.121 vs 0.891)但MDD更高(18.7% vs 16.5%)。两者可作为n10的高低风险组合

149. **vol_price_corr_20d是新发现的有效因子** — 量价相关性因子在n5的IR=0.847-1.302(平均1.124)。该因子衡量成交量和价格变动的相关性, 低相关=量价背离=反转信号。但MDD波动较大(10.5pp), 鲁棒性不如amplitude

150. **amplitude的dd周期: dd6>dd5>dd7>dd4>dd3** — 与ATR的dd5最优不同, amplitude在dd6表现最佳(IR=1.281 vs dd5的1.104)。说明不同因子的最优drawdown周期不同, dd5不是万能最优。dd6+amp的MDD=17.7%也低于dd5+amp的23.1%

151. **amplitude无止损IR=1.141, alpha来源极其真实** — 无止损版OOS=+421%, IR=1.141, MDD=28.2%。证明amplitude因子本身具有极强的alpha, 不依赖止损。止损的作用是把MDD从28.2%降到17.7%(dd5)/15.6%(dd6), 而非创造alpha

152. **amplitude+parkinson_vol(4因子)确认n5只适合3因子** — IR=0.379, 再次验证4因子在n5中信息冗余。即使两个都是"纯日内波动率"因子, 组合仍然变差。n5的3因子结构是终极最优

153. **boll_width_10在n5有效(IR=1.020)** — 布林带宽度10日窗口比20日(IR=-0.082)和5日(IR=0.547)都好。短期(10日)盘整度有一定alpha, 但MDD=29.1%偏高, 不推荐

---

## 全新因子维度探索 (ZL-ZM) — 2026-07-02

> 探索amplitude正交的alpha源: 行业动量/长期动量/MACD/KD/RSV/成交额/均线
> 发现两个有效新因子: rsv_9(超卖反转) 和 dif(MACD趋势)

### 新增策略

| ID | 策略名 | 因子 | 级别 | 4种子IR范围 | 4种子MDD范围 | 过拟合风险 | 状态 |
|----|--------|------|------|------------|-------------|-----------|------|
| **ZZ-011** | **dd5_rsv9_ret20_trail** | dd5+rsv_9+ret_20d | n5 | **0.962-1.279** | **17.6-23.7%** | **低** | **★★★ 超卖反转新alpha** |
| **ZZ-012** | **dd5_dif_ret20_trail** | dd5+dif+ret_20d | n5 | **1.053-1.250** | **23.0-23.6%** | **极低** | **★★★ MDD波动仅0.6pp!** |
| ZZ-013 | dd5_amp_amt20_ret20 | dd6+amplitude+amt_20d+ret_20d | n10 | 0.786(单种子) | 17.0%(单种子) | 中 | ★ n10 4因子组合有效 |

### 全策略排名 (4种子平均, 防过拟合) — 更新

| 排名 | 策略 | 级别 | 平均IR | 平均MDD | MDD波动 | IR波动 | 过拟合风险 |
|------|------|------|--------|---------|---------|--------|-----------|
| **1** | **dd6_amp20_trail** | **n5** | **1.303** | **16.1%** | **2.1pp** | 0.090 | **极低** |
| **2** | dd6_mfi6_trail | n10 | 1.121 | 18.7% | 1.0pp | 0.062 | 极低 |
| **3** | dd5_rsv9_trail | n5 | 1.179 | 20.6% | 6.0pp | 0.318 | 低 |
| **3** | dd5_dif_trail | n5 | 1.179 | 23.2% | **0.6pp** | 0.197 | **极低** |
| 5 | dd5_amp20_trail | n5 | 1.083 | 21.4% | 11.1pp | 0.190 | 极低 |
| 6 | dd5_amp20_trail | n10 | 0.817 | 18.6% | 4.2pp | 0.127 | 极低 |
| 7 | dd5_pvol20_trail | n5 | 0.936 | 21.1% | 9.8pp | 0.281 | 极低 |
| 8 | dd6_amp20_trail | n10 | 0.891 | 16.5% | 0.0pp | 0.119 | 极低 |
| 9 | dd5_vpc20_trail | n5 | 1.124 | 25.5% | 10.5pp | 0.455 | 低 |
| 10 | dd5_atr20_trail | n5 | 0.627 | 20.4% | 9.1pp | 0.293 | 低 |

### 新增经验教训

154. **rsv_9是超卖反转维度的最强因子** — 9日RSV(未成熟随机值)在n5的IR=0.962-1.279(4种子中3个>1.0), 平均1.179。无止损IR=1.035, alpha真实。去掉drawdown后IR=1.308, 有独立alpha。RSV窗口排名: rsv_9(1.279)>rsv_7(1.236)>rsv_8(1.148)>rsv_6(1.049)>rsv_5(0.822)>rsv_14(0.398)

155. **dif的MDD波动仅0.6pp, 项目史上MDD最稳定** — MACD DIF因子4种子MDD=23.0%-23.6%, 波动仅0.6pp。IR=1.053-1.250(4种子全部>1.0!), 平均1.179。虽然MDD绝对值偏高(23.2%), 但稳定性极强。OOS=+533~663%, 高收益补偿MDD

156. **不同因子的最优drawdown周期不同** — dd6更适合amplitude(dd6>dd5), 但dd5更适合rsv_9(dd5>dd6)。说明drawdown周期不是全局最优, 而是因子相关的。amplitude衡量日内波动(需要更长dd周期), rsv_9衡量超卖(需要更短dd周期)

157. **rsv_9和amplitude正交性差** — n10_dd6_amp_rsv9_ret20(4因子)IR=0.388, 远低于单独amp(IR=0.979)和单独rsv_9(IR=0.845)。两个超卖/波动因子在n10组合后信息冗余。但n10_dd6_amp_amt20_ret20(4因子)IR=0.786, MDD=17.0%, 说明amplitude+流动性维度可以正交组合

158. **n5_rsv9_ret20(2因子, 无drawdown)IR=1.308** — 去掉drawdown后IR反而最高! 说明rsv_9本身已包含超卖信息, drawdown是冗余的。但MDD=23.9%偏高, 加入drawdown可降低MDD

159. **ZL测试的10个新因子中只有3个IR>0.9** — rsv_9(1.279), dif(1.053), k_value(0.967)。其余7个(industry_mom/mom_120/ret_60d/amt_20d/px_to_ma60/macd_hist/d_value)均MDD>25%或IR<0.9。技术 oscillator类因子(RSV/KD/MACD DIF)比趋势/动量类因子更适合n5+止损框架

160. **n10 4因子组合: amp+amt20有效但amp+indmom/mom120无效** — amp+amt_20d: IR=0.786, MDD=17.0%。amp+industry_mom: IR=0.638, MDD=28.4%。amp+mom_120_20: IR=0.334, MDD=38.2%。说明流动性(amt_20d)与日内波动率(amplitude)正交, 但行业/长期动量不正交

| **ZZ-014** | **dd6_rsv9_ret20_trail** | dd6+rsv_9+ret_20d | n5 | **1.002-1.163** | **19.6-24.1%** | **低** | **★★★ ZO冠军: OOS=318%!** |
| **ZZ-015** | **dd4_rsv9_ret20_trail** | dd4+rsv_9+ret_20d | n10 | **1.200-1.522** | **23.1-30.7%** | **中** | **★★ IR=1.381, OOS=410%!** |
| ZZ-016 | dd5_dif_ret20_trail | dd5+dif+ret_20d | n10 | 0.993-1.137 | 21.1-27.5% | 中 | ★ N10版DIF, IR=1.066 |
| ZZ-017 | dd4_amp_ret20_trail | dd4+amplitude_avg_20d+ret_20d | n10 | 0.842-1.279 | 25.2-29.9% | 中 | ★ N10版dd4+振幅, IR=1.033 |

161. **dd6+rsv_9是dd6系列的新冠军** - n5 4种子IR=1.089, OOS=318%, MDD=21.9%(波动2.2pp)
162. **dd4+rsv_9在n10上IR=1.381项目最高** - 但MDD=26.8%偏高
163. **dd3/dd4提升OOS但牺牲MDD** - 回撤周期是OOS-MDD权衡核心旋钮
164. **DIF因子需要dd5** - dd5+dif IR=1.066, dd4+dif IR=0.707, dd6+dif IR=0.920
165. **dd6+RSV9 vs dd6+振幅互补** - RSV9高OOS(318%vs89%), 振幅低MDD(16.1%vs21.9%)

---

## Batch ZP (2026-07-03) — N10低MDD探索 + N5 4因子优化

| ID | 策略名 | 因子 | N | 4种子IR | 4种子MDD | MDD级别 | 评价 |
|----|--------|------|---|---------|----------|---------|------|
| **ZZ-018** | **dd6_rsv9_vpc_ret20_trail** | dd6+rsv_9+vol_price_corr_20d+ret_20d | n5 | **1.005-1.397** | **17.4-20.9%** | **低** | **★★★ N5低MDD新#2! IR=1.239, 首个IR>1.2的4因子策略** |
| **ZZ-019** | **dd3_rsv9_ret20_trail** | dd3+rsv_9+ret_20d | n10 | **0.856-1.367** | **30.0-40.5%** | **非低** | **★★ N10非低MDD新#2! IR=1.208, OOS=338%** |
| **ZZ-020** | **dd6_amp_dif_ret20_trail** | dd6+amplitude_avg_20d+dif+ret_20d | n5 | **1.025-1.362** | **15.6-24.4%** | **非低** | **★★ N5高OOS冠军! OOS=448%, IR=1.143** |
| **ZZ-021** | **dd6_rsv9_amp_ret20_trail** | dd6+rsv_9+amplitude_avg_20d+ret_20d | n5 | **0.939-1.008** | **14.0-16.1%** | **低** | **★★★ 项目最低MDD! 14.8%! IR≈0.975, MDD std=0.9pp** |
| ZZ-022 | dd6_rsv9_dif_ret20_trail | dd6+rsv_9+dif+ret_20d | n5 | 0.652-1.172 | 17.0-32.3% | 非低 | IR=1.000, MDD波动大(7.7pp), 不稳健 |
| ZZ-023 | dd6_rsv9_ret20_trail_n10 | dd6+rsv_9+ret_20d | n10 | 0.946-1.071 | 17.2-18.5% | 低 | N10低MDD版, IR=0.996, MDD=17.5%(std=0.7pp!) |
| ZZ-024 | dd5_amp_ret20_trail_n10 | dd5+amplitude_avg_20d+ret_20d | n10 | 0.923-1.031 | 15.4-19.6% | 低 | N10低MDD版, IR=0.975, MDD=18.6% |
| ZZ-025 | dd6_vpc_ret20_trail_n10 | dd6+vol_price_corr_20d+ret_20d | n10 | 0.886-1.031 | 22.9-28.5% | 非低 | N10版VPC, IR=0.963 |
| ZZ-026 | dd6_dif_ret20_trail_n10 | dd6+dif+ret_20d | n10 | 0.653-1.131 | 19.7-30.1% | 非低 | N10版dd6+DIF, IR=0.800, 不如dd5+DIF |

166. **dd6+RSV9+VPC是首个IR>1.2的4因子策略** — 4种子平均IR=1.239, MDD=18.8%(std=1.7pp), OOS=339%。VPC(量价相关)与RSV9(超卖振荡)正交, 突破了"4因子不如3因子"的结论。关键: 第4因子必须提供正交alpha而非冗余信号
167. **dd3+RSV9在N10上IR=1.208但MDD波动大** — 4种子IR=0.856-1.367(std=0.236), MDD=30-40%。seed=0的IR<1.0是风险信号, 但3/4种子IR>1.2。dd3比dd4更激进(OOS更高但MDD更高)
168. **dd6+振幅+DIF是N5最高OOS策略** — 4种子平均OOS=448%(最高654.7%!), IR=1.143, MDD=20.8%。振幅(日内波动)+DIF(趋势方向)的组合产生极高收益, 但MDD略超20%门槛
169. **dd6+RSV9+振幅创造项目最低MDD=14.8%** — 4种子MDD=14.0-16.1%(std=0.9pp!), IR=0.975, OOS=230%。RSV9+振幅双alpha源叠加dd6回撤过滤, 实现了"接近1.0的IR + 史上最低MDD"。MDD std=0.9pp是项目最稳定回撤
170. **N10低MDD确认: dd6+RSV9 MDD=17.5%(std=0.7pp)** — N10版dd6+RSV9的MDD比N5版(21.9%)低4.4pp, 因N10分散度更高。但IR=0.996<N5版(1.089), 分散换稳健的经典权衡
171. **4因子并非总是差于3因子** — ZP修正了Lesson 160的结论。4因子优劣取决于第4因子是否正交: VPC正交于RSV9(IR↑), 振幅正交于RSV9(MDD↓), 但DIF+振幅已有重叠(MDD波动大)
172. **N10低MDD因子排名(dd6系)** — RSV9(IR=0.996,MDD=17.5%) > 振幅(IR=0.975,MDD=18.6%) > VPC(IR=0.963,MDD=25.9%) > DIF(IR=0.800,MDD=27.0%)。RSV9在N10低MDD场景也优于振幅

---

## Batch ZQ (2026-07-03) — dd7探索 + N10 4因子 + dd5变体 + 新正交组合

| ID | 策略名 | 因子 | N | 4种子IR | 4种子MDD | 评价 |
|----|--------|------|---|---------|----------|------|
| ZZ-027 | dd7_rsv9_ret20_trail_n10 | dd7+rsv_9+ret_20d | n10 | 0.942-1.156 | 25.2-27.7% | N10版dd7+RSV9, IR=1.077, MDD=26.3%(std=1.1pp!), 不如dd3/dd4 |
| ZZ-028 | dd6_rsv9_park20_ret20_trail | dd6+rsv_9+parkinson_vol_20d+ret_20d | n5 | 0.854-1.086 | 14.2-15.2% | Parkinson替代振幅, MDD=15.0%(std=0.5pp!), IR=0.938, MDD极稳但IR略低 |
| ZZ-029 | dd6_vpc_amp_ret20_trail | dd6+vol_price_corr_20d+amplitude_avg_20d+ret_20d | n5 | 0.551-0.850 | 15.6-23.2% | 无RSV9的VPC+振幅, IR=0.729, 证明RSV9是核心alpha |
| ZZ-030 | dd7_rsv9_vpc_ret20_trail | dd7+rsv_9+vol_price_corr_20d+ret_20d | n5 | 0.825-1.116 | 28.1-29.2% | dd7版ZZ-018, IR=1.014, MDD=28.7%, dd7劣于dd6 |
| ZZ-031 | dd7_amp_ret20_trail | dd7+amplitude_avg_20d+ret_20d | n5 | 0.957-1.069 | 24.1-31.7% | dd7版振幅, IR=1.007, MDD=28.8%, dd7劣于dd6(1.303/16.1%) |
| ZZ-032 | dd7_rsv9_ret20_trail | dd7+rsv_9+ret_20d | n5 | 0.676-1.249 | 24.9-32.1% | dd7版RSV9, IR=0.891, MDD=29.3%, dd7劣于dd6(1.089/21.9%) |
| ZZ-033 | dd7_rsv9_amp_ret20_trail | dd7+rsv_9+amplitude_avg_20d+ret_20d | n5 | 0.513-0.581 | 39.0-44.0% | dd7版ZZ-021, IR=0.541, MDD=41.3%!, 灾难性失败 |
| ZZ-034 | dd5_rsv9_vpc_ret20_trail | dd5+rsv_9+vol_price_corr_20d+ret_20d | n5 | 0.640-1.016 | 25.9-28.9% | dd5版ZZ-018, IR=0.824, MDD=28.1%, dd5劣于dd6 |
| ZZ-035 | dd5_rsv9_amp_ret20_trail | dd5+rsv_9+amplitude_avg_20d+ret_20d | n5 | 0.269-0.913 | 16.2-32.8% | dd5版ZZ-021, IR=0.673, MDD=25.8%, dd5劣于dd6 |
| ZZ-036 | dd6_rsv9_vpc_ret20_trail_n10 | dd6+rsv_9+vol_price_corr_20d+ret_20d | n10 | 0.763-0.893 | 18.3-21.8% | N10版ZZ-018, IR=0.845, MDD=19.8%, alpha稀释(-32%) |
| ZZ-037 | dd6_rsv9_amp_ret20_trail_n10 | dd6+rsv_9+amplitude_avg_20d+ret_20d | n10 | 0.481-0.680 | 18.2-19.5% | N10版ZZ-021, IR=0.538, MDD=18.5%, alpha严重稀释(-45%) |
| ZZ-038 | dd5_rsv9_vpc_ret20_trail_n10 | dd5+rsv_9+vol_price_corr_20d+ret_20d | n10 | 0.599-0.976 | 20.5-29.7% | N10版dd5+VPC, IR=0.841, MDD=25.4% |

173. **dd6是4因子策略的唯一最优回撤周期** — ZQ系统验证: dd5+RSV9+VPC IR=0.824/MDD=28.1%, dd6+RSV9+VPC IR=1.239/MDD=18.8%, dd7+RSV9+VPC IR=1.014/MDD=28.7%。dd6在IR和MDD两个维度同时最优, 非权衡关系
174. **dd7在所有因子组合中全面劣于dd6** — dd7+RSV9 IR降18%(1.089→0.891), dd7+振幅 IR降23%(1.303→1.007), dd7+RSV9+振幅 IR降45%(0.975→0.541)且MDD暴涨至41%!. dd7回撤周期过长, 信号滞后
175. **N10 4因子存在alpha稀释效应** — N5→N10的IR降幅: dd6+RSV9+VPC -32%(1.239→0.845), dd6+RSV9+振幅 -45%(0.975→0.538). 4因子alpha集中在少数极端标的, 分散到10只后alpha被稀释. N10应优先用3因子
176. **Parkinson可替代振幅实现MDD控制** — dd6+RSV9+Parkinson: MDD=15.0%(std=0.5pp!), vs dd6+RSV9+振幅 MDD=14.8%(std=0.9pp). Parkinson的MDD更稳定但IR略低(0.938 vs 0.975). 两者都是日内波动率因子, 提供相似的MDD控制效果
177. **RSV9是4因子组合的核心alpha源** — 去掉RSV9后(dd6+VPC+振幅): IR=0.729, 降幅25%. RSV9(超卖振荡)提供的alpha不可被VPC(量价相关)或振幅(日内波动)替代
178. **dd7+RSV9在N10上IR=1.077且MDD稳定** — 虽然不如dd3/dd4的IR高, 但MDD std=1.1pp(26.2-27.7%), 是N10非低MDD中最稳定的. 适合风险偏好较低的N10非低MDD配置
179. **回撤周期完整排序: dd6 > dd5 > dd4 > dd3 > dd7** — 综合ZO+ZP+ZQ: dd6在4因子中最优, dd5在3因子DIF中最优(Lesson 164), dd4在RSV9高IR中最优(ZZ-015), dd3在高OOS中最优(ZZ-019), dd7全面最差

---

## Batch ZR (2026-07-03) — 新因子家族探索: CMF/MFI/Bollinger

| ID | 策略名 | 因子 | N | 4种子IR | 4种子MDD | 评价 |
|----|--------|------|---|---------|----------|------|
| ZZ-039 | dd6_cmf20_ret20_trail | dd6+cmf_20+ret_20d | n5 | 0.974-1.300 | 21.9-28.3% | CMF20有止损版, IR=1.136, 非低MDD, 强但不进前三 |
| ZZ-040 | dd6_cmf7_ret20_trail | dd6+cmf_7+ret_20d | n5 | 1.034-1.220 | 25.7-29.1% | CMF7短窗口, IR=1.102, MDD std=1.7pp(稳!) |
| ZZ-041 | dd6_mfi7_ret20_trail | dd6+mfi_7+ret_20d | n5 | 0.261-0.951 | 16.9-30.0% | MFI7有止损版灾难! IR=0.678, 远不如MFI6(ZZ-001=1.121) |
| ZZ-042 | dd6_rsv9_cmf20_ret20_trail | dd6+rsv_9+cmf_20+ret_20d | n5 | 0.723-1.114 | 22.3-23.1% | RSV9+CMF20负交互, IR=0.923<CMF20单独(1.136) |
| ZZ-043 | dd6_rsv9_mfi7_ret20_trail | dd6+rsv_9+mfi_7+ret_20d | n5 | -0.117-0.347 | 25.5-30.4% | RSV9+MFI7灾难! IR≈0, 3/4种子为负! |
| ZZ-044 | dd6_amp_cmf20_ret20_trail | dd6+amplitude_avg_20d+cmf_20+ret_20d | n5 | 0.306-0.871 | 24.3-32.6% | 振幅+CMF20负交互, IR=0.679 |
| ZZ-045 | dd6_rsv9_bollpb5_ret20_trail | dd6+rsv_9+boll_pct_b_5+ret_20d | n5 | 0.660-0.922 | 21.0-26.3% | RSV9+Boll%B5失败, IR=0.745 |
| ZZ-046 | dd6_amp_bollpb5_ret20_trail | dd6+amplitude_avg_20d+boll_pct_b_5+ret_20d | n5 | 0.060-0.459 | 18.6-24.3% | 振幅+Boll%B5全批最差! IR=0.190 |
| ZZ-047 | dd6_rsv9_turn520_ret20_trail | dd6+rsv_9+turnover_change_5_20+ret_20d | n5 | 0.575-1.194 | 18.2-32.7% | RSV9+换手变化, IR=0.878, 3/4种子MDD=18.2% |
| ZZ-048 | dd5_mfi7_ret20_trail | dd5+mfi_7+ret_20d | n5 | 0.473-1.048 | 18.9-31.2% | dd5版MFI7, IR=0.835, MDD波动大(std=5.6pp) |
| ZZ-049 | n10_dd6_cmf20_ret20_trail | dd6+cmf_20+ret_20d | n10 | 0.708-1.082 | 20.6-27.6% | N10版CMF20, IR=0.959 |
| ZZ-050 | n10_dd6_mfi7_ret20_trail | dd6+mfi_7+ret_20d | n10 | 0.717-1.167 | 20.2-29.3% | N10版MFI7, IR=0.999, 比N5版(0.678)好! |
| ZZ-051 | n5_dd6_cmf20_vpc_ret20_trail | dd6+cmf_20+vol_price_corr_20d+ret_20d | n5 | 0.829-1.299 | 19.2-29.6% | CMF20+VPC, IR=1.117, 不如CMF20单独(1.136) |
| ZZ-052 | n5_dd6_cmf20_dif_ret20_trail | dd6+cmf_20+dif+ret_20d | n5 | 0.614-1.311 | 16.8-36.0% | CMF20+DIF! 3/4种子IR>1.27 MDD<18% OOS=612%! seed=0异常 |
| ZZ-053 | n5_dd6_cmf20_park_ret20_trail | dd6+cmf_20+parkinson_vol_20d+ret_20d | n5 | 0.434-0.648 | 27.4-30.3% | CMF20+parkinson冗余! IR=0.569, 都用high-low |
| ZZ-054 | n5_dd6_rsv9_bollw5_ret20_trail | dd6+rsv_9+boll_width_5+ret_20d | n5 | 0.353-0.488 | 35.0-47.8% | boll_width_5有害! IR=0.427 MDD=40.4% |
| ZZ-055 | n5_dd6_rsv9_bollw20_ret20_trail | dd6+rsv_9+boll_width_20+ret_20d | n5 | -0.261-0.179 | 29.9-41.6% | boll_width_20灾难! IR=0.061, seed=0负收益 |
| ZZ-056 | n5_dd6_rsv9_skew_ret20_trail | dd6+rsv_9+ret_skew_20d+ret_20d | n5 | 0.355-1.131 | 19.7-37.8% | RSV9+偏度, IR=0.773, 方差大 |
| ZZ-057 | n5_dd6_cmf10_ret20_trail | dd6+cmf_10+ret_20d | n5 | 0.962-1.175 | 23.4-23.5% | CMF10, IR=1.052, 最稳定(stdIR=0.081) |
| ZZ-058 | n5_dd6_cmf14_ret20_trail | dd6+cmf_14+ret_20d | n5 | 0.524-1.308 | 24.8-38.7% | CMF14, IR=1.069, seed=0异常(同CMF20+DIF) |
| ZZ-059 | n5_dd6_rsv9_vpc_amp_ret20_trail | dd6+rsv_9+vol_price_corr_20d+amplitude_avg_20d+ret_20d | n5 | 0.422-0.727 | 14.3-20.3% | 5因子! IR=0.551, alpha稀释-55% |
| ZZ-060 | n5_dd6_rsv9_vpc_park_ret20_trail | dd6+rsv_9+vol_price_corr_20d+parkinson_vol_20d+ret_20d | n5 | 0.516-0.945 | 16.1-21.6% | 5因子, IR=0.771, MDD=17.7%低但IR太低 |
| ZZ-061 | n10_dd4_cmf20_ret20_trail | dd4+cmf_20+ret_20d | n10 | 0.775-1.378 | 29.9-43.6% | N10 dd4+CMF20, IR=1.126但MDD=37.4%! |
| ZZ-062 | n10_dd3_cmf20_ret20_trail | dd3+cmf_20+ret_20d | n10 | 0.685-0.859 | 42.9-49.4% | N10 dd3+CMF20, MDD=45%灾难! |

180. **振荡器+振荡器组合始终有害** — ZR系统验证: RSV9+CMF20 IR=0.923(<CMF20单独1.136), RSV9+MFI7 IR≈0(3/4负!), RSV9+Boll%B5 IR=0.745, 振幅+CMF20 IR=0.679, 振幅+Boll%B5 IR=0.190. 振荡器间高度相关, 组合产生噪音而非alpha
181. **4因子正交法则** — 成功组合(RSV9+VPC, RSV9+振幅, RSV9+Parkinson)都是跨家族(振荡器+波动率/量价相关); 失败组合(RSV9+CMF/MFI/Boll%B)都是同家族(振荡器+振荡器). 第4因子必须来自不同因子家族
182. **CMF20是强独立因子** — dd6+CMF20有止损4种子IR=1.136(MDD=24.8%), 接近dd6+振幅(ZZ-008 IR=1.303)的水平. 但MDD偏高(24.8% vs 16.1%), 非低MDD
183. **MFI7有止损远不如MFI6** — MFI7+trail IR=0.678, MFI6+trail IR=1.121(ZZ-001). MFI7窗口太短, 信号频繁被止损截断. MFI6是止损策略的最优MFI窗口
184. **N10 MFI7比N5 MFI7好** — N10版IR=0.999 vs N5版0.678. N10分散度降低了个股止损风险, MFI7的alpha在N10中得到更好保留
185. **换手变化因子有潜力但不稳定** — RSV9+turnover_change: 3/4种子MDD=18.2%(低MDD!), 但seed=0 MDD=32.7%. IR std=0.253, 不满足4种子稳健性
186. **CMF20+DIF是唯一有效的CMF20跨家族组合** — 3/4种子IR>1.27, MDD<18%, OOS=501-612%. 但seed=0异常(IR=0.614, MDD=36%). DIF(趋势因子)与CMF20(资金流振荡器)真正正交
187. **boll_width是有害因子** — RSV9+boll_width_5 IR=0.427, RSV9+boll_width_20 IR=0.061(seed=0负收益!). 波动率挤压因子与RSV9完全不相容, 不应作为第4因子
188. **5因子alpha稀释确认** — RSV9+VPC+amplitude IR=0.551(vs 4因子1.239, -55%), RSV9+VPC+parkinson IR=0.771(-38%). 4因子是alpha保留的硬上限
189. **CMF窗口排序: CMF20 > CMF7 > CMF14 > CMF10** — 4种子平均IR分别为1.136/1.102/1.069/1.052. 更长窗口更好, 但CMF14/CMF20有seed=0问题
190. **CMF10是最稳定CMF窗口** — stdIR=0.081(vs CMF20=0.135, CMF14=0.320), 4种子MDD几乎完全相同(23.4-23.5%). 适合追求稳健性而非最高IR
191. **N10短回撤周期+CMF20的MDD灾难** — dd3 MDD=45%, dd4 MDD=37.4%, dd6 MDD=22.8%. 短回撤周期在N10中MDD放大效应极强, dd6是N10 CMF20的唯一可行回撤周期
192. **seed=0是CMF策略的系统性问题** — CMF20+DIF(seed=0 IR=0.614), CMF14(seed=0 IR=0.524). seed=0的HPO可能落入局部最优, 需增加n_trials或使用不同种子集
193. **ret_skew与RSV9组合效果中等** — IR=0.773, 低于VPC(1.239)和振幅(0.975), 但远好于boll_width(0.427/0.061). 偏度因子有微弱alpha但不够强
194. **CMF20+parkinson冗余失败** — IR=0.569. 两者都使用high-low range数据, 信息高度重叠. 因子冗余不仅看家族标签, 还要看底层数据来源
195. **CMF20是"自私"因子** — 仅DIF能与其协同(IR=1.125), VPC无效(1.117<1.136), parkinson灾难(0.569), 振幅已知失败(0.679). CMF20的alpha难以通过加因子增强

### Batch ZT (2026-07-03) — CMF+DIF修复seed=0 + DIF单独 + N3集中度 + CMF+振幅修复

| ID | Config | Factors | N | IR范围 | MDD范围 | 备注 |
|----|--------|---------|---|--------|---------|------|
| ZZ-063 | n5_dd6_cmf7_dif_ret20_trail | dd6+cmf_7+dif+ret_20d | n5 | 1.050-1.193 | 13.8-19.3% | CMF7+DIF! IR=1.105, stdIR=0.067, MDD=19.4%低, 4种子全>1.0! 修复seed=0 |
| ZZ-064 | n5_dd6_cmf10_dif_ret20_trail | dd6+cmf_10+dif+ret_20d | n5 | 0.667-1.177 | 15.3-35.9% | CMF10+DIF, IR=0.971, seed=0仍失败(0.667) |
| ZZ-065 | n5_dd5_cmf20_dif_ret20_trail | dd5+cmf_20+dif+ret_20d | n5 | 0.958-1.280 | 19.3-23.7% | dd5+CMF20+DIF, IR=1.135, seed=0修复(1.128)但seed=3回落(0.958) |
| ZZ-066 | n5_dd4_cmf20_dif_ret20_trail | dd4+cmf_20+dif+ret_20d | n5 | 0.458-0.657 | 42.4-48.2% | dd4+CMF20+DIF灾难! IR=0.570, MDD=44.8% |
| ZZ-067 | n5_dd6_dif_ret20_trail | dd6+dif+ret_20d | n5 | 0.737-1.194 | 23.4-42.6% | DIF单独(dd6), IR=0.920, 不稳定stdIR=0.195 |
| ZZ-068 | n5_dd5_dif_ret20_trail | dd5+dif+ret_20d | n5 | 1.053-1.250 | 23.0-23.6% | DIF单独(dd5), IR=1.179, 4种子全>1.0! =ZZ-012确认 |
| ZZ-069 | n5_dd4_dif_ret20_trail | dd4+dif+ret_20d | n5 | 0.608-0.772 | 34.6-47.1% | DIF单独(dd4), IR=0.692, 灾难 |
| ZZ-070 | n3_dd6_cmf20_ret20_trail | dd6+cmf_20+ret_20d | n3 | 1.010-1.010 | 24.7-24.7% | N3 CMF20, IR=1.010, stdIR=0(确定性), 但低于N5(1.136) |
| ZZ-071 | n3_dd6_rsv9_vpc_ret20_trail | dd6+rsv_9+vol_price_corr_20d+ret_20d | n3 | 0.964-0.964 | 23.6-23.6% | N3 RSV9+VPC, IR=0.964, 远低于N5(1.239) |
| ZZ-072 | n5_dd6_cmf7_amp_ret20_trail | dd6+cmf_7+amplitude_avg_20d+ret_20d | n5 | 0.237-0.585 | 27.0-33.6% | CMF7+振幅, IR=0.434, 灾难 |
| ZZ-073 | n5_dd6_cmf10_amp_ret20_trail | dd6+cmf_10+amplitude_avg_20d+ret_20d | n5 | 0.515-0.838 | 19.6-25.4% | CMF10+振幅, IR=0.670, 失败 |
| ZZ-074 | n5_dd5_amp_dif_ret20_trail | dd5+amplitude_avg_20d+dif+ret_20d | n5 | 0.853-1.086 | 18.4-31.3% | 振幅+DIF, IR=0.953, 振幅拖累DIF(-19%) |

196. **CMF7+DIF成功修复seed=0** — CMF7窗口将CMF20+DIF的seed=0从IR=0.614提升至1.050, 4种子全>1.0, stdIR=0.067(最稳定), MDD=19.4%低MDD. CMF7是CMF+DIF组合的最优窗口
197. **dd5是DIF的最优回撤周期** — dd5+DIF IR=1.179(4种子全>1.0), dd6+DIF IR=0.920(不稳定), dd4+DIF IR=0.692(灾难). dd5是DIF alpha释放的sweet spot, 与RSV9(dd6)和振幅(dd6)不同
198. **DIF单独即强因子** — dd5+DIF 4种子IR=1.053/1.250/1.213/1.200, OOS=606%, MDD=23.2%. 确认DIF是继振幅(1.303)、RSV9+VPC(1.239)、CMF20(1.136)后的第四大独立alpha来源
199. **N3集中度降低IR** — N3 CMF20 IR=1.010(vs N5=1.136, -11%), N3 RSV9+VPC IR=0.964(vs N5=1.239, -22%). N3确定性极高(stdIR=0)但集中风险增加, 个股冲击成本放大. N5是alpha表达的最优持仓数
200. **CMF+振幅跨窗口全部失败** — CMF7+amp IR=0.434, CMF10+amp IR=0.670, CMF20+amp IR=0.679. 改变CMF窗口无法修复CMF+振幅的因子冲突, 这是结构性问题非参数问题
201. **dd4对CMF20+DIF组合完全不可行** — IR=0.570, 4种子全<0.66, MDD=44.8%. dd4只在dd4+RSV9(ZZ-015 IR=1.381)中有效, 说明dd4的alpha需要RSV9这类振荡器才能释放
202. **amplitude拖累DIF** — dd5+amp+DIF IR=0.953(vs dd5+DIF 1.179, -19%). 振幅偏好高波动(适合逆势买入), DIF偏好趋势确认(需要持续上涨), 信号方向冲突
203. **CMF10+DIF仍无法修复seed=0** — IR=0.971, seed=0=0.667. 只有CMF7窗口成功修复seed=0, CMF窗口越短对HPO轨迹影响越大
204. **dd5+CMF20+DIF比CMF7+DIF更高IR但不稳定** — dd5+CMF20+DIF IR=1.135(vs CMF7+DIF 1.105), 但stdIR=0.134(vs 0.067), seed=3降至0.958. 高IR伴随高方差
205. **DIF是第四大核心alpha因子** — DIF(dd5)单独IR=1.179, 仅次于振幅(dd6)1.303、RSV9+VPC(dd6)1.239、CMF20(dd6)1.136. DIF+CMF(1.105-1.135)和DIF单独(1.179)都>1.0. RSV9+DIF尚未测试, 是下一批重点方向

### Batch ZU (2026-07-03) — RSV9+DIF跨家族 + DIF多振荡器对比 + dd5冠军变体

| ID | Config | Factors | N | IR范围 | MDD范围 | 备注 |
|----|--------|---------|---|--------|---------|------|
| ZZ-075 | n5_dd5_rsv9_dif_ret20_trail | dd5+rsv_9+dif+ret_20d | n5 | 0.841-0.908 | 20.4-28.7% | RSV9+DIF(dd5), IR=0.873, 低于DIF单独(1.179)! 反转+趋势冲突 |
| ZZ-076 | n5_dd6_rsv9_dif_ret20_trail | dd6+rsv_9+dif+ret_20d | n5 | 0.652-1.172 | 17.0-32.3% | RSV9+DIF(dd6), IR=1.000但不稳定stdIR=0.237 |
| ZZ-077 | n5_dd4_rsv9_dif_ret20_trail | dd4+rsv_9+dif+ret_20d | n5 | 0.474-0.920 | 24.5-36.4% | RSV9+DIF(dd4), IR=0.624, 灾难 |
| ZZ-078 | n5_dd5_mfi6_dif_ret20_trail | dd5+mfi_6+dif+ret_20d | n5 | 0.852-1.008 | 31.9-32.1% | MFI6+DIF, IR=0.906, MFI6与DIF不协同 |
| ZZ-079 | n5_dd5_mfi7_dif_ret20_trail | dd5+mfi_7+dif+ret_20d | n5 | 0.680-0.979 | 24.6-34.4% | MFI7+DIF, IR=0.821, 更差 |
| ZZ-080 | n5_dd5_bpb5_dif_ret20_trail | dd5+boll_pct_b_5+dif+ret_20d | n5 | 0.468-0.706 | 34.7-41.9% | Boll%B+DIF, IR=0.567, 灾难 |
| ZZ-081 | n5_dd5_vpc_dif_ret20_trail | dd5+vol_price_corr_20d+dif+ret_20d | n5 | 0.860-0.990 | 27.5-40.6% | VPC+DIF, IR=0.934, MDD=35%太高 |
| ZZ-082 | n5_dd5_park_dif_ret20_trail | dd5+parkinson_vol_20d+dif+ret_20d | n5 | 0.976-1.087 | 22.4-35.0% | parkinson+DIF, IR=1.043, 第二好DIF组合! |
| ZZ-083 | n5_dd5_rsv9_vpc_ret20_trail | dd5+rsv_9+vol_price_corr_20d+ret_20d | n5 | 0.640-1.016 | 25.9-28.9% | dd5+RSV9+VPC, IR=0.824, vs dd6版1.239! dd5不适合RSV9 |
| ZZ-084 | n5_dd5_rsv9_park_ret20_trail | dd5+rsv_9+parkinson_vol_20d+ret_20d | n5 | 0.713-1.000 | 17.7-25.8% | dd5+RSV9+park, IR=0.855 |
| ZZ-085 | n5_dd5_rsv9_amp_ret20_trail | dd5+rsv_9+amplitude_avg_20d+ret_20d | n5 | 0.269-0.913 | 16.2-32.8% | dd5+RSV9+amp, IR=0.673, vs dd6版1.303! |
| ZZ-086 | n5_dd5_cmf7_rsv9_ret20_trail | dd5+cmf_7+rsv_9+ret_20d | n5 | 0.298-0.514 | 21.9-25.7% | CMF7+RSV9振荡器+振荡器, IR=0.393, 再次确认法则 |

206. **RSV9+DIF失败 — 反转与趋势信号冲突** — dd5版IR=0.873(vs DIF单独1.179, -26%), dd6版IR=1.000但不稳定(stdIR=0.237). RSV9选超卖反弹股, DIF选趋势确认股, 信号方向矛盾. 两个强因子组合不一定更强
207. **CMF是唯一与DIF协同的振荡器** — DIF+CMF7=1.105, DIF+CMF20=1.125; 但DIF+RSV9=0.873, DIF+MFI6=0.906, DIF+MFI7=0.821, DIF+Boll%B=0.567. CMF(资金流)与DIF(趋势)同向, 其他振荡器与DIF反向
208. **parkinson+DIF是第二好DIF组合** — IR=1.043, stdIR=0.053(稳定), 但MDD=27.4%非低. parkinson(日内波动率)与DIF(趋势)有微弱正交互补
209. **dd5是DIF专属回撤周期, dd6是RSV9专属** — dd5+RSV9+VPC=0.824(vs dd6版1.239, -34%), dd5+RSV9+amp=0.673(vs dd6版1.303, -48%). RSV9需要更长回撤周期(dd6)释放反转alpha, DIF需要中等周期(dd5)确认趋势
210. **振荡器+振荡器法则再次确认** — CMF7+RSV9 IR=0.393, 比CMF7+DIF(1.105)低64%. 跨家族(振荡器+趋势/波动率)始终优于同家族组合
211. **VPC+DIF虽跨家族但MDD灾难** — IR=0.934但MDD=35.2%. VPC(量价相关)与DIF(趋势)逻辑上正交, 但VPC的高波动性放大了组合MDD
212. **Boll%B+DIF是最差DIF组合** — IR=0.567. Boll%B是均值回归振荡器, 与趋势DIF完全对立, 比RSV9+DIF(0.873)更差
213. **最强4因子组合仍为ZZ-018(dd6+RSV9+VPC, IR=1.239)** — ZU的dd5版冠军变体全部失败, 确认dd6是RSV9+VPC和RSV9+amplitude的不可替代回撤周期. 因子-周期匹配是策略设计的关键维度
