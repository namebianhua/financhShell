import requests
import re
import schedule
import time
from datetime import datetime

# ====================== 【配置区 - 只改这里】 ======================
DINGDING_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=85be796f79555f13dbc9bce2470c2b8026b354cd78ed1e2feb013fd3f6c76bad"

# 50个行业龙头股票池
STOCK_POOL = [
    "sh600036", "sh600030", "sh601318", "sh601398", "sh601288",
    "sh600000", "sh601658", "sh601988", "sh601857", "sh600028",
    "sh601628", "sh601336", "sh600104", "sh600031", "sh600887",
    "sh600519", "sh600009", "sh600900", "sh600016", "sh601899",
    "sh601766", "sh601601", "sh601088", "sh601818", "sh601998",
    "sz000858", "sz000568", "sz002594", "sz002415", "sz000333",
    "sz000001", "sz000063", "sz002230", "sz002475", "sz002555",
    "sz002027", "sz300750", "sz300015", "sz300124", "sz300498",
    "sz002241", "sz002352", "sz002271", "sz002456", "sz002714",
    "sz002916", "sz002008", "sz002602", "sz002202", "sz000725"
]

CHECK_INTERVAL = 60  # 秒
# ==================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com/"
}

last_signal_map = {code: None for code in STOCK_POOL}

def send_dingding(title, content):
    msg = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"## {title}\n{content}"
        }
    }
    try:
        requests.post(DINGDING_WEBHOOK, json=msg, timeout=3)
    except Exception as e:
        print(f"钉钉发送失败: {e}")

def get_real_bs_signal(code):
    """
    真实获取新浪财经B/S点信号
    返回: signal(B/S/HOLD), price, time
    """
    url = f"https://finance.sina.com/stock/realchart/jsonp/{code}/signal.js"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        resp.raise_for_status()
        txt = resp.text

        signal = "HOLD"
        if re.search(r'"B"\s*:', txt):
            signal = "B"
        elif re.search(r'"S"\s*:', txt):
            signal = "S"

        # 提取价格
        price_match = re.search(r'"latest"\s*:\s*([\d.]+)', txt)
        price = float(price_match.group(1)) if price_match else 0.0

        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return signal, price, dt

    except Exception as e:
        # print(f"{code} 获取失败: {e}")
        return "ERROR", 0.0, ""

def monitor_pool():
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n=== {now} 轮询 {len(STOCK_POOL)} 只股票 ===")

    for code in STOCK_POOL:
        sig, price, dt = get_real_bs_signal(code)
        if sig in ("B", "S") and sig != last_signal_map[code]:
            title = f"【{code}】出现{sig}信号"
            content = f"""
**股票代码**: {code}
**信号**: {sig}
**价格**: {price:.2f} 元
**时间**: {dt}
"""
            send_dingding(title, content)
            last_signal_map[code] = sig
            print(f"✅ {code} {sig} 已推送钉钉")
        else:
            print(f"{code}: {sig}")
        time.sleep(0.3)  # 防封IP

def main():
    print("🚀 启动新浪财经B/S点实时监控（股票池50龙头）")
    print(f"🔔 信号将通过钉钉推送，间隔 {CHECK_INTERVAL} 秒")

    schedule.every(CHECK_INTERVAL).seconds.do(monitor_pool)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()