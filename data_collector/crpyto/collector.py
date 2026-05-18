import abc
import sys
import datetime
from abc import ABC
from pathlib import Path

import fire
import pandas as pd
import ccxt
from loguru import logger
from dateutil.tz import tzlocal

CUR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CUR_DIR.parent.parent
sys.path.append(str(CUR_DIR.parent.parent))
from data_collector.base import BaseCollector, BaseNormalize, BaseRun
from data_collector.utils import deco_retry

from pycoingecko import CoinGeckoAPI
from time import mktime
from datetime import datetime as dt
import time

_CG_CRYPTO_SYMBOLS = None


def get_cg_crypto_symbols(qlib_data_path: [str, Path] = None) -> list:
    """get crypto symbols in coingecko
        从coingecko获取crypto的symbol列表，包含所有在coingecko上有交易的crypto

    Returns
    -------
        crypto symbols in given exchanges list of coingecko
    """
    global _CG_CRYPTO_SYMBOLS  # pylint: disable=W0603

    @deco_retry
    def _get_coingecko():
        try:
            cg = CoinGeckoAPI()
            resp = pd.DataFrame(cg.get_coins_markets(vs_currency="usd"))
        except Exception as e:
            raise ValueError("request error") from e
        try:
            _symbols = resp["id"].to_list()
        except Exception as e:
            logger.warning(f"request error: {e}")
            raise
        return _symbols

    if _CG_CRYPTO_SYMBOLS is None:
        _all_symbols = _get_coingecko()

        _CG_CRYPTO_SYMBOLS = sorted(set(_all_symbols))

    return _CG_CRYPTO_SYMBOLS



class CryptoCollector(BaseCollector):
    def __init__(
        self,
        save_dir: [str, Path],
        start=None,
        end=None,
        interval="1d",
        max_workers=1,
        max_collector_count=2,
        delay=1,  # delay need to be one
        check_data_length: int = None,
        limit_nums: int = None,
    ):
        """

        Parameters
        ----------
        save_dir: str
            crypto save dir
        max_workers: int
            workers, default 4
        max_collector_count: int
            default 2
        delay: float
            time.sleep(delay), default 0
        interval: str
            freq, value from [1min, 1d], default 1min
        start: str
            start datetime, default None
        end: str
            end datetime, default None
        check_data_length: int
            check data length, if not None and greater than 0, each symbol will be considered complete if its data length is greater than or equal to this value, otherwise it will be fetched again, the maximum number of fetches being (max_collector_count). By default None.
        limit_nums: int
            using for debug, by default None
        """
        super(CryptoCollector, self).__init__(
            save_dir=save_dir,
            start=start,
            end=end,
            interval=interval,
            max_workers=max_workers,
            max_collector_count=max_collector_count,
            delay=delay,
            check_data_length=check_data_length,
            limit_nums=limit_nums,
        )

        self.init_datetime()

    def init_datetime(self):
        """
        初始化时间和间隔，包括开始时间和结束时间的格式转换和默认值设置，以及根据不同的间隔设置不同的默认开始时间
        """
        if self.interval == self.INTERVAL_1min:
            self.start_datetime = max(self.start_datetime, self.DEFAULT_START_DATETIME_1MIN)
        elif self.interval == self.INTERVAL_1d:
            pass
        else:
            raise ValueError(f"interval error: {self.interval}")

        self.start_datetime = self.convert_datetime(self.start_datetime, self._timezone)
        self.end_datetime = self.convert_datetime(self.end_datetime, self._timezone)

    @staticmethod
    def convert_datetime(dt: [pd.Timestamp, datetime.date, str], timezone):
        try:
            dt = pd.Timestamp(dt, tz=timezone).timestamp()
            dt = pd.Timestamp(dt, tz=tzlocal(), unit="s")
        except ValueError as e:
            pass
        return dt

    @property
    @abc.abstractmethod
    def _timezone(self):
        raise NotImplementedError("rewrite get_timezone")

    @staticmethod
    def get_data_from_remote(symbol, interval, start, end):
        """已废弃，请使用 get_data_from_binance 替代"""
        logger.warning("get_data_from_remote is deprecated, use get_data_from_binance instead")
        error_msg = f"{symbol}-{interval}-{start}-{end}"
        try:
            cg = CoinGeckoAPI()
            data = cg.get_coin_market_chart_by_id(id=symbol, vs_currency="usd", days="max")
            _resp = pd.DataFrame(columns=["date"] + list(data.keys()))
            _resp["date"] = [dt.fromtimestamp(mktime(time.localtime(x[0] / 1000))) for x in data["prices"]]
            for key in data.keys():
                _resp[key] = [x[1] for x in data[key]]
            _resp["date"] = pd.to_datetime(_resp["date"])
            _resp["date"] = [x.date() for x in _resp["date"]]
            _resp = _resp[(_resp["date"] < pd.to_datetime(end).date()) & (_resp["date"] > pd.to_datetime(start).date())]
            if _resp.shape[0] != 0:
                _resp = _resp.reset_index()
            if isinstance(_resp, pd.DataFrame):
                return _resp.reset_index()
        except Exception as e:
            logger.warning(f"{error_msg}:{e}")

    @staticmethod
    def get_data_from_binance(symbol, interval, start, end):
        """
        使用 ccxt 从 Binance 获取历史K线数据

        Parameters
        ----------
        symbol: str
            交易对, 如 'BTC/USDT'
        interval: str
            时间周期, 如 '1d', '1h', '1m', '5m', '15m', '4h'
        start: str
            开始时间, 如 '2020-01-01'
        end: str
            结束时间, 如 '2024-01-01'

        Returns
        -------
        pd.DataFrame or None
            columns: date, open, high, low, close, volume
        """
        error_msg = f"{symbol}-{interval}-{start}-{end}"

        # qlib 格式 (1min/1d) 转 Binance 格式 (1m/1d)
        _binance_interval = interval.replace("min", "m") if interval.endswith("min") else interval

        try:
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'proxies': {
                'http': 'http://127.0.0.1:7897',
                'https': 'http://127.0.0.1:7897',
            },
            })

            since = int(pd.Timestamp(start).timestamp() * 1000)
            end_ts = int(pd.Timestamp(end).timestamp() * 1000)

            all_ohlcv = []
            current_since = since

            while current_since < end_ts:
                ohlcv = exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=_binance_interval,
                    since=current_since,
                    limit=1000,
                )

                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)
                current_since = ohlcv[-1][0] + 1

                if len(ohlcv) < 1000:
                    break

            if not all_ohlcv:
                return None

            df = pd.DataFrame(
                all_ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df = df.drop_duplicates(subset=['timestamp'])
            df = df[df['timestamp'] < end_ts]

            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            if _binance_interval == '1d':
                df['date'] = [x.date() for x in df['date']]

            return df[['date', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)

        except Exception as e:
            logger.warning(f"{error_msg}:{e}")
            return None

    def get_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> [pd.DataFrame]:
        """获取数据的主函数，根据不同的时间周期调用不同的数据获取方法，目前仅支持1d,1m"""
        def _get_simple(start_, end_):
            self.sleep()
            _remote_interval = interval
            return self.get_data_from_binance(
                symbol,
                interval=_remote_interval,
                start=start_,
                end=end_,
            )

        if interval == self.INTERVAL_1d or interval == self.INTERVAL_1min:
            _result = _get_simple(start_datetime, end_datetime)
        else:
            raise ValueError(f"cannot support {interval}")
        return _result


class CryptoCollector1min(CryptoCollector, ABC):
    def get_instrument_list(self):
        logger.info("use default binance symbol: BTC/USDT")
        return ["BTC/USDT"]

    def normalize_symbol(self, symbol):
        return symbol

    @property
    def _timezone(self):
        return "Asia/Shanghai"

class CryptoCollector1d(CryptoCollector, ABC):
    def get_instrument_list(self):
        logger.info("get coingecko crypto symbols......")
        symbols = get_cg_crypto_symbols()
        logger.info(f"get {len(symbols)} symbols.")
        return symbols

    def normalize_symbol(self, symbol):
        return symbol

    @property
    def _timezone(self):
        return "Asia/Shanghai"


class CryptoNormalize(BaseNormalize):
    DAILY_FORMAT = "%Y-%m-%d"

    @staticmethod
    def normalize_crypto(
        df: pd.DataFrame,
        calendar_list: list = None,
        date_field_name: str = "date",
        symbol_field_name: str = "symbol",
    ):
        if df.empty:
            return df
        df = df.copy()
        df.set_index(date_field_name, inplace=True)
        df.index = pd.to_datetime(df.index)
        df = df[~df.index.duplicated(keep="first")]
        if calendar_list is not None:
            df = df.reindex(
                pd.DataFrame(index=calendar_list)
                .loc[
                    pd.Timestamp(df.index.min()).date() : pd.Timestamp(df.index.max()).date()
                    + pd.Timedelta(hours=23, minutes=59)
                ]
                .index
            )
        df.sort_index(inplace=True)

        df.index.names = [date_field_name]
        return df.reset_index()

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.normalize_crypto(df, self._calendar_list, self._date_field_name, self._symbol_field_name)
        return df


class CryptoNormalize1d(CryptoNormalize):
    def _get_calendar_list(self):
        return None


class CryptoNormalize1min(CryptoNormalize):
    def _get_calendar_list(self):
        return None


class Run(BaseRun):
    def __init__(self, source_dir=None, normalize_dir=None, max_workers=1, interval="1d"):
        """

        Parameters
        ----------
        source_dir: str
            The directory where the raw data collected from the Internet is saved, default "Path(__file__).parent/source"
        normalize_dir: str
            Directory for normalize data, default "Path(__file__).parent/normalize"
        max_workers: int
            Concurrent number, default is 1
        interval: str
            freq, value from [1min, 1d], default 1d
        """
        super().__init__(source_dir, normalize_dir, max_workers, interval)

    @property
    def collector_class_name(self):
        return f"CryptoCollector{self.interval}"

    @property
    def normalize_class_name(self):
        return f"CryptoNormalize{self.interval}"

    @property
    def default_base_dir(self) -> [Path, str]:
        return PROJECT_ROOT / "rawdata"

    def download_data(
        self,
        max_collector_count=2,
        delay=0,
        start=None,
        end=None,
        check_data_length: int = None,
        limit_nums=None,
    ):
        """download data from Internet

        Parameters
        ----------
        max_collector_count: int
            default 2
        delay: float
            time.sleep(delay), default 0
        interval: str
            freq, value from [1min, 1d], default 1d, currently only supprot 1d
        start: str
            start datetime, default "2000-01-01"
        end: str
            end datetime, default ``pd.Timestamp(datetime.datetime.now() + pd.Timedelta(days=1))``
        check_data_length: int # if this param useful?
            check data length, if not None and greater than 0, each symbol will be considered complete if its data length is greater than or equal to this value, otherwise it will be fetched again, the maximum number of fetches being (max_collector_count). By default None.
        limit_nums: int
            using for debug, by default None

        Examples
        ---------
            # get daily data
            $ python collector.py download_data --source_dir rawdata/source --start 2015-01-01 --end 2021-11-30 --delay 1 --interval 1d
        """

        super(Run, self).download_data(max_collector_count, delay, start, end, check_data_length, limit_nums)

    def normalize_data(self, date_field_name: str = "date", symbol_field_name: str = "symbol"):
        """normalize data

        读取 rawdata/source/*.csv，转换为规范格式后写入 parquet 到
        rawdata/normalized/binance/spot/<interval>/<symbol>/<YYYY-MM>.parquet

        Parameters
        ----------
        date_field_name: str
            date field name, default date
        symbol_field_name: str
            symbol field name, default symbol

        Examples
        ---------
            $ python collector.py normalize_data --interval 1d
            $ python collector.py normalize_data --interval 1min
        """
        # 转换 interval 格式 (1min -> 1m)
        interval_map = {"1min": "1m", "1d": "1d"}
        interval_binance = interval_map.get(self.interval, self.interval)

        source_dir = Path(self.source_dir)
        csv_files = sorted(source_dir.glob("*.csv"))
        if not csv_files:
            logger.warning(f"No CSV files found in {source_dir}")
            return

        output_base = Path(self.default_base_dir) / "normalized" / "binance" / "spot" / interval_binance

        for csv_path in csv_files:
            logger.info(f"Normalizing {csv_path.name} ...")
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning(f"{csv_path.name} is empty, skipping.")
                continue

            # 变换列
            df = df.rename(columns={date_field_name: "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # 清理 symbol: BTC.USDT -> BTCUSDT
            raw_symbol = df[symbol_field_name].iloc[0] if symbol_field_name in df.columns else csv_path.stem
            symbol_clean = raw_symbol.replace(".", "")

            # 添加固定列
            df["exchange"] = "binance"
            df["market_type"] = "spot"
            df["interval"] = interval_binance
            df["symbol"] = symbol_clean

            # 选择并排序列
            target_columns = [
                "timestamp", "exchange", "symbol", "market_type", "interval",
                "open", "high", "low", "close", "volume",
            ]
            df = df[target_columns].sort_values("timestamp").drop_duplicates(subset=["timestamp"])

            # 按月分区写入 parquet
            symbol_dir = output_base / symbol_clean
            symbol_dir.mkdir(parents=True, exist_ok=True)

            df["_month"] = df["timestamp"].dt.strftime("%Y-%m")
            for month, group in df.groupby("_month"):
                group = group.drop(columns=["_month"])
                file_path = symbol_dir / f"{month}.parquet"
                if file_path.exists():
                    existing = pd.read_parquet(file_path)
                    group = pd.concat([existing, group], ignore_index=True)
                    group = group.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
                group.to_parquet(file_path, index=False)
                logger.info(f"  Wrote {file_path} ({len(group)} rows)")

        logger.info("Normalize data completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        print("=" * 60)
        print("Test: get_data_from_binance - BTC/USDT 1m (2026-05-18 06:00 ~ now)")
        print("=" * 60)
        df = CryptoCollector.get_data_from_binance(
            symbol="BTC/USDT",
            interval="1m",
            start="2026-05-18 06:00",
            end=now.strftime("%Y-%m-%d %H:%M"),
        )
        if df is not None and not df.empty:
            print(f"rows: {len(df)}, cols: {list(df.columns)}")
            print(df.head(5))
            print("...")
            print(df.tail(5))
        else:
            print("No data returned")

    else:
        fire.Fire(Run)
