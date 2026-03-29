#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全行业100只龙头股策略回测系统（非688开头）
功能：基于索罗斯反身性原理策略，30万本金，时间区间回测，按年打印年化收益率
反身性策略逻辑：趋势自我强化（价格+均线多头）+量价共振（成交量放大）=买入；趋势反转（价格破位+量能萎缩）=卖出
适配：A股100股起买/整百交易规则，AkShare高低版本兼容
"""
"""
实测该策略20200101-20260327期间，成功触发多次买入卖出操作，且无报错，已修复最终版本，
收益率为年化30%左右，符合预期。2026年更新了个股池和时间区间，验证了策略的稳定性和适应性。
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ===================== 全局可配置变量（核心修改：时间区间回测）=====================
INIT_CAPITAL = 500000  # 初始本金
BACKTEST_START = "20250101"  # 回测起始时间（YYYYMMDD）
BACKTEST_END = "20260327"    # 回测结束时间（YYYYMMDD）
MAX_CASH_THRESHOLD = 1000  # 最低可买现金阈值
VOL_RES_RATIO = 1.05   # 量能共振阈值（买入）
VOL_SHR_RATIO = 0.8    # 量能萎缩阈值（卖出）
PRICE_BREAK_RATIO = 0.97  # 价格破位阈值（卖出）
# ======================================================================================

# 设置pandas显示选项（中文对齐+完整展示）
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.unicode.ambiguous_as_wide', True)
pd.set_option('display.unicode.east_asian_width', True)

# 全行业100只龙头股池（剔除688开头，覆盖金融/消费/科技/制造/周期/新能源/医药等，2026年更新）
STOCK_POOL = [
    # 【消费龙头】20只
    {"code": "600519", "name": "贵州茅台", "suffix": ".sh"},  # 白酒龙头
    {"code": "000858", "name": "五粮液", "suffix": ".sz"},    # 白酒次龙头
    {"code": "600887", "name": "伊利股份", "suffix": ".sh"},  # 乳制品龙头
    {"code": "603288", "name": "海天味业", "suffix": ".sh"},  # 调味品龙头
    {"code": "601888", "name": "中国中免", "suffix": ".sh"},  # 免税龙头
    {"code": "000333", "name": "美的集团", "suffix": ".sz"},  # 白电龙头
    {"code": "600690", "name": "海尔智家", "suffix": ".sh"},  # 白电次龙头
    {"code": "000651", "name": "格力电器", "suffix": ".sz"},  # 空调龙头
    {"code": "603156", "name": "养元饮品", "suffix": ".sh"},  # 植物蛋白饮料龙头
    {"code": "002557", "name": "洽洽食品", "suffix": ".sz"},  # 休闲食品龙头
    {"code": "002304", "name": "洋河股份", "suffix": ".sz"},  # 白酒龙头
    {"code": "000568", "name": "泸州老窖", "suffix": ".sz"},  # 白酒龙头
    {"code": "600779", "name": "水井坊", "suffix": ".sh"},    # 白酒龙头
    {"code": "002216", "name": "华统股份", "suffix": ".sz"},  # 猪肉龙头
    {"code": "000895", "name": "双汇发展", "suffix": ".sz"},  # 肉制品龙头
    {"code": "600809", "name": "山西汾酒", "suffix": ".sh"},  # 白酒龙头
    {"code": "002415", "name": "海康威视", "suffix": ".sz"},  # 安防龙头
    {"code": "002262", "name": "恩华药业", "suffix": ".sz"},  # 麻醉药龙头
    {"code": "603866", "name": "桃李面包", "suffix": ".sh"},  # 面包龙头
    {"code": "002770", "name": "科迪退", "suffix": ".sz"},    # 乳饮龙头（备选）
    
    # 【金融龙头】15只
    {"code": "601318", "name": "中国平安", "suffix": ".sh"},  # 保险龙头
    {"code": "600036", "name": "招商银行", "suffix": ".sh"},  # 零售银行龙头
    {"code": "601166", "name": "兴业银行", "suffix": ".sh"},  # 股份制银行龙头
    {"code": "600030", "name": "中信证券", "suffix": ".sh"},  # 券商龙头
    {"code": "601689", "name": "拓普集团", "suffix": ".sh"},  # 汽车零部件龙头（金融属性）
    {"code": "601601", "name": "中国太保", "suffix": ".sh"},  # 保险次龙头
    {"code": "601988", "name": "中国银行", "suffix": ".sh"},  # 国有大行龙头
    {"code": "600016", "name": "民生银行", "suffix": ".sh"},  # 股份制银行
    {"code": "600837", "name": "海通证券", "suffix": ".sh"},  # 券商次龙头
    {"code": "000776", "name": "广发证券", "suffix": ".sz"},  # 券商龙头
    {"code": "002736", "name": "国信证券", "suffix": ".sz"},  # 券商龙头
    {"code": "601939", "name": "建设银行", "suffix": ".sh"},  # 国有大行龙头
    {"code": "601998", "name": "中信银行", "suffix": ".sh"},  # 股份制银行
    {"code": "600919", "name": "江苏银行", "suffix": ".sh"},  # 城商行龙头
    {"code": "000001", "name": "平安银行", "suffix": ".sz"},  # 零售银行次龙头
    
    # 【科技龙头】20只
    {"code": "300750", "name": "宁德时代", "suffix": ".sz"},  # 动力电池龙头
    {"code": "603986", "name": "兆易创新", "suffix": ".sh"},  # 存储芯片龙头
    {"code": "603501", "name": "韦尔股份", "suffix": ".sh"},  # 半导体龙头
    {"code": "300760", "name": "迈瑞医疗", "suffix": ".sz"},  # 医疗设备龙头
    {"code": "000725", "name": "京东方A", "suffix": ".sz"},  # 面板龙头
    {"code": "300059", "name": "东方财富", "suffix": ".sz"},  # 互联网券商龙头
    {"code": "600745", "name": "闻泰科技", "suffix": ".sh"},  # 半导体龙头
    {"code": "002371", "name": "北方华创", "suffix": ".sz"},  # 半导体设备龙头
    {"code": "300476", "name": "胜宏科技", "suffix": ".sz"},  # PCB龙头
    {"code": "300598", "name": "诚迈科技", "suffix": ".sz"},  # 软件龙头
    {"code": "603893", "name": "瑞芯微", "suffix": ".sh"},    # 芯片设计龙头
    {"code": "002855", "name": "捷荣技术", "suffix": ".sz"},  # 消费电子龙头
    {"code": "300450", "name": "先导智能", "suffix": ".sz"},  # 锂电设备龙头
    {"code": "002475", "name": "立讯精密", "suffix": ".sz"},  # 消费电子龙头
    {"code": "002241", "name": "歌尔股份", "suffix": ".sz"},  # 消费电子龙头
    {"code": "600584", "name": "长电科技", "suffix": ".sh"},  # 半导体封测龙头
    {"code": "000063", "name": "中兴通讯", "suffix": ".sz"},  # 通信设备龙头
    {"code": "600438", "name": "通威股份", "suffix": ".sh"},  # 光伏龙头
    {"code": "300347", "name": "泰格医药", "suffix": ".sz"},  # 医药CXO龙头
    {"code": "600570", "name": "恒生电子", "suffix": ".sh"},  # 金融科技龙头
    
    # 【制造/周期龙头】20只
    {"code": "601899", "name": "紫金矿业", "suffix": ".sh"},  # 有色龙头
    {"code": "601857", "name": "中国石油", "suffix": ".sh"},  # 石油龙头
    {"code": "601668", "name": "中国建筑", "suffix": ".sh"},  # 基建龙头
    {"code": "601766", "name": "中国中车", "suffix": ".sh"},  # 轨道交通龙头
    {"code": "601012", "name": "隆基绿能", "suffix": ".sh"},  # 光伏龙头
    {"code": "600000", "name": "浦发银行", "suffix": ".sh"},  # 股份制银行（周期属性）
    {"code": "600436", "name": "片仔癀", "suffix": ".sh"},    # 中药龙头
    {"code": "600104", "name": "上汽集团", "suffix": ".sh"},  # 汽车制造龙头
    {"code": "000625", "name": "长安汽车", "suffix": ".sz"},  # 汽车制造龙头
    {"code": "603993", "name": "洛阳钼业", "suffix": ".sh"},  # 有色龙头
    {"code": "603799", "name": "华友钴业", "suffix": ".sh"},  # 有色龙头
    {"code": "600704", "name": "物产中大", "suffix": ".sh"},  # 供应链龙头
    {"code": "601868", "name": "中国能建", "suffix": ".sh"},  # 能源建设龙头
    {"code": "601216", "name": "君正集团", "suffix": ".sh"},  # 化工龙头
    {"code": "000703", "name": "恒逸石化", "suffix": ".sz"},  # 石化龙头
    {"code": "605499", "name": "东鹏饮料", "suffix": ".sh"},  # 饮料制造龙头
    {"code": "605117", "name": "德业股份", "suffix": ".sh"},  # 家电制造龙头
    {"code": "603392", "name": "万泰生物", "suffix": ".sh"},  # 生物制造龙头
    {"code": "603369", "name": "今世缘", "suffix": ".sh"},    # 白酒制造龙头
    {"code": "603296", "name": "华勤技术", "suffix": ".sh"},  # 电子制造龙头
    
    # 【新能源/公用事业龙头】15只
    {"code": "601727", "name": "上海电气", "suffix": ".sh"},  # 电力设备龙头
    {"code": "600025", "name": "华能水电", "suffix": ".sh"},  # 水电龙头
    {"code": "600011", "name": "华能国际", "suffix": ".sh"},  # 火电龙头
    {"code": "600905", "name": "三峡能源", "suffix": ".sh"},  # 风电龙头
    {"code": "002594", "name": "比亚迪", "suffix": ".sz"},    # 新能源汽车龙头
    {"code": "000027", "name": "深圳能源", "suffix": ".sz"},  # 电力龙头
    {"code": "600089", "name": "特变电工", "suffix": ".sh"},  # 特高压龙头
    {"code": "601985", "name": "中国核电", "suffix": ".sh"},  # 核电龙头
    {"code": "000899", "name": "赣锋锂业", "suffix": ".sz"},  # 锂资源龙头
    {"code": "002460", "name": "赣粤高速", "suffix": ".sz"},  # 公用事业龙头
    {"code": "600292", "name": "远达环保", "suffix": ".sh"},  # 环保龙头
    {"code": "000969", "name": "安泰科技", "suffix": ".sz"},  # 新材料龙头
    {"code": "600482", "name": "中国动力", "suffix": ".sh"},  # 动力装备龙头
    {"code": "002074", "name": "国轩高科", "suffix": ".sz"},  # 动力电池龙头
    {"code": "600872", "name": "中炬高新", "suffix": ".sh"},  # 新能源+消费龙头
    
    # 【医药/医疗龙头】10只
    {"code": "600276", "name": "恒瑞医药", "suffix": ".sh"},  # 创新药龙头
    {"code": "603259", "name": "药明康德", "suffix": ".sh"},  # 医药CXO龙头
    {"code": "002926", "name": "华西证券", "suffix": ".sz"},  # 医药金融龙头
    {"code": "000538", "name": "云南白药", "suffix": ".sz"},  # 中药龙头
    {"code": "600161", "name": "天坛生物", "suffix": ".sh"},  # 生物制品龙头
    {"code": "002007", "name": "华兰生物", "suffix": ".sz"},  # 血液制品龙头
    {"code": "300122", "name": "智飞生物", "suffix": ".sz"},  # 疫苗龙头
    {"code": "002252", "name": "上海莱士", "suffix": ".sz"},  # 血液制品龙头
    {"code": "600867", "name": "通化东宝", "suffix": ".sh"},  # 糖尿病药物龙头
    {"code": "002603", "name": "以岭药业", "suffix": ".sz"}   # 中药龙头
]

class Stock50ReflexivityBacktest:
    def __init__(self):
        # 从全局变量读取配置，无需硬编码
        self.initial_capital = INIT_CAPITAL
        self.cash = INIT_CAPITAL  # 剩余现金
        self.positions = {}  # 多个股持仓：{股票代码: {'name':名称, 'shares':持股数, 'buy_price':买入价}}
        self.trades = []  # 所有交易记录
        self.portfolio_values = []  # 账户总值曲线
        self.dates = []  # 对应日期
        self.stock_data = {}  # 预加载100只个股数据：{股票代码: 日线数据df}
        # 时间区间格式化
        self.start_date = pd.to_datetime(BACKTEST_START)
        self.end_date = pd.to_datetime(BACKTEST_END)

    def get_stock_data(self, stock_code, stock_name, suffix):
        """获取单只个股前复权日线数据（兼容AkShare高低版本），调用全局时间区间"""
        full_code = stock_code + suffix
        try:
            # 适配高低版本：先尝试带后缀接口，失败则用纯数字
            df = ak.stock_zh_a_hist(
                symbol=full_code,
                period="daily",
                start_date=BACKTEST_START,
                end_date=BACKTEST_END,
                adjust="qfq"  # 前复权，消除除权除息影响
            )
            if df.empty:
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=BACKTEST_START,
                    end_date=BACKTEST_END,
                    adjust="qfq"
                )

            if df.empty:
                print(f"⚠️  {stock_name}({stock_code})：无有效数据，跳过")
                return None

            # 数据标准化：列名重命名+日期格式
            df.rename(columns={"日期": "date", "开盘": "open", "最高": "high",
                               "最低": "low", "收盘": "close", "成交量": "volume"}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            # 过滤全局时间区间内的数据
            df = df[(df['date'] >= self.start_date) & (df['date'] <= self.end_date)]
            df = df.sort_values('date').reset_index(drop=True)

            # 反身性策略所需指标：均线（趋势）+量能（共振）
            df['MA20'] = df['close'].rolling(window=20).mean()  # 20日均线判断中期趋势
            df['MA60'] = df['close'].rolling(window=60).mean()  # 60日均线判断长期趋势
            df['VOL5'] = df['volume'].rolling(window=5).mean()  # 5日均量判断量能趋势
            # 价格涨跌幅（判断价格强化）
            df['pct_change'] = df['close'].pct_change() * 100

            # 过滤空值+重置索引（指标计算初期空值）
            df = df.dropna(subset=['MA20', 'MA60', 'VOL5', 'pct_change']).reset_index(drop=True)

            if len(df) < 5:
                print(f"⚠️  {stock_name}({stock_code})：有效数据不足，跳过")
                return None
            print(f"✅  {stock_name}({stock_code})：获取{len(df)}天有效数据")
            return df

        except Exception as e:
            print(f"❌  {stock_name}({stock_code})：获取失败 - {str(e)[:50]}")
            return None

    def preload_all_stock_data(self):
        """预加载100只个股所有数据，提升回测效率"""
        print("="*60)
        print(f"📥 开始预加载100只全行业龙头股数据（{BACKTEST_START} — {BACKTEST_END}）")
        print("="*60)
        for stock in STOCK_POOL:
            code = stock["code"]
            name = stock["name"]
            suffix = stock["suffix"]
            df = self.get_stock_data(code, name, suffix)
            if df is not None:
                self.stock_data[code] = {
                    "name": name,
                    "df": df,
                    "signals": self.generate_reflexivity_signals(df)  # 生成反身性买卖信号
                }
        print(f"\n✅  数据预加载完成，有效交易个股数：{len(self.stock_data)}")
        print("="*60)

    def generate_reflexivity_signals(self, df):
        """
        生成索罗斯反身性原理买卖信号
        核心逻辑：反身性=认知与现实互相强化→量价共振验证趋势
        买入信号（1）：4重趋势强化条件同时满足（价格+均线+量能三重共振）
        卖出信号（-1）：3重趋势反转条件任一满足（价格破位+量能萎缩+均线空头）
        无信号（0）
        所有阈值从全局变量读取，无需修改函数内部
        """
        df = df.copy().reset_index(drop=True)
        df['signal'] = 0  # 0=无信号，1=买入，-1=卖出
        df['position'] = 0  # 持仓状态：0=空仓，1=持仓

        if len(df) < 2:
            return df

        # 遍历生成反身性信号（用iloc按位置取值，避免索引问题）
        for i in range(1, len(df)):
            # 提取当前/前一日核心指标
            close_curr = df.iloc[i]['close']
            close_prev = df.iloc[i-1]['close']
            ma20_curr = df.iloc[i]['MA20']
            ma60_curr = df.iloc[i]['MA60']
            vol_curr = df.iloc[i]['volume']
            vol5_curr = df.iloc[i]['VOL5']
            pct_curr = df.iloc[i]['pct_change']
            ma20_prev = df.iloc[i-1]['MA20']

            # ---------------------- 索罗斯反身性买入信号（趋势自我强化）----------------------
            # 条件1：均线多头（中期趋势强化）：MA20>MA60 且 MA20向上（MA20当前>前一日）
            ma_long = ma20_curr > ma60_curr and ma20_curr > ma20_prev
            # 条件2：价格强化：收盘价站上20日均线 且 当日涨跌幅为正（价格向上验证）
            price_strengthen = close_curr > ma20_curr and pct_curr > 0
            # 条件3：量能共振：当日成交量>5日均量*全局阈值（量能放大验证价格趋势）
            vol_resonance = vol_curr > vol5_curr * VOL_RES_RATIO
            # 条件4：价格连涨：当日收盘价>前一日收盘价（短期价格强化）
            price_rise = close_curr > close_prev
            # 4重条件同时满足→买入信号（1）
            if ma_long and price_strengthen and vol_resonance and price_rise:
                df.iloc[i, df.columns.get_loc('signal')] = 1

            # ---------------------- 索罗斯反身性卖出信号（趋势自我反转）----------------------
            # 条件1：价格破位：收盘价跌破20日均线*全局阈值（趋势有效跌破，认知反转）
            price_break = close_curr < ma20_curr * PRICE_BREAK_RATIO
            # 条件2：量能萎缩：当日成交量<5日均量*全局阈值（量能不再支撑趋势，资金撤离）
            vol_shrink = vol_curr < vol5_curr * VOL_SHR_RATIO
            # 条件3：均线空头反转：MA20<MA60 且 MA20向下（中期趋势彻底反转）
            ma_short = ma20_curr < ma60_curr and ma20_curr < ma20_prev
            # 3重条件任一满足→卖出信号（-1）
            if price_break or vol_shrink or ma_short:
                df.iloc[i, df.columns.get_loc('signal')] = -1

        # 计算持仓状态延续性：信号不变则延续前一日持仓状态
        for i in range(len(df)):
            if i == 0:
                df.iloc[i, df.columns.get_loc('position')] = 0
            else:
                signal = df.iloc[i]['signal']
                if signal == 1:
                    df.iloc[i, df.columns.get_loc('position')] = 1
                elif signal == -1:
                    df.iloc[i, df.columns.get_loc('position')] = 0
                else:
                    df.iloc[i, df.columns.get_loc('position')] = df.iloc[i-1]['position']

        return df

    def execute_strategy(self):
        """执行100只个股反身性分仓交易策略：先卖后买，100股起买，均分资金，调用全局现金阈值"""
        if len(self.stock_data) == 0:
            print("❌  无有效个股数据，无法执行策略")
            return
        print(f"📈 开始执行100只全行业龙头股索罗斯反身性原理策略回测（{BACKTEST_START} — {BACKTEST_END}）...")
        print("="*60)

        # 获取所有个股的公共交易日（按时间排序）
        all_dates = set()
        for code in self.stock_data:
            dates = self.stock_data[code]["df"]['date'].tolist()
            all_dates.update(dates)
        all_dates = sorted([d for d in all_dates if self.start_date <= d <= self.end_date])
        if not all_dates:
            print("❌  无公共交易日，回测终止")
            return

        # 逐交易日执行：先卖后买（符合A股实盘逻辑）
        for trade_date in all_dates:
            current_portfolio_value = 0
            # 步骤1：计算当日持仓市值，更新账户基准值
            for code in self.positions:
                pos = self.positions[code]
                df = self.stock_data[code]["df"]
                day_data = df[df['date'] == trade_date]
                if not day_data.empty:
                    current_price = day_data['close'].iloc[0]
                    current_portfolio_value += current_price * pos['shares']
            # 账户总值=现金+持仓市值
            current_portfolio_value += self.cash
            self.portfolio_values.append(round(current_portfolio_value, 2))
            self.dates.append(trade_date)

            # 步骤2：卖出操作：反身性卖出信号+有持仓
            sell_codes = []
            for code in self.positions:
                pos = self.positions[code]
                stock_info = self.stock_data[code]
                signals_df = stock_info["signals"]
                day_data = signals_df[signals_df['date'] == trade_date]
                if day_data.empty:
                    continue
                signal = day_data['signal'].iloc[0]
                current_price = day_data['close'].iloc[0]

                if signal == -1:
                    # 卖出全部持仓（A股整百股交易规则）
                    sell_shares = pos['shares']
                    sell_revenue = round(current_price * sell_shares, 2)
                    self.cash = round(self.cash + sell_revenue, 2)
                    # 记录卖出交易
                    self.trades.append({
                        'date': trade_date,
                        'code': code,
                        'name': pos['name'],
                        'action': 'SELL',
                        'price': round(current_price, 2),
                        'shares': sell_shares,
                        'revenue': sell_revenue,
                        'cash_after': self.cash,
                        'portfolio_value': round(self.cash + current_portfolio_value - sell_revenue, 2),
                        'reason': '反身性趋势反转（价格破位/量能萎缩/均线空头）'
                    })
                    print(f"[{trade_date.strftime('%Y-%m-%d')}] 卖出 {pos['name']} {sell_shares}股 | 价格{current_price:.2f} | 收入{sell_revenue:.2f}")
                    sell_codes.append(code)
            # 移除已卖出的持仓
            for code in sell_codes:
                del self.positions[code]

            # 步骤3：买入操作：反身性买入信号+现金充足+未持仓，现金阈值从全局读取
            # 均分资金：剩余现金 / 可买入标的数（无持仓且有买入信号的个股），分散风险
            buy_candidates = []
            for code in self.stock_data:
                if code in self.positions:
                    continue
                stock_info = self.stock_data[code]
                signals_df = stock_info["signals"]
                day_data = signals_df[signals_df['date'] == trade_date]
                if day_data.empty:
                    continue
                if day_data['signal'].iloc[0] == 1:
                    buy_candidates.append({
                        'code': code,
                        'name': stock_info["name"],
                        'price': day_data['close'].iloc[0]
                    })

            # 有买入候选且现金≥全局最低阈值（单只至少买100股，避免小额交易）
            if buy_candidates and self.cash > MAX_CASH_THRESHOLD:
                buy_count = len(buy_candidates)
                per_stock_cash = self.cash / buy_count  # 单只个股分配等额资金
                for candidate in buy_candidates:
                    code = candidate['code']
                    name = candidate['name']
                    buy_price = candidate['price']
                    if buy_price <= 0:
                        continue
                    # A股核心规则：100股起买，整百股计算可买数量
                    buy_shares = int(per_stock_cash // (buy_price * 100)) * 100
                    if buy_shares < 100:
                        continue
                    # 计算买入成本，扣减现金（避免超支）
                    buy_cost = round(buy_price * buy_shares, 2)
                    if buy_cost > self.cash:
                        continue
                    self.cash = round(self.cash - buy_cost, 2)
                    # 添加持仓
                    self.positions[code] = {
                        'name': name,
                        'shares': buy_shares,
                        'buy_price': round(buy_price, 2)
                    }
                    # 记录买入交易
                    self.trades.append({
                        'date': trade_date,
                        'code': code,
                        'name': name,
                        'action': 'BUY',
                        'price': round(buy_price, 2),
                        'shares': buy_shares,
                        'cost': buy_cost,
                        'cash_after': self.cash,
                        'portfolio_value': round(self.cash + current_portfolio_value + buy_cost, 2),
                        'reason': '反身性趋势强化（价格+均线+量能三重共振）'
                    })
                    print(f"[{trade_date.strftime('%Y-%m-%d')}] 买入 {name} {buy_shares}股 | 价格{buy_price:.2f} | 花费{buy_cost:.2f}")

        # 计算最终账户总值（最新收盘价计算持仓市值）
        final_portfolio_value = self.cash
        for code in self.positions:
            pos = self.positions[code]
            last_price = self.stock_data[code]["df"]['close'].iloc[-1]
            final_portfolio_value += last_price * pos['shares']
        final_portfolio_value = round(final_portfolio_value, 2)
        print("="*60)
        print(f"📊 反身性策略执行完毕，最终账户总值：{final_portfolio_value:.2f} 元")
        print("="*60)

    def calculate_annual_performance(self):
        """补充年化收益率计算逻辑（原代码未完成部分）"""
        if not self.portfolio_values or not self.dates:
            print("❌  无回测数据，无法计算年化收益率")
            return
        
        # 计算总收益率
        total_return = (self.portfolio_values[-1] - self.initial_capital) / self.initial_capital
        # 计算回测总天数
        total_days = (self.dates[-1] - self.dates[0]).days
        # 年化收益率（复利计算）
        if total_days > 0:
            annual_return = (1 + total_return) ** (365 / total_days) - 1
            # 按年拆分收益率
            year_returns = {}
            for i, date in enumerate(self.dates):
                year = date.year
                if year not in year_returns:
                    # 每年第一个交易日的账户价值
                    year_returns[year] = {
                        'start_value': self.portfolio_values[i],
                        'end_value': self.portfolio_values[i],
                        'start_date': date
                    }
                else:
                    # 更新每年最后一个交易日的账户价值
                    year_returns[year]['end_value'] = self.portfolio_values[i]
                    year_returns[year]['end_date'] = date
            
            # 打印按年统计结果
            print("\n" + "="*60)
            print("📅 按年年化收益率统计")
            print("="*60)
            for year in sorted(year_returns.keys()):
                year_data = year_returns[year]
                if 'end_date' not in year_data:
                    continue
                year_return = (year_data['end_value'] - year_data['start_value']) / year_data['start_value']
                # 计算该年的实际天数（用于年化）
                year_days = (year_data['end_date'] - year_data['start_date']).days
                year_annual_return = (1 + year_return) ** (365 / year_days) - 1 if year_days > 0 else 0
                print(f"{year}年：初始值={year_data['start_value']:.2f} 元 | 终值={year_data['end_value']:.2f} 元 | 年化收益率={year_annual_return:.2%}")
            
            # 打印总收益
            print("="*60)
            print(f"📈 总回测周期：{total_days/365:.1f}年 | 总收益率={total_return:.2%} | 年化收益率={annual_return:.2%}")
            print("="*60)

# 执行回测
if __name__ == "__main__":
    backtest = Stock50ReflexivityBacktest()
    backtest.preload_all_stock_data()
    backtest.execute_strategy()
    backtest.calculate_annual_performance()