数据集结构
```
    cn_data/
    ├── calendars/
    │   ├── day.txt            # A股交易日历（6386个交易日，2000-01-04 ~ 2025-09-30）
    │   └── day_future.txt     # 期货交易日历
    ├── instruments/
    │   ├── all.txt            # 全部股票池（6095只，格式: 代码  上市日期  退市日期）
    │   ├── csi300.txt         # 沪深300
    │   ├── csi500.txt         # 中证500
    │   ├── csi800.txt         # 中证800
    │   ├── csi1000.txt        # 中证1000
    │   └── csiall.txt         # 全A
    └── features/
        └── {stock_code}/      # 每只股票一个目录（6095个目录）
            ├── close.day.bin      # 收盘价（复权调整后）
            ├── open.day.bin       # 开盘价
            ├── high.day.bin       # 最高价
            ├── low.day.bin        # 最低价
            ├── adjclose.day.bin   # 复权收盘价
            ├── vwap.day.bin       # 均价（VWAP）
            ├── volume.day.bin     # 成交量
            ├── amount.day.bin     # 成交额
            ├── change.day.bin     # 涨跌幅
            └── factor.day.bin     # 复权因子
```
Bin 格式说明
每个 .bin 文件由 长度 = 记录的个数 的序列组成，每条记录 8 字节（2 个 float32）：

偏移	字段	说明
0-3	值	对应字段的数值（复权调整后）
4-7	复权因子	用于反向复权的乘数
复权计算：实际价格 = bin中存储的值 / 复权因子

数据按时间顺序排列（从上市日到退市/最新日），与 calendars/day.txt 中的交易日对齐。

查看数据的方法
方法1：安装 qlib 后用 API 读取

```pip install qlib

import qlib
from qlib.data import D

qlib.init(provider_uri="C:/code/qlib_test/cn_data")

# 获取某只股票的全部特征
```df = D.features(
    ["BJ430017"],
    ["$close", "$volume", "$vwap"],
    start_time="2023-05-31",
    end_time="2024-07-31"
)
print(df)
方法2：直接解析 bin 文件

import struct
import os

def read_qlib_bin(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    n = len(data) // 8
    result = []
    for i in range(n):
        val, factor = struct.unpack('ff', data[i*8:(i+1)*8])
        result.append((val, factor))
    return result
```
# 读取复权收盘价
```cal = open('cn_data/calendars/day.txt').read().strip().split()
data = read_qlib_bin('cn_data/features/BJ430017/close.day.bin')
```
# 打印前5条
```for i in range(5):
    print(f"{cal[i]}: adj_close={data[i][0]:.2f}, factor={data[i][1]:.4f}")
```

简单来说：bin 格式 = 纯浮点数的二进制序列，每条记录 8 字节（值 + 复权因子），按交易日历顺序排列。