# 添加雪场联系信息功能

## 功能概述

从 OnTheSnow 采集并保存雪场的联系信息：
- 地址（address）
- 城市（city）
- 邮编（zip_code）
- 电话（phone）
- 官网（website）

## 数据库迁移

### 本地开发环境

```bash
cd /Users/jimmysun/Desktop/workspace/resort-data/backend-api

# 执行迁移脚本
psql -h localhost -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f migrations/add_contact_info.sql
```

### 生产环境（RDS）

使用 AWS Systems Manager Session Manager 或本地 psql 通过 VPN 连接到 RDS：

```bash
# 方法1: 使用 psql（需要配置 VPN 或堡垒机）
psql -h <RDS_ENDPOINT> -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f migrations/add_contact_info.sql

# 方法2: 通过 AWS Lambda 执行（推荐）
# 创建一个临时 Lambda 函数执行迁移脚本
```

## 修改的文件

1. **models.py** - 添加了联系信息字段
   - `address` - 街道地址
   - `city` - 城市
   - `zip_code` - 邮编
   - `phone` - 电话
   - `website` - 官网

2. **normalizer.py** - 从 OnTheSnow 提取联系信息
   - 在 `_normalize_onthesnow` 方法中添加联系信息字段

3. **db_manager.py** - 保存和查询联系信息
   - `save_resort_data` - 更新雪场时保存联系信息
   - `get_latest_resort_data` - 查询时包含联系信息

4. **migrations/add_contact_info.sql** - 数据库迁移脚本

## 使用方法

### 重新采集数据以获取联系信息

```bash
cd /Users/jimmysun/Desktop/workspace/resort-data/backend-api

# 采集单个雪场（测试）
python3 collect_data.py --resort-id 612

# 采集所有雪场
python3 collect_data.py
```

### API 输出示例

```json
{
  "resort_id": 612,
  "name": "Mont Sutton",
  "slug": "mont-sutton",
  "location": "Quebec, Canada",
  "lat": 45.105336,
  "lon": -72.561525,
  "address": "671 Maple St.",
  "city": "Sutton",
  "zip_code": "J0E 2K0",
  "phone": "1-866-538-2545",
  "website": null,
  "status": "closed",
  "new_snow": 0,
  ...
}
```

## 数据源说明

- **OnTheSnow**: 可以获取完整的联系信息
- **MtnPowder**: 不包含联系信息，这些字段会保持为 `null`
- **Open-Meteo**: 只提供天气数据，不包含联系信息

## 注意事项

1. **数据可用性**: 并非所有雪场都有完整的联系信息，某些字段可能为 `null`
2. **数据更新**: 联系信息会在每次采集时自动更新
3. **向后兼容**: 新字段都是可选的，不会影响现有功能

