import requests

try:
    import yfinance as yf
    d = yf.download("MSFT", start="2022-01-01", end="2023-01-01", progress=False, auto_adjust=True)
    print("yfinance rows:", len(d))
except Exception as e:
    print("yfinance failed:", repr(e))

try:
    r = requests.get("https://stooq.com/q/d/l/?s=msft.us&i=d",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    print("stooq:", r.status_code, r.text[:100].replace("\n", " | "))
except Exception as e:
    print("stooq failed:", repr(e))