# ❄️ 雪场信息数据库系统

自动化采集北美主要滑雪场的实时数据，提供统一的 REST API 接口。

## 📁 项目结构

```
resort-data/
├── collectors/              # 采集器模块
│   ├── __init__.py
│   ├── base.py             # 采集器基类
│   ├── mtnpowder.py        # MtnPowder API 采集器
│   └── onthesnow.py        # OnTheSnow 网页采集器
├── normalizer.py           # 数据标准化器
├── resort_manager.py       # 雪场数据管理器
├── collect_data.py         # 数据采集主程序
├── api.py                  # REST API 服务
├── resorts_config.json     # 雪场配置文件
├── requirements.txt        # Python 依赖
├── data/                   # 数据存储目录
│   └── latest.json         # 最新数据
└── README.md               # 本文件
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置雪场列表

编辑 `resorts_config.json`，添加或修改雪场配置：

```json
{
  "id": 1,
  "name": "雪场名称",
  "slug": "resort-slug",
  "data_source": "onthesnow",
  "source_url": "https://www.onthesnow.com/...",
  "enabled": true
}
```

### 3. 采集数据

```bash
# 采集所有已启用的雪场
python collect_data.py

# 采集所有雪场（包括未启用的）
python collect_data.py --all

# 只采集指定 ID 的雪场
python collect_data.py --resort-id 1
```

### 4. 启动 API 服务

```bash
python api.py
```

API 将在 `http://localhost:5000` 启动。

## 📡 API 接口

### 获取所有雪场

```http
GET /api/resorts
```

**响应示例：**

```json
{
  "metadata": {
    "timestamp": "2025-10-28T13:00:00",
    "total_resorts": 4
  },
  "resorts": [
    {
      "resort_id": 1,
      "name": "Mammoth Mountain",
      "status": "closed",
      "new_snow": 0,
      "lifts_open": 0,
      "lifts_total": 24,
      ...
    }
  ]
}
```

### 获取单个雪场（by ID）

```http
GET /api/resorts/1
```

### 获取单个雪场（by slug）

```http
GET /api/resorts/slug/mammoth-mountain
```

### 获取开放的雪场

```http
GET /api/resorts/open
```

### 查询附近的雪场

```http
GET /api/resorts/nearby?lat=50.1157&lon=-122.9485&radius=100
```

**参数：**
- `lat`: 纬度
- `lon`: 经度
- `radius`: 半径（km，默认 100）

### 获取系统状态

```http
GET /api/status
```

## 🗂️ 数据格式

标准化后的雪场数据格式：

```json
{
  "resort_id": 1,
  "name": "Mammoth Mountain",
  "location": "California, USA",
  "lat": 37.6308,
  "lon": -119.0326,
  "status": "open|partial|closed",
  "new_snow": 0,
  "base_depth": 0,
  "lifts_open": 0,
  "lifts_total": 24,
  "trails_open": 0,
  "trails_total": 180,
  "temperature": 15,
  "last_update": "2025-10-28T13:00:00",
  "source": "https://...",
  "data_source": "mtnpowder|onthesnow"
}
```

## 🔧 支持的数据源

### 1. MtnPowder API

- **适用雪场**: Mammoth Mountain 等
- **数据质量**: ⭐⭐⭐⭐⭐
- **更新频率**: 实时
- **配置示例**:

```json
{
  "data_source": "mtnpowder",
  "source_id": "60"
}
```

### 2. OnTheSnow 网页

- **适用雪场**: 大部分北美雪场
- **数据质量**: ⭐⭐⭐⭐
- **更新频率**: 每日
- **配置示例**:

```json
{
  "data_source": "onthesnow",
  "source_url": "https://www.onthesnow.com/..."
}
```

## 📊 已验证的雪场

| 雪场 | 位置 | 数据源 | 状态 |
|------|------|--------|------|
| Mammoth Mountain | California, USA | MtnPowder | ✅ |
| Whistler Blackcomb | BC, Canada | OnTheSnow | ✅ |
| Cypress Mountain | BC, Canada | OnTheSnow | ✅ |
| Grouse Mountain | BC, Canada | OnTheSnow | ✅ |

## 🔄 定时采集

使用 cron 定时采集数据（建议每 3 小时）：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每 3 小时执行一次）
0 */3 * * * cd /path/to/resort-data && python3 collect_data.py
```

## 📝 添加新雪场

1. 在 `resorts_config.json` 中添加配置
2. 设置 `enabled: true`
3. 运行采集测试: `python collect_data.py --resort-id <ID>`
4. 验证数据格式正确

## ⚠️ 注意事项

1. **遵守爬虫礼仪**
   - 请求间隔 ≥ 3 小时
   - 设置合适的 User-Agent
   - 遵守 robots.txt

2. **数据准确性**
   - 非雪季数据可能不完整
   - 建议多数据源交叉验证

3. **错误处理**
   - 采集失败会自动跳过
   - 查看日志排查问题

## 📄 许可证

本项目仅用于学习和研究目的。使用时请遵守相关网站的服务条款。


