
import ccxt
import pandas as pd
from pathlib import Path

# =========================
# 1. 初始化交易所
# =========================

exchange = ccxt.binance({
    'enableRateLimit': True,
    'proxies': {
        'http': 'http://127.0.0.1:7897',
        'https': 'http://127.0.0.1:7897',
    }
})

# =========================
# 2. 获取K线
# =========================

symbol = 'BTC/USDT'
timeframe = '1h'

ohlcv = exchange.fetch_ohlcv(
    symbol=symbol,
    timeframe=timeframe,
    limit=500
)

# =========================
# 3. 转DataFrame
# =========================

df = pd.DataFrame(
    ohlcv,
    columns=[
        'timestamp',
        'open',
        'high',
        'low',
        'close',
        'volume'
    ]
)

# 时间转换
df['timestamp'] = pd.to_datetime(
    df['timestamp'],
    unit='ms'
)

# =========================
# 4. 创建data目录
# =========================

data_dir = Path('data')
data_dir.mkdir(exist_ok=True)

# =========================
# 5. 保存Parquet
# =========================

file_path = data_dir / 'BTCUSDT_1h.parquet'

df.to_parquet(
    file_path,
    index=False
)

print(f'Saved to: {file_path}')

# =========================
# 6. 读取测试
# =========================

df2 = pd.read_parquet(file_path)

print(df2.head())