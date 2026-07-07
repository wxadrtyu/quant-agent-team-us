# 数据源花名册（免费、无 token）

> **创建日期：2026-06-28　|　最后更新：2026-06-28**
> 目的：每个字段都备多个**不同提供商**的免费源,任一限流可切换。原则见记忆 [[multi-source-data-discipline]]:同因子只用一致单源、备源仅 failover、带 source 标签、不重复拉。
> 实测环境：akshare 1.18.64。✓=实测可用,✗=实测失败,~=慢/不稳。

## 行情价格(OHLCV)
| 优先级 | 源 | 提供商 | akshare 接口 | 状态 |
|---|---|---|---|---|
| 主 | 东方财富 | 东财 | `stock_zh_a_hist`(qfq/hfq) | ✓ 已用于全市场重建(5368股) |
| 备1 | 新浪 | 新浪 | `stock_zh_a_daily`(qfq/hfq) | ✓ 实测 OK,~3.6s/只 |
| 备2 | 腾讯 | 腾讯 | `stock_zh_a_hist_tx` | ~ 测时超时,待复核 |

## 估值 PE/PB
| 优先级 | 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|---|
| 主(历史) | 百度 | 百度 | `stock_zh_valuation_baidu` | ✓ 有历史,**但~1800次后限流**(降并发可恢复) |
| 备(当前兜底) | 东财 spot | 东财 | `stock_{sh,sz,cy,kc,bj}_a_spot_em` | ✓ 全市场当前 PE/PB(5530股快照),不限流但仅当前 |
| 备(待接) | tushare | tushare | `daily_basic` | ⭐ 需 token,按日批量、最抗限流 |

## ROE / 质量
| 优先级 | 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|---|
| 主(在用) | 同花顺 | 同花顺 | `stock_financial_abstract_ths` | ✓ ~6s/只,年度ROE,**比新浪快、不同源** |
| 备1 | 新浪 | 新浪 | `stock_financial_analysis_indicator` | ✓ 稳但慢(10s/只) |
| 备2 | 东财业绩报表 | 东财 | `stock_yjbb_em` | ✗ 分页极慢+传输中断(东财被拉毛) |
| 备(待接) | tushare | tushare | `fina_indicator` | ⭐ 需 token,批量 |

## 指数基准(A4)
| 优先级 | 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|---|
| **主(已切)** | **新浪** | 新浪 | `stock_zh_index_daily` | ✓ **全基准都通**(300/500/1000/上证50/北证50),~1s,到2026-06-26 |
| 备1 | 中证官方 | 中证 | `stock_zh_index_hist_csindex` | ✓ 可用 |
| 备2 | 东财 | 东财 | `index_zh_a_hist` | ✓ 可用但前期被我们拉时会卡 |

## 行业分类(B2)
| 优先级 | 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|---|
| 主 | 东财行业板块 | 东财 | `stock_board_industry_name_em`+`_cons_em` | 脚本就绪(待跑) |
| 备1 | 同花顺 | 同花顺 | `stock_board_industry_name_ths`/`_summary_ths` | 待测 |
| 备2 | 巨潮 | 巨潮 | `stock_industry_category_cninfo` | ~ 参数待调 |
| 备3 | 申万 | 申万 | `stock_industry_clf_hist_sw` | ✗ SSL 挂(swsresearch.com) |

## ST / 停牌
| 字段 | 源 | 接口 | 状态 |
|---|---|---|---|
| 停牌(历史) | 交易日历缺口推导 | 本地 `build_tradability.py` | ✓ 已入库(7094条) |
| ST(当前) | 东财 spot 名称含"ST" | `stock_zh_a_spot_em` | 脚本就绪;**历史ST无免费源**(记忆已注明) |
| 停牌(当前) | 东财 | `stock_zh_a_stop_em` | ~ 测时超时,待复核 |

## 退市股(B3,幸存者偏差)
| 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|
| 沪退市 | 上交所 | `stock_info_sh_delist` | ✓ 154 条 |
| 深退市 | 深交所 | `stock_info_sz_delist` | ✗ **szse.cn SSL 挂**,需备源 |
| 退市备源 | 东财 | `stock_zh_a_stop_em` / `*_delisted_em` | 待测 |

## 分红除权(验复权用)
| 源 | 提供商 | 接口 | 状态 |
|---|---|---|---|
| 巨潮 | 巨潮 | `stock_dividend_cninfo` | ✓ 送转/除权明细可用 |
| 同花顺 | 同花顺 | `stock_fhps_detail_ths` | 待测 |

## 待办备源缺口
- **深市退市**:szse SSL 挂,需用东财或巨潮替代。
- **历史 ST**:免费无源,只能当前近似(已注明)。
- **tushare**:估值+ROE 的最强批量方案,等用户给 token 即可大幅提速。
