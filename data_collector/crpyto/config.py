import os
from dotenv import load_dotenv

load_dotenv()

# Binance 配置 (使用 ccxt)
DEFAULT_SYMBOL = 'BTC/USDT'
DEFAULT_TIMEFRAME = '1d'
DEFAULT_LIMIT = 100

# qlib 配置
QLIB_FEATURES = ['open', 'high', 'low', 'close', 'volume']

