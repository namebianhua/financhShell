import akshare as ak
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# ====================== 核心配置 ======================
DATA_FILE = "soros_final.json"
BACKTEST_DAYS = 252
CASH = 300000
MAX_POSITION = 40
STOP_LOSS = 0.08
INDUSTRY_BLACKLIST = ["综合", "非银金融"]

# ====================== 数据存储 ======================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"daily": [], "weekly": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====================== 1. 获取全行业 + 50行业龙头（修复akshare接口） ======================
def get_all_industries():
    """获取所有非黑名单行业"""
    try:
        # 适配新版akshare行业接口
        ind = ak.stock_info_industry()
        # 兼容不同列名
        if "行业" in ind.columns:
            ind = ind[~ind["行业"].isin(INDUSTRY_BLACKLIST)]
            return ind["行业"].dropna().unique().tolist()
        elif "industry" in ind.columns:
            ind = ind[~ind["industry"].isin(INDUSTRY_BLACKLIST)]
            return ind["industry"].dropna().unique().tolist()
    except Exception as e:
        print(f"⚠️ 获取行业列表失败：{e}")
        # 兜底行业列表
        return ["银行", "证券", "保险", "半导体", "医药生物", "新能源", "消费", "家电", "汽车", "化工"]

def get_50_industry_leaders():
    """筛选50个行业龙头（替换废弃的市值接口）"""
    print("🔍 正在筛选 50 个行业龙头...")
    try:
        # 1. 获取A股基础列表（过滤科创/北交所）
        df = ak.stock_info_a_code_name()
        df.columns = ["code", "name"] if "代码" not in df.columns else ["代码", "名称"]
        df = df.rename(columns={"代码": "code", "名称": "name"})
        df = df[~df["code"].str.startswith(("688", "8", "4"))]  # 过滤科创/北交所/老三板

        # 2. 新版市值获取接口（替代stock_fund_flow_market_cap）
        def get_market_cap(code):
            """获取个股总市值（处理单位转换）"""
            try:
                fin_df = ak.stock_individual_info_em(symbol=code)
                # 适配不同列名
                if "item" in fin_df.columns and "value" in fin_df.columns:
                    cap_str = fin_df[fin_df["item"] == "总市值"]["value"].iloc[0]
                elif "指标" in fin_df.columns and "值" in fin_df.columns:
                    cap_str = fin_df[fin_df["指标"] == "总市值"]["值"].iloc[0]
                else:
                    return 0
                
                # 单位转换（亿/万）
                cap_str = str(cap_str).replace(",", "").replace(" ", "")
                if "亿" in cap_str:
                    return float(cap_str.replace("亿", "")) * 100000000
                elif "万" in cap_str:
                    return float(cap_str.replace("万", "")) * 10000
                else:
                    return float(cap_str) if cap_str.replace(".", "").isdigit() else 0
            except:
                return 0

        # 3. 批量获取市值（加延迟避免风控）
        import time
        df["总市值"] = 0.0
        for idx, row in df.iterrows():
            if idx % 50 == 0:
                time.sleep(0.2)  # 每50只暂停0.2秒
            df.loc[idx, "总市值"] = get_market_cap(row["code"])

        # 4. 按市值排序取前300
        df = df[df["总市值"] > 0].sort_values("总市值", ascending=False).head(300)
        if df.empty:
            print("⚠️ 市值数据获取失败，按代码兜底选股")
            df = df.head(300)

        # 5. 关联行业信息
        ind = ak.stock_info_industry()
        ind = ind.rename(columns={"代码": "code", "行业": "industry"})
        df = df.merge(ind[["code", "industry"]], on="code", how="left").dropna(subset=["industry"])

        # 6. 按行业选龙头（每个行业取市值最高1只）
        leaders = []
        for industry in df["industry"].unique()[:50]:
            sub = df[df["industry"] == industry].head(1)
            if not sub.empty:
                leaders.append(sub.iloc[0]["code"])

        # 兜底：不足50只补充
        if len(leaders) < 50:
            supplement = df[~df["code"].isin(leaders)]["code"].head(50 - len(leaders)).tolist()
            leaders += supplement

        return leaders[:50]
    except Exception as e:
        print(f"❌ 筛选龙头失败：{e}")
        # 兜底龙头列表（常用蓝筹）
        return ["600519", "000858", "601318", "600036", "000333", "601689", "600030", "002594", "300750", "601899",
                "600887", "002415", "000568", "601012", "600309", "002714", "601766", "600016", "601857", "600900",
                "000001", "601166", "600276", "000651", "002230", "601601", "600048", "000725", "601398", "600690",
                "002352", "601989", "600585", "000100", "600104", "000063", "600893", "601288", "600703", "002075",
                "600600", "000983", "600436", "002142", "600340", "000768", "601111", "000895", "600028", "601939"]

# ====================== 2. 行业轮动判断（强/弱行业自动识别） ======================
def get_industry_strength(industry, days=20):
    """计算行业强度（收益率求和）"""
    try:
        # 适配新版行业指数接口
        ind_df = ak.stock_industry_sw_index_hist(symbol=industry, period="daily")
        if ind_df.empty:
            ind_df = ak.stock_industry_index_hist(symbol=industry, period="daily")
        
        ind_df["date"] = pd.to_datetime(ind_df["日期"])
        ind_df = ind_df.tail(days)
        return ind_df["收盘"].pct_change().sum()
    except Exception as e:
        print(f"⚠️ 行业{industry}强度计算失败：{e}")
        return -999

def get_strong_industries(top=10):
    """获取强势行业（前N个）"""
    industries = get_all_industries()
    score = {i: get_industry_strength(i) for i in industries}
    sorted_ind = sorted(score.items(), key=lambda x: x[1], reverse=True)
    return [i for i, s in sorted_ind[:top] if s > -999]

# ====================== 3. 基础数据获取（保留核心，移除多因子） ======================
def get_price(code, days=60):
    """获取个股价格数据"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, 
            period="daily", 
            adjust="qfq",
            start_date=(datetime.now() - timedelta(days=days+10)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d")
        )
        df["date"] = pd.to_datetime(df["日期"])
        return df.tail(days).reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ 获取{code}价格失败：{e}")
        return pd.DataFrame()

def get_index(days=60):
    """获取沪深300指数数据"""
    try:
        df = ak.index_zh_a_hist(symbol="000300", period="daily")
        df["date"] = pd.to_datetime(df["日期"])
        # 修复fillna（兼容pandas2.0+）
        df = df.ffill().bfill()
        return df.tail(days).reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ 获取沪深300失败：{e}")
        return pd.DataFrame()

# ====================== 4. 最终选股：仅保留龙头 + 强行业（移除多因子打分） ======================
def select_final_stocks(top=20):
    """选股逻辑：强行业内的龙头股"""
    try:
        leaders = get_50_industry_leaders()
        strong_ind = get_strong_industries(15)
        ind_df = ak.stock_info_industry().rename(columns={"代码":"code", "行业":"industry"})
        
        # 筛选强行业内的龙头
        strong_leaders = []
        for code in leaders:
            if code in ind_df["code"].tolist():
                industry = ind_df[ind_df["code"]==code]["industry"].iloc[0]
                if industry in strong_ind:
                    strong_leaders.append(code)
        
        # 兜底：不足20只补充龙头
        if len(strong_leaders) < top:
            supplement = [c for c in leaders if c not in strong_leaders][:top - len(strong_leaders)]
            strong_leaders += supplement
        
        return strong_leaders[:top]
    except Exception as e:
        print(f"❌ 选股失败：{e}")
        # 兜底标的
        return ["600519", "000858", "601318", "600036", "000333", "601689", "600030", "002594", "300750", "601899",
                "600887", "002415", "000568", "601012", "600309", "002714", "601766", "600016", "601857", "600900"]

# ====================== 5. 仓位与风控 ======================
def get_target_position():
    """根据指数趋势判断目标仓位"""
    idx = get_index(30)
    if idx.empty:
        return 15  # 数据失败时默认仓位
    trend = idx["涨跌幅"].tail(15).sum() / 100  # 转换为比例（原代码可能单位错误）
    if trend < -0.08:
        return 0
    elif trend < 0:
        return 15
    elif trend < 0.08:
        return 40
    else:
        return 10

def is_stop_loss(code, cost):
    """判断是否止损"""
    df = get_price(code, 5)
    if len(df) < 1 or cost <= 0:
        return False
    return df.iloc[-1]["收盘"] / cost - 1 < -STOP_LOSS

# ====================== 6. 完整回测框架（移除多因子相关） ======================
def backtest():
    print("\n📊 启动【行业轮动+龙头选股】回测（一年）")
    codes = get_50_industry_leaders()
    cash = CASH
    positions = {c:0 for c in codes}
    cost = {c:0 for c in codes}
    history = []
    dates = get_index(BACKTEST_DAYS)["date"].tolist()

    if not dates:
        print("❌ 回测失败：无指数数据")
        return pd.DataFrame()

    for idx_date in dates:
        target_pct = get_target_position()
        target_value = cash * target_pct / 100
        selected = select_final_stocks(20)

        # 止损
        for c in codes:
            if positions[c] > 0 and is_stop_loss(c, cost[c]):
                p = get_price(c,1).iloc[-1]["收盘"] if not get_price(c,1).empty else 0
                if p > 0:
                    cash += positions[c] * p
                    positions[c] = 0

        # 开仓
        if target_pct > 0 and len(selected) > 0:
            per = target_value / len(selected) if len(selected) > 0 else 0
            for c in selected:
                df = get_price(c,3)
                if len(df) < 1: continue
                p = df.iloc[-1]["收盘"]
                buy_shares = int(per / p / 100) * 100  # 整百股买入
                if buy_shares > 0 and cash >= buy_shares * p:
                    positions[c] = buy_shares
                    cost[c] = p
                    cash -= buy_shares * p

        # 计算净值
        net = cash
        for c, shares in positions.items():
            if shares > 0:
                df = get_price(c,1)
                if len(df) > 0:
                    net += shares * df.iloc[-1]["收盘"]

        history.append({
            "date": str(idx_date.date()),
            "net": net,
            "cash": cash,
            "hold_shares": sum(positions.values())
        })

    res = pd.DataFrame(history)
    if res.empty:
        print("❌ 回测无数据")
        return res
    
    total_ret = (res["net"].iloc[-1] / CASH - 1) * 100
    max_dd = ((res["net"].cummax() - res["net"]) / res["net"].cummax()).max() * 100
    print(f"\n✅ 回测完成")
    print(f"总收益：{total_ret:.2f}%")
    print(f"最大回撤：{max_dd:.2f}%")
    return res

# ====================== 7. 每日自动决策 ======================
def daily_decision():
    print("\n📄 生成今日交易决策")
    try:
        pos = get_target_position()
        selected = select_final_stocks(20)
        strong_ind = get_strong_industries(10)
        record = {
            "date": str(datetime.now().date()),
            "建议仓位": pos,
            "强势行业": strong_ind,
            "精选标的": selected
        }
        data = load_data()
        data["daily"].append(record)
        save_data(data)
        print("✅ 决策已保存")
        return record
    except Exception as e:
        print(f"❌ 生成决策失败：{e}")
        return {"date": str(datetime.now().date()), "建议仓位": 15, "强势行业": [], "精选标的": []}

# ====================== 主菜单 ======================
def main():
    while True:
        print("\n" + "="*60)
        print("       行业轮动 + 龙头选股 交易系统（移除多因子）")
        print("="*60)
        print("1. 今日自动决策（选股+仓位+行业）")
        print("2. 运行一年回测（收益+回撤）")
        print("3. 查看历史记录")
        print("4. 退出系统")
        choice = input("请输入指令：")
        if choice == "1":
            daily_decision()
        elif choice == "2":
            backtest()
        elif choice == "3":
            data = load_data()
            print("\n最近5条记录：")
            for item in data["daily"][-5:]:
                print(f"{item['date']} | 建议仓位：{item['建议仓位']}%")
        elif choice == "4":
            print("\n👋 退出系统，投资顺利！")
            break

if __name__ == "__main__":
    main()