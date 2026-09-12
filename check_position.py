from datetime import datetime
import os
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf

# 1. データ取得
start_date = "2010-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

yf_raw = yf.download(
    ["GC=F", "^GVZ"], start=start_date, end=end_date, auto_adjust=True
)["Close"]
yf_raw.columns = ["Gold", "GVZ"]
fred_data = web.DataReader(["FEDFUNDS"], "fred", start_date, end_date)

df = pd.concat([yf_raw, fred_data], axis=1, sort=False).ffill().dropna()

# 2. 最新日の判定
df["FF_3M_Change"] = df["FEDFUNDS"].diff(60)
df["GVZ_High"] = (df["GVZ"] > 25) | (
    df["GVZ"] > df["GVZ"].rolling(20).mean() * 1.2
)

latest = df.iloc[-1]
rate_rising = latest["FF_3M_Change"] > 0.25
gvz_high = latest["GVZ_High"]

if rate_rising and gvz_high:
  target_size = 30
  reason = "【注意】FF金利上昇トレンド ＋ 金ボラティリティ(GVZ)過熱"
elif rate_rising:
  target_size = 70
  reason = "【警戒】FF金利上昇トレンド（ボラティリティは正常）"
elif gvz_high:
  target_size = 50
  reason = "【警戒】金ボラティリティ(GVZ)過熱（金利は安定）"
else:
  target_size = 100
  reason = "【良好】マクロ環境・ボラティリティともに安定"

updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S JST")

# 3. index.html の自動出力
html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>金2倍ブル ポジション判定</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; text-align: center; }}
        .card {{ background: #fff; max-width: 480px; margin: 40px auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        .size {{ font-size: 3rem; font-weight: bold; color: #d97706; margin: 20px 0; }}
        .reason {{ background: #fef3c7; color: #92400e; padding: 12px; border-radius: 8px; font-size: 0.95rem; margin-bottom: 20px; }}
        .meta {{ font-size: 0.85rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>金2倍ブル 当日推奨ポジション</h2>
        <div class="size">{target_size}%</div>
        <div class="reason">{reason}</div>
        <div class="meta">
            最終更新: {updated_at}<br>
            前日金価格: {latest['Gold']:.1f} | GVZ: {latest['GVZ']:.2f}
        </div>
    </div>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)
