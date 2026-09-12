from datetime import datetime
import os
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf

# GitHub Actions環境でのyfinanceキャッシュエラー回避
os.environ["YFINANCE_CACHE_DIR"] = "/tmp/yfinance_cache"

# 1. データ取得
start_date = "2010-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")


def fetch_yf_data(ticker):
  t = yf.Ticker(ticker)
  df = t.history(start=start_date, end=end_date)
  # タイムゾーン情報を除去して tz-naive に統一
  if df.index.tz is not None:
    df.index = df.index.tz_localize(None)
  return df["Close"]


# 個別に取得
gold_series = fetch_yf_data("GC=F")
gvz_series = fetch_yf_data("^GVZ")

yf_raw = pd.concat([gold_series, gvz_series], axis=1, sort=False)
yf_raw.columns = ["Gold", "GVZ"]
yf_raw = yf_raw.ffill().dropna()

# FREDから金利データを取得 (デフォルトで tz-naive)
fred_data = web.DataReader(["FEDFUNDS"], "fred", start_date, end_date)

# データの統合
df = pd.concat([yf_raw, fred_data], axis=1, sort=False).ffill().dropna()

# 2. 指標計算
df["FF_3M_Change"] = df["FEDFUNDS"].diff(60)
df["GVZ_High"] = (df["GVZ"] > 25) | (
    df["GVZ"] > df["GVZ"].rolling(20).mean() * 1.2
)

latest = df.iloc[-1]
rate_rising = latest["FF_3M_Change"] > 0.25
gvz_high = latest["GVZ_High"]

# --- 金2倍ブル判定（動的ポジション調整） ---
if rate_rising and gvz_high:
  target_size_2x = 30
  reason_2x = "【注意】FF金利上昇 ＋ ボラティリティ(GVZ)過熱。減価リスク回避のためポジション縮小"
elif rate_rising:
  target_size_2x = 70
  reason_2x = "【警戒】FF金利上昇トレンド。強気相場の一休み"
elif gvz_high:
  target_size_2x = 50
  reason_2x = "【警戒】金ボラティリティ(GVZ)過熱。一時的ショック安に注意"
else:
  target_size_2x = 100
  reason_2x = "【良好】マクロ環境・ボラティリティともに安定。フルポジション維持"

# --- 金1倍（現物・1倍ETF）判定（ホールド/買い増し戦略） ---
if rate_rising and gvz_high:
  target_size_1x = "ガチホ (100%)"
  action_1x = "押し目買い準備"
  reason_1x = "マクロ逆風による調整局面。現物・1倍は減価しないため売却不要。連動安は絶好の買い増し好機。"
elif rate_rising or gvz_high:
  target_size_1x = "ガチホ (100%)"
  action_1x = "静観 / 継続保有"
  reason_1x = "一時的なボラティリティ高騰または金利上昇。ガチホを維持。"
else:
  target_size_1x = "ガチホ (100%)"
  action_1x = "継続保有 / 定期積立"
  reason_1x = "上昇トレンド継続中。現物資産として安定保有。"

updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S JST")

# 3. index.html の自動出力
html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>金ポートフォリオ ポジション判定</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; text-align: center; color: #333; }}
        .container {{ max-width: 800px; margin: 20px auto; }}
        .header {{ margin-bottom: 25px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
        .card {{ background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; }}
        .card-title {{ font-size: 1.2rem; font-weight: bold; margin-bottom: 15px; color: #1e293b; }}
        .size {{ font-size: 2.8rem; font-weight: bold; color: #d97706; margin: 15px 0; }}
        .action-tag {{ display: inline-block; padding: 6px 14px; background: #e0f2fe; color: #0369a1; font-weight: bold; border-radius: 20px; font-size: 0.9rem; margin-bottom: 15px; }}
        .reason {{ background: #fef3c7; color: #92400e; padding: 12px; border-radius: 8px; font-size: 0.9rem; text-align: left; line-height: 1.5; }}
        .meta-card {{ background: #fff; margin-top: 20px; padding: 15px; border-radius: 8px; font-size: 0.85rem; color: #64748b; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>金（Gold）アセット別ポジション判定</h2>
        </div>
        <div class="grid">
            <!-- 金2倍ブル -->
            <div class="card">
                <div class="card-title">金2倍ブル（レバレッジ）</div>
                <div class="size">{target_size_2x}%</div>
                <div class="reason">{reason_2x}</div>
            </div>
            <!-- 金1倍（現物・ノーマル） -->
            <div class="card">
                <div class="card-title">金1倍（現物 / 通常ETF）</div>
                <div class="size" style="color: #059669;">{target_size_1x}</div>
                <div class="action-tag">{action_1x}</div>
                <div class="reason" style="background: #ecfdf5; color: #065f46;">{reason_1x}</div>
            </div>
        </div>
        <div class="meta-card">
            最終更新日時: {updated_at}<br>
            前日金スポット価格: <strong>${latest['Gold']:.1f}</strong> | 金ボラティリティ指数(GVZ): <strong>{latest['GVZ']:.2f}</strong> | FF金利3ヶ月変動: <strong>{latest['FF_3M_Change']:+.2f}%</strong>
        </div>
    </div>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)
