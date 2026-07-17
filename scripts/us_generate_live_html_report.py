from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd


COMMON_CN_NAMES = {
    "AAPL": "苹果",
    "MSFT": "微软",
    "NVDA": "英伟达",
    "AMZN": "亚马逊",
    "GOOGL": "谷歌",
    "GOOG": "谷歌",
    "META": "Meta平台",
    "TSLA": "特斯拉",
    "AVGO": "博通",
    "BRK.B": "伯克希尔哈撒韦",
    "BRK-B": "伯克希尔哈撒韦",
    "LLY": "礼来",
    "JPM": "摩根大通",
    "V": "维萨",
    "MA": "万事达",
    "NFLX": "奈飞",
    "COST": "开市客",
    "HD": "家得宝",
    "PG": "宝洁",
    "UNH": "联合健康",
    "XOM": "埃克森美孚",
    "JNJ": "强生",
    "WMT": "沃尔玛",
    "ORCL": "甲骨文",
    "CRM": "赛富时",
    "AMD": "超威半导体",
    "ADBE": "奥多比",
    "CSCO": "思科",
    "QCOM": "高通",
    "INTC": "英特尔",
    "IBM": "IBM",
    "DELL": "戴尔",
    "AMAT": "应用材料",
    "AMG": "联博资产管理",
    "AMKR": "安靠科技",
    "ALGM": "Allegro微系统",
    "ACN": "埃森哲",
    "APO": "阿波罗全球管理",
    "ARE": "亚历山大房地产",
    "ARM": "安谋控股",
    "ARW": "艾睿电子",
    "ASTS": "AST SpaceMobile",
    "AVB": "AvalonBay社区",
    "AXON": "Axon企业",
    "AYI": "Acuity品牌",
    "BBWI": "Bath & Body Works",
    "BWA": "博格华纳",
    "BWXT": "BWX技术",
    "CAR": "安飞士预算集团",
    "CBSH": "商业银行股份",
    "CHTR": "Charter通信",
    "CCI": "皇冠城堡",
    "CEG": "星座能源",
    "CLF": "克利夫兰克里夫",
    "CNC": "康西哥",
    "CNXC": "Concentrix",
    "COLD": "Americold Realty Trust",
    "CTSH": "高知特",
    "CRCL": "Circle互联网集团",
    "CROX": "卡骆驰",
    "CXT": "Crane NXT",
    "DDOG": "Datadog",
    "DKS": "迪克体育用品",
    "DLR": "数字房地产信托",
    "DOW": "陶氏",
    "DUOL": "多邻国",
    "ENTG": "英特格",
    "EQH": "公平控股",
    "EQIX": "易昆尼克斯",
    "ESS": "埃塞克斯物业信托",
    "ETSY": "Etsy",
    "EVR": "艾维克",
    "FBIN": "Fortune Brands创新",
    "FE": "第一能源",
    "FIVE": "Five Below",
    "FOX": "福克斯",
    "FTNT": "飞塔",
    "GAP": "盖璞",
    "GEV": "通用电气能源",
    "GFS": "格芯",
    "GLW": "康宁",
    "HAYW": "海沃德控股",
    "HON": "霍尼韦尔",
    "HOOD": "罗宾汉市场",
    "HPE": "慧与科技",
    "HPQ": "惠普",
    "HRL": "荷美尔食品",
    "HST": "Host酒店与度假村",
    "HUM": "哈门那",
    "HUBB": "哈贝尔",
    "IBKR": "盈透证券",
    "IRM": "铁山",
    "JEF": "杰富瑞金融集团",
    "KLAC": "科磊",
    "KRC": "基尔罗伊地产",
    "LBRDK": "自由宽带K类",
    "LINE": "Lineage",
    "LNC": "林肯金融",
    "LRCX": "泛林集团",
    "LYB": "利安德巴塞尔",
    "M": "梅西百货",
    "MAR": "万豪国际",
    "MKSI": "MKS仪器",
    "MLI": "穆勒工业",
    "MOH": "Molina医疗",
    "MRNA": "莫德纳",
    "MRVL": "迈威尔科技",
    "MSTR": "微策略",
    "NTRA": "Natera",
    "NUE": "纽柯",
    "NVR": "NVR住宅",
    "NLY": "Annaly资本管理",
    "NWL": "纽威品牌",
    "OC": "欧文斯科宁",
    "OGN": "欧加农",
    "OLN": "奥林公司",
    "ON": "安森美",
    "ONTO": "Onto创新",
    "OXY": "西方石油",
    "PANW": "帕洛阿尔托网络",
    "PFG": "信安金融集团",
    "PH": "派克汉尼汾",
    "PLD": "普洛斯",
    "PTC": "参数技术公司",
    "RAL": "拉尔夫劳伦",
    "REXR": "Rexford工业地产",
    "REYN": "雷诺消费品",
    "SNX": "新聚思",
    "SN": "SharkNinja",
    "SMCI": "超微电脑",
    "SEB": "海滨公司",
    "TECH": "Bio-Techne",
    "TLN": "泰伦能源",
    "TFC": "Truist金融",
    "TJX": "TJX公司",
    "TMUS": "美国T-Mobile",
    "VIRT": "Virtu金融",
    "VZ": "威瑞森",
    "WPC": "W.P.凯瑞",
    "WWD": "伍德沃德",
    "MU": "美光科技",
    "UBER": "优步",
    "UAL": "联合大陆航空",
    "PVH": "PVH集团",
    "STWD": "喜达屋地产信托",
    "ZBH": "捷迈邦美",
    "ABNB": "爱彼迎",
    "DIS": "迪士尼",
    "NKE": "耐克",
    "SBUX": "星巴克",
    "MCD": "麦当劳",
    "KO": "可口可乐",
    "PEP": "百事",
    "PFE": "辉瑞",
    "MRK": "默沙东",
    "TMO": "赛默飞世尔",
    "LIN": "林德",
    "GE": "通用电气",
    "GM": "通用汽车",
    "F": "福特汽车",
    "BA": "波音",
    "CAT": "卡特彼勒",
    "GS": "高盛",
    "MS": "摩根士丹利",
    "BAC": "美国银行",
    "C": "花旗",
    "AA": "美国铝业",
    "ALB": "雅保",
    "CME": "芝商所集团",
    "FIX": "Comfort Systems USA",
    "HUN": "亨斯迈",
    "STLD": "Steel Dynamics",
    "WFRD": "Weatherford International",
}


def normalize_symbol(symbol: str) -> str:
    return str(symbol).upper().replace("-", ".").strip()


def load_name_map(raw_dir: Path) -> dict[str, str]:
    meta_path = raw_dir / "us_stock_meta.csv"
    names: dict[str, str] = {}
    if meta_path.exists():
        meta = pd.read_csv(meta_path)
        for row in meta.itertuples(index=False):
            symbol = normalize_symbol(getattr(row, "symbol"))
            raw_name = str(getattr(row, "name", "")).strip()
            names[symbol] = COMMON_CN_NAMES.get(symbol, raw_name or symbol)
    for symbol, name in COMMON_CN_NAMES.items():
        names[normalize_symbol(symbol)] = name
    return names


def display_symbol(symbol: str, name_map: dict[str, str]) -> str:
    raw = str(symbol).upper().strip()
    name = name_map.get(normalize_symbol(raw), raw)
    return f"{raw}（{name}）"


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.2f}%"


def num(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.3f}"


def load_prices(raw_dir: Path, entry_date: str, mtm_date: str) -> pd.DataFrame:
    prices = pd.read_parquet(raw_dir / "us_market_daily.parquet")
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.strftime("%Y-%m-%d")
    entry = prices.loc[prices["trade_date"].eq(entry_date), ["symbol", "open"]].rename(columns={"open": "buy_price"})
    mtm = prices.loc[prices["trade_date"].eq(mtm_date), ["symbol", "close"]].rename(columns={"close": "mtm_price"})
    out = entry.merge(mtm, on="symbol", how="inner")
    out["stock_return"] = out["mtm_price"] / out["buy_price"] - 1.0 - 0.002
    return out


def build_payload(db_path: Path, raw_dir: Path) -> dict:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        strategies = con.execute("select * from us_live_monitoring_strategies_current").fetchdf()
        holdings = con.execute("select * from us_live_monitoring_holdings_current").fetchdf()
    finally:
        con.close()

    if strategies.empty:
        raise RuntimeError("us_live_monitoring_strategies_current is empty")
    if holdings.empty:
        raise RuntimeError("us_live_monitoring_holdings_current is empty")

    # Current table layout:
    # 0 current_run_id, 1 monitor_key, 2 run_id, 3 策略编号, 4 candidate_id, ...
    entry_date = str(strategies["入场日期"].dropna().iloc[0])
    signal_date = str(strategies["实盘起点"].dropna().iloc[0])
    mtm_date = str(strategies["估值日期"].dropna().iloc[0])
    name_map = load_name_map(raw_dir)
    price_frame = load_prices(raw_dir, entry_date, mtm_date)
    holdings = holdings.merge(price_frame, left_on="股票代码", right_on="symbol", how="left")
    holdings["stock_return"] = holdings["stock_return"].fillna(0.0)
    holdings["contribution"] = holdings["目标权重"] * holdings["stock_return"]

    results = []
    for row in strategies.itertuples(index=False):
        monitor_key = getattr(row, "monitor_key")
        sid = getattr(row, "策略编号")
        candidate_id = getattr(row, "candidate_id")
        sub = holdings.loc[holdings["monitor_key"].eq(monitor_key)].copy()
        stocks = []
        for h in sub.sort_values("排名").itertuples(index=False):
            buy = None if pd.isna(getattr(h, "buy_price")) else float(getattr(h, "buy_price"))
            mtm = None if pd.isna(getattr(h, "mtm_price")) else float(getattr(h, "mtm_price"))
            stocks.append(
                {
                    "code": getattr(h, "股票代码"),
                    "name": name_map.get(normalize_symbol(getattr(h, "股票代码")), getattr(h, "股票代码")),
                    "display": display_symbol(getattr(h, "股票代码"), name_map),
                    "rank": int(getattr(h, "排名")),
                    "weight": float(getattr(h, "目标权重")),
                    "buy_price": buy,
                    "mtm_price": mtm,
                    "return": float(getattr(h, "stock_return")),
                    "contribution": float(getattr(h, "contribution")),
                    "entry_date": entry_date,
                    "mtm_date": mtm_date,
                }
            )
        results.append(
            {
                "monitor_key": monitor_key,
                "sid": sid,
                "candidate_id": candidate_id,
                "category": getattr(row, "策略类型"),
                "factors": getattr(row, "主要区分因子"),
                "n": int(getattr(row, "持仓数量")),
                "rebalance": getattr(row, "调仓周期"),
                "information_ratio": float(getattr(row, "信息比率")),
                "avg_information_ratio": float(getattr(row, "年度平均信息比率")),
                "rolling_excess": float(getattr(row, "样本外滚动验证超基准收益")),
                "max_drawdown": float(getattr(row, "最大回撤")),
                "win_excess": float(getattr(row, "超基准胜率")),
                "random_status": getattr(row, "随机检验状态"),
                "deflated_z": float(getattr(row, "去偏标准分")),
                "live_return": float(getattr(row, "实盘收益")),
                "benchmark_return": float(getattr(row, "实盘基准收益")),
                "live_excess": float(getattr(row, "实盘超基准收益")),
                "monitor_status": getattr(row, "监控状态"),
                "admission_date": str(getattr(row, "入库日期", "")),
                "days_in_pool": int(getattr(row, "入库天数", 0)),
                "is_outperforming": bool(getattr(row, "当前是否跑赢基准", float(getattr(row, "实盘超基准收益")) > 0)),
                "post_admission_observations": int(getattr(row, "入库后可用估值次数", 1)),
                "persistent_outperformer": bool(getattr(row, "入库至今持续跑赢", float(getattr(row, "实盘超基准收益")) > 0)),
                "diagnosis": str(getattr(row, "当前诊断", "")),
                "stocks": stocks,
                "n_stocks": len(stocks),
            }
        )

    return {
        "title": "美股正式监控实盘报告",
        "signal_date": signal_date,
        "entry_date": entry_date,
        "mtm_date": mtm_date,
        "benchmark_return": float(strategies["实盘基准收益"].dropna().iloc[0]),
        "universe_status": "动态流动性降偏，尚非完整历史时点成分",
        "results": results,
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股正式监控实盘报告</title>
<style>
:root {
  --bg:#0f172a; --panel:#172033; --card:#1e293b; --card2:#263449; --border:#334155;
  --text:#e5edf7; --muted:#94a3b8; --green:#22c55e; --red:#ef4444; --blue:#3b82f6;
  --orange:#f59e0b; --purple:#a855f7; --cyan:#06b6d4;
}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
.container{max-width:1680px;margin:0 auto;padding:22px}
.header{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid var(--border);border-radius:10px;padding:24px 28px;margin-bottom:14px}
.header h1{font-size:24px;margin:0 0 10px}.meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:13px}
.banner{border:1px solid rgba(245,158,11,.35);background:rgba(245,158,11,.09);color:#f8d99a;border-radius:8px;padding:12px 16px;margin-bottom:14px}
.cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:14px 0 18px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:15px;text-align:center}.card .label{color:var(--muted);font-size:12px}.card .value{font-size:22px;font-weight:700}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.tab{border:1px solid var(--border);background:var(--card);color:var(--muted);border-radius:8px;padding:9px 14px;cursor:pointer}.tab.active{color:white;background:#2563eb;border-color:#60a5fa}
.content{display:none}.content.active{display:block}.section{background:var(--panel);border:1px solid var(--border);border-radius:8px;margin-bottom:14px;overflow:hidden}.section h2{margin:0;padding:12px 16px;background:var(--card);font-size:15px}
table{width:100%;border-collapse:collapse}th,td{padding:9px 10px;border-bottom:1px solid rgba(51,65,85,.75);text-align:left;white-space:nowrap}th{color:#cbd5e1;background:#202c3f;font-weight:600;font-size:12px}td{font-variant-numeric:tabular-nums}tr:hover td{background:rgba(148,163,184,.06)}
.pos{color:var(--green);font-weight:700}.neg{color:var(--red);font-weight:700}.muted{color:var(--muted)}.pill{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:2px 8px;background:rgba(148,163,184,.08)}
.bar{display:inline-block;width:76px;height:8px;background:#263449;border-radius:999px;overflow:hidden;margin-right:6px;vertical-align:middle}.fill{display:block;height:8px}.fill.pos{background:var(--green)}.fill.neg{background:var(--red)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.strategy-block{border-top:1px solid var(--border)}.strategy-head{display:flex;justify-content:space-between;gap:12px;padding:12px 16px;background:rgba(15,23,42,.45);font-weight:700}
@media(max-width:1100px){.cards{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}.container{padding:12px}table{font-size:12px}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>美股正式监控实盘报告</h1>
    <div class="meta">
      <span>信号日：<b id="signal-date"></b></span>
      <span>入场日：<b id="entry-date"></b></span>
      <span>估值日：<b id="mtm-date"></b></span>
      <span>基准：同一动态流动性股票池等权收益</span>
    </div>
  </div>
  <div class="banner"><b>风险说明：</b>当前数据池为动态流动性降偏版本，尚非完整历史时点成分和退市覆盖。报告用于监控和研究复盘，不代表收益保证。</div>
  <div class="cards" id="cards"></div>
  <div class="tabs" id="tabs"></div>
  <div id="contents"></div>
</div>
<script type="application/json" id="json-data">__JSON_DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('json-data').textContent);
const R = DATA.results.map(x => ({...x, pnl_pct:x.live_return*100, excess_pct:x.live_excess*100}));
const fmtPct = v => (v == null || !isFinite(v)) ? '-' : (v>=0?'+':'') + (v*100).toFixed(2) + '%';
const fmtPctRaw = v => (v == null || !isFinite(v)) ? '-' : (v>=0?'+':'') + v.toFixed(2) + '%';
const fmtNum = v => (v == null || !isFinite(v)) ? '-' : Number(v).toFixed(3);
const cls = v => v >= 0 ? 'pos' : 'neg';
function bar(v){ const x=Math.min(100, Math.abs(v)*18); return `<span class="bar"><span class="fill ${cls(v)}" style="width:${x}%"></span></span>`; }
function groups(){
  const tabs = [
    {id:'ALL', label:'全策略', rows:R},
    {id:'PERSIST', label:'入库至今持续跑赢', rows:R.filter(r=>r.persistent_outperformer)},
    {id:'WINNOW', label:'当前跑赢基准', rows:R.filter(r=>r.live_excess>0)},
    {id:'DIAG', label:'跑输诊断', rows:R.filter(r=>r.live_excess<=0)}
  ];
  [...new Set(R.map(r=>'持仓'+r.n))].sort((a,b)=>Number(a.replace('持仓',''))-Number(b.replace('持仓',''))).forEach(label=>{
    tabs.push({id:label, label, rows:R.filter(r=>'持仓'+r.n===label)});
  });
  [...new Set(R.map(r=>r.category))].forEach(label=>tabs.push({id:label, label, rows:R.filter(r=>r.category===label)}));
  return tabs;
}
function holdingGroups(rows){
  return [...new Set(rows.map(r=>Number(r.n)))]
    .sort((a,b)=>a-b)
    .map(n=>({n, rows:rows.filter(r=>Number(r.n)===n)}));
}
function uniqueStocks(rows){
  const m = {};
  rows.forEach(r => r.stocks.forEach(s => {
    if(!m[s.code]) m[s.code] = {code:s.code, display:s.display || s.code, strategies:[], ret:s.return||0, weight:0};
    m[s.code].strategies.push(r.monitor_key);
    m[s.code].weight += s.weight || 0;
  }));
  return Object.values(m).sort((a,b)=>b.strategies.length-a.strategies.length || b.ret-a.ret);
}
function categorySummary(rows){
  const m = {};
  rows.forEach(r => { if(!m[r.category]) m[r.category]=[]; m[r.category].push(r); });
  return Object.entries(m).map(([k,v])=>({category:k, count:v.length, avg:v.reduce((a,r)=>a+r.live_return,0)/v.length, excess:v.reduce((a,r)=>a+r.live_excess,0)/v.length}))
    .sort((a,b)=>b.count-a.count || b.excess-a.excess);
}
function renderCards(rows){
  const avg = rows.reduce((a,r)=>a+r.live_return,0)/rows.length;
  const excess = rows.reduce((a,r)=>a+r.live_excess,0)/rows.length;
  const beat = rows.filter(r=>r.live_excess>0).length;
  const persist = rows.filter(r=>r.persistent_outperformer).length;
  const stocks = uniqueStocks(rows).length;
  return `
    <div class="card"><div class="label">策略数</div><div class="value">${rows.length}</div></div>
    <div class="card"><div class="label">唯一股票</div><div class="value">${stocks}</div></div>
    <div class="card"><div class="label">平均实盘收益</div><div class="value ${cls(avg)}">${fmtPct(avg)}</div></div>
    <div class="card"><div class="label">平均超基准收益</div><div class="value ${cls(excess)}">${fmtPct(excess)}</div></div>
    <div class="card"><div class="label">跑赢策略数</div><div class="value">${beat}</div></div>
    <div class="card"><div class="label">持续跑赢策略数</div><div class="value">${persist}</div></div>`;
}
function weakestStock(r){
  if(!r.stocks || !r.stocks.length) return null;
  return [...r.stocks].sort((a,b)=>(a.contribution||0)-(b.contribution||0))[0];
}
function diagnosisReason(r){
  const weak = weakestStock(r);
  const weakText = weak ? `；最大拖累：${weak.display || weak.code}，贡献 ${fmtPct(weak.contribution)}` : '';
  if(r.live_excess > 0) return '当前仍跑赢基准，继续监控';
  if(r.live_return > 0) return `绝对收益为正，但弱于同池等权基准，说明选股相对强度不足${weakText}`;
  if(r.n <= 7) return `集中持仓下个股拖累更明显，需观察是否为短期噪声${weakText}`;
  if(r.information_ratio < 1.2) return `历史信息比率偏低，当前跑输可能暴露稳定性不足${weakText}`;
  return `当前组合相对基准回撤，保留样本继续归因，不从监控池删除${weakText}`;
}
function strategyTable(rows){
  const sorted=[...rows].sort((a,b)=>b.live_excess-a.live_excess);
  return `<div class="section"><h2>策略盈亏总览</h2><table><thead><tr>
    <th>#</th><th>监控编号</th><th>策略编号</th><th>类型</th><th>持仓</th><th>调仓</th><th>入库日期</th><th>入库天数</th><th>实盘收益</th><th>超基准收益</th><th>信息比率</th><th>样本外超基准收益</th><th>最大回撤</th><th>持续状态</th><th>状态</th>
  </tr></thead><tbody>` + sorted.map((r,i)=>`<tr>
    <td>${i+1}</td><td>${r.monitor_key}</td><td>${r.sid}</td><td>${r.category}</td><td>${r.n}</td><td>${r.rebalance}</td><td>${r.admission_date || '-'}</td><td>${r.days_in_pool}</td>
    <td class="${cls(r.live_return)}">${bar(r.pnl_pct)}${fmtPct(r.live_return)}</td>
    <td class="${cls(r.live_excess)}">${fmtPct(r.live_excess)}</td><td>${fmtNum(r.information_ratio)}</td>
    <td>${fmtPct(r.rolling_excess)}</td><td>${fmtPct(r.max_drawdown)}</td><td><span class="pill">${r.persistent_outperformer ? '入库至今持续跑赢' : '未持续跑赢'}</span></td><td><span class="pill">${r.monitor_status}</span></td>
  </tr>`).join('') + `</tbody></table></div>`;
}
function diagnosisTable(rows){
  const sorted=[...rows].sort((a,b)=>a.live_excess-b.live_excess);
  return `<div class="section"><h2>跑输基准策略诊断（保留监控，不删除样本）</h2><table><thead><tr>
    <th>#</th><th>监控编号</th><th>类型</th><th>持仓</th><th>入库多久</th><th>实盘收益</th><th>基准收益</th><th>超基准收益</th><th>诊断</th>
  </tr></thead><tbody>` + sorted.map((r,i)=>`<tr>
    <td>${i+1}</td><td>${r.monitor_key}</td><td>${r.category}</td><td>${r.n}</td><td>${r.days_in_pool}天</td>
    <td class="${cls(r.live_return)}">${fmtPct(r.live_return)}</td><td class="${cls(r.benchmark_return)}">${fmtPct(r.benchmark_return)}</td><td class="${cls(r.live_excess)}">${fmtPct(r.live_excess)}</td><td>${diagnosisReason(r)}</td>
  </tr>`).join('') + `</tbody></table></div>`;
}
function stockTable(rows){
  const stocks=uniqueStocks(rows);
  return `<div class="section"><h2>唯一股票汇总（按出现策略数排序）</h2><table><thead><tr><th>#</th><th>股票代码</th><th>实盘收益</th><th>出现策略数</th><th>目标权重合计</th><th>出现在</th></tr></thead><tbody>` +
    stocks.map((s,i)=>`<tr><td>${i+1}</td><td>${s.display}</td><td class="${cls(s.ret)}">${fmtPct(s.ret)}</td><td>${s.strategies.length}</td><td>${(s.weight*100).toFixed(1)}%</td><td class="muted">${s.strategies.join(', ')}</td></tr>`).join('') +
    `</tbody></table></div>`;
}
function categoryTable(rows){
  const cats=categorySummary(rows);
  return `<div class="section"><h2>策略类型汇总</h2><table><thead><tr><th>策略类型</th><th>策略数</th><th>平均实盘收益</th><th>平均超基准收益</th></tr></thead><tbody>` +
    cats.map(c=>`<tr><td>${c.category}</td><td>${c.count}</td><td class="${cls(c.avg)}">${fmtPct(c.avg)}</td><td class="${cls(c.excess)}">${fmtPct(c.excess)}</td></tr>`).join('') +
    `</tbody></table></div>`;
}
function holdings(rows){
  const sorted=[...rows].sort((a,b)=>a.monitor_key.localeCompare(b.monitor_key));
  return `<div class="section"><h2>策略持仓明细</h2>` + sorted.map(r=>`<div class="strategy-block"><div class="strategy-head"><span>${r.monitor_key} / ${r.sid} / ${r.category}</span><span class="${cls(r.live_excess)}">超基准 ${fmtPct(r.live_excess)}</span></div>
    <table><thead><tr><th>排名</th><th>股票代码</th><th>目标权重</th><th>买入价</th><th>估值价</th><th>个股收益</th><th>收益贡献</th></tr></thead><tbody>` +
    r.stocks.map(s=>`<tr><td>${s.rank}</td><td>${s.display || s.code}</td><td>${(s.weight*100).toFixed(1)}%</td><td>${s.buy_price == null ? '-' : s.buy_price.toFixed(2)}</td><td>${s.mtm_price == null ? '-' : s.mtm_price.toFixed(2)}</td><td class="${cls(s.return)}">${fmtPct(s.return)}</td><td class="${cls(s.contribution)}">${fmtPct(s.contribution)}</td></tr>`).join('') +
    `</tbody></table></div>`).join('') + `</div>`;
}
function renderTab(id, rows){
  if(id === 'ALL'){
    return holdingGroups(rows).map(g => `
      <div class="section"><h2>${g.n} 只持仓实盘策略（${g.rows.length} 个）</h2></div>
      <div class="cards">${renderCards(g.rows)}</div>
      ${strategyTable(g.rows)}
      <div class="grid2">${categoryTable(g.rows)}${stockTable(g.rows)}</div>
      ${holdings(g.rows)}
    `).join('');
  }
  if(id === 'DIAG'){
    return `<div class="cards">${renderCards(rows)}</div>${diagnosisTable(rows)}${strategyTable(rows)}<div class="grid2">${categoryTable(rows)}${stockTable(rows)}</div>${holdings(rows)}`;
  }
  return `<div class="cards">${renderCards(rows)}</div>${strategyTable(rows)}<div class="grid2">${categoryTable(rows)}${stockTable(rows)}</div>${holdings(rows)}`;
}
document.getElementById('signal-date').textContent = DATA.signal_date;
document.getElementById('entry-date').textContent = DATA.entry_date;
document.getElementById('mtm-date').textContent = DATA.mtm_date;
document.getElementById('cards').innerHTML = renderCards(R);
const tabData=groups();
document.getElementById('tabs').innerHTML = tabData.map((t,i)=>`<button class="tab ${i===0?'active':''}" onclick="show('${t.id}')">${t.label} (${t.rows.length})</button>`).join('');
document.getElementById('contents').innerHTML = tabData.map((t,i)=>`<div class="content ${i===0?'active':''}" id="tab-${t.id}">${renderTab(t.id,t.rows)}</div>`).join('');
function show(id){ document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active')); document.querySelectorAll('.content').forEach(c=>c.classList.remove('active')); event.target.classList.add('active'); document.getElementById('tab-'+id).classList.add('active'); }
</script>
</body>
</html>
"""


def write_outputs(payload: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{payload['signal_date'][5:].replace('-', '')}_{payload['mtm_date'][5:].replace('-', '')}"
    json_path = out_dir / f"us_simulation_formal_monitoring_{suffix}.json"
    html_path = out_dir / f"us_simulation_formal_monitoring_detail_{suffix}.html"
    simple_path = out_dir / f"us_simulation_formal_monitoring_simple_{suffix}.html"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    json_path.write_text(json_text, encoding="utf-8")
    html = HTML_TEMPLATE.replace("__JSON_DATA__", json_text.replace("</", "<\\/"))
    html_path.write_text(html, encoding="utf-8")
    simple = html.replace("策略持仓明细", "策略持仓明细").replace("const tabData=groups();", "const tabData=[groups()[0]];")
    simple_path.write_text(simple, encoding="utf-8")
    return {"json": str(json_path), "detail_html": str(html_path), "simple_html": str(simple_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=r"E:\quant-agent-team-us\research\us_strategy_research.duckdb")
    parser.add_argument("--raw-dir", default=r"E:\quant-agent-team-us\data\us\raw\2026-07-16-intraday-chart")
    parser.add_argument("--out-dir", default=r"G:\quant-agent-team-us\reports\us\live\current")
    args = parser.parse_args()
    payload = build_payload(Path(args.db), Path(args.raw_dir))
    outputs = write_outputs(payload, Path(args.out_dir))
    print(json.dumps({"strategies": len(payload["results"]), **outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
