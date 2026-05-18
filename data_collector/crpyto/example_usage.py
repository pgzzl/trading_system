#!/usr/bin/env python3
"""使用示例 - 需要在 qlib 环境中运行"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_collector.crpyto.data_layer import BinanceDataFetcher
from data_collector.crpyto.config import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME


def main():
    print("初始化 Binance 数据获取器...")
    fetcher = BinanceDataFetcher(enable_rate_limit=True)

    # 示例1: 获取最近100条1天线数据
    print("\n示例1: 获取BTC近期1d数据...")
    try:
        df = fetcher.get_klines(symbol='BTC/USDT', timeframe='1d', limit=100)
        print(df.head())
        print(f"总共获取 {len(df)} 条数据\n")
    except Exception as e:
        print(f"错误: {e}\n")

    # 示例2: 获取当前价格
    print("示例2: 获取BTC当前价格...")
    try:
        ticker = fetcher.get_ticker_price('BTC/USDT')
        print(f"BTC/USDT 当前价格: {ticker.get('price', 'N/A')} USDT")
        print(f"买价(Bid): {ticker.get('bid', 'N/A')}")
        print(f"卖价(Ask): {ticker.get('ask', 'N/A')}\n")
    except Exception as e:
        print(f"错误: {e}\n")

    # 示例3: 获取最近30天的历史数据
    print("示例3: 获取最近30天的数据...")
    try:
        hist_df = fetcher.get_historical_klines(
            symbol='BTC/USDT',
            timeframe='1d',
            start_date='2026-04-17',
            end_date='2026-05-17'
        )
        print(f"获取了 {len(hist_df)} 条历史数据")
        if len(hist_df) > 0:
            print(f"时间范围: {hist_df.index.min()} 到 {hist_df.index.max()}")
            print(hist_df.head())
    except Exception as e:
        print(f"错误: {e}\n")


if __name__ == '__main__':
    main()

