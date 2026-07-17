"""
intraday_research — does an intraday edge SURVIVE realistic costs?

The whole question with intraday is turnover: gross returns can look fine,
but you trade constantly, so per-trade cost + spread decides everything.
So we report GROSS vs NET at several cost levels AND trades/year.

Hourly bars. Crypto via ccxt (24/7, deepest free intraday history);
US via yfinance hourly (~2y cap). Look-ahead guard: signal shifted 1 bar.
Cost is charged per unit turnover (entry+exit => ~2x per round trip).
"""
from __future__ import annotations
import os, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ.setdefault("VIBE_TRADING_DATA_CACHE", "1")
os.environ.setdefault("TUSHARE_TOKEN", "noop")
from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
_ensure_registered()

INTERVAL = "1H"
BARS_PER_YEAR_CRYPTO = 24 * 365
BARS_PER_YEAR_US = 6.5 * 252  # ~6.5 trading hours/day
START, END = "2023-06-01", "2025-12-31"

ASSETS = [("BTC/USDT","ccxt",BARS_PER_YEAR_CRYPTO),
          ("ETH/USDT","ccxt",BARS_PER_YEAR_CRYPTO),
          ("SPY","yfinance",BARS_PER_YEAR_US),
          ("QQQ","yfinance",BARS_PER_YEAR_US)]


def load(code, src):
    try:
        dm = LOADER_REGISTRY[src]().fetch([code], START, END, interval=INTERVAL)
        df = dm.get(code)
        if df is None or len(df) < 500: return None
        df.index = pd.to_datetime(df.index)
        return df[~df.index.duplicated(keep="last")].sort_index()
    except Exception as e:
        print(f"  ! {code}/{src}: {str(e)[:70]}"); return None


def rsi(s, n):
    d=s.diff(); up=d.clip(lower=0).rolling(n).mean(); dn=(-d.clip(upper=0)).rolling(n).mean()
    return 100-100/(1+up/dn.replace(0,np.nan))


def sigs(df):
    c=df["close"]
    out={}
    out["mom_ema24"]  = (c > c.ewm(span=24).mean()).astype(float)          # hourly trend
    hi=c.rolling(24).max(); lo=c.rolling(24).min()
    br=pd.Series(np.nan,index=c.index); br[c>=hi]=1.0; br[c<=lo]=0.0
    out["breakout24"] = br.ffill().fillna(0.0)                            # 24h breakout
    r=rsi(c,6); mr=pd.Series(np.nan,index=c.index); mr[r<20]=1.0; mr[r>60]=0.0
    out["meanrev_rsi6"] = mr.ffill().fillna(0.0)                          # intraday mean-rev
    return out


def perf(df, pos, cost, bars_per_year):
    ret=df["close"].pct_change().fillna(0.0)
    p=pos.shift(1).fillna(0.0)
    turn=p.diff().abs().fillna(0.0)
    net=p*ret - turn*cost
    gross=p*ret
    if net.std()==0: return None
    n_trades = (turn>0).sum()
    yrs=len(net)/bars_per_year
    def sharpe(x): return x.mean()/x.std()*np.sqrt(bars_per_year)
    def cagr(x):
        eq=(1+x).cumprod(); return eq.iloc[-1]**(1/yrs)-1
    return dict(gross_sh=sharpe(gross), net_sh=sharpe(net),
                gross_cagr=cagr(gross), net_cagr=cagr(net),
                trades_yr=n_trades/yrs)


def main():
    data={}
    print("Loading hourly bars...")
    for code,src,bpy in ASSETS:
        d=load(code,src)
        if d is not None:
            data[code]=(d,bpy)
            print(f"  {code:10} {len(d)} bars {d.index[0]}..{d.index[-1]}")
    print()
    for code,(df,bpy) in data.items():
        print(f"=== {code}  (buy&hold Sharpe {(df['close'].pct_change().mean()/df['close'].pct_change().std()*np.sqrt(bpy)):.2f}) ===")
        print(f"  {'strategy':14}{'trades/yr':>10}{'grossSh':>9}{'netSh@5bp':>11}{'netSh@10bp':>12}{'netCAGR@10bp':>14}")
        for name,pos in sigs(df).items():
            r0=perf(df,pos,0.0,bpy); r5=perf(df,pos,0.0005,bpy); r10=perf(df,pos,0.0010,bpy)
            if not r0: continue
            print(f"  {name:14}{r0['trades_yr']:>10.0f}{r0['gross_sh']:>9.2f}{r5['net_sh']:>11.2f}{r10['net_sh']:>12.2f}{r10['net_cagr']:>13.1%}")
        print()
    print("Read the drop gross->net: that gap IS the intraday cost tax.")


if __name__ == "__main__":
    main()
