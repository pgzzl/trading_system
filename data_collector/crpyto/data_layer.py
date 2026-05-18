import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import ccxt
from typing import Optional
from data_collector.crpyto.config import DEFAULT_LIMIT


class BinanceDataFetcher:
    """Binance 原始数据获取层(兼容 qlib)"""

    def __init__(self, enable_rate_limit: bool = True):
        self.exchange = ccxt.binance({
            'enableRateLimit': enable_rate_limit,
            'timeout': 30000,
            'proxies': {
                'http': 'http://127.0.0.1:7897',
                'https': 'http://127.0.0.1:7897',
            },
            'options': {
                'fetchOHLCVMethod': 'public',
            }
        })

    def get_klines(
        self,
        symbol: str = 'BTC/USDT',
        timeframe: str = '1d',
        start_time: Optional[int] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易对(如BTC/USDT或BTCUSDT)
            timeframe: 时间周期(1m, 5m, 15m, 1h, 4h, 1d等)
            start_time: 开始时间(毫秒时间戳)
            limit: 返回条数

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if '/' not in symbol:
            symbol = symbol.replace('USDT', '/USDT')

        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=start_time,
                limit=limit,
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')

            return df

        except Exception as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()

    def get_historical_klines(
        self,
        symbol: str = 'BTC/USDT',
        timeframe: str = '1d',
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        获取历史K线数据

        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_date: 开始日期(格式: '2024-01-01')
            end_date: 结束日期(格式: '2024-12-31')

        Returns:
            DataFrame with all historical data
        """
        if start_date:
            start_time = int(pd.Timestamp(start_date).timestamp() * 1000)
        else:
            start_time = None

        end_time = None
        if end_date:
            end_time = int(pd.Timestamp(end_date).timestamp() * 1000)

        all_data = []
        current_time = start_time

        while True:
            if end_time and current_time and current_time >= end_time:
                break

            df = self.get_klines(
                symbol=symbol,
                timeframe=timeframe,
                start_time=current_time,
                limit=1000,
            )

            if df.empty:
                break

            if end_time:
                df = df[df.index <= pd.Timestamp(end_time, unit='ms')]

            all_data.append(df)

            if len(df) < 1000:
                break

            current_time = int(df.index[-1].timestamp() * 1000) + 1

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data)
        return result[~result.index.duplicated(keep='first')].sort_index()

    def get_ticker_price(self, symbol: str = 'BTC/USDT') -> dict:
        """获取当前价格"""
        if '/' not in symbol:
            symbol = symbol.replace('USDT', '/USDT')
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
            }
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return {}
