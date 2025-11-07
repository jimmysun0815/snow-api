# 静态配置设计说明

## 📋 设计原则

### 为什么海拔数据从配置文件读取？

**海拔数据（`elevation_min`, `elevation_max`）是雪场的静态属性，不会改变。**

传统方案是将这些数据存储在数据库中，但这会带来以下问题：
1. ❌ 修改配置需要更新数据库
2. ❌ 本地开发和远端生产环境数据不一致
3. ❌ 数据库迁移时需要额外处理
4. ❌ 配置更新不灵活

**新方案：配置文件 + 动态合并**

✅ 配置文件（`resorts_config.json`）作为唯一数据源
✅ API 返回时动态合并配置数据
✅ 数据库只存储动态数据（天气、雪况等）
✅ 修改配置文件后重启 API 即可生效

---

## 🏗️ 架构设计

```
┌─────────────────┐
│ resorts_config  │  ← 静态配置（海拔、位置、数据源等）
│     .json       │
└────────┬────────┘
         │
         │ 启动时加载到内存
         ↓
┌─────────────────┐     ┌──────────────┐
│   API Service   │────→│  PostgreSQL  │  ← 动态数据（天气、雪况）
│   (Flask)       │     │  Database    │
└────────┬────────┘     └──────────────┘
         │
         │ 返回前合并配置
         ↓
┌─────────────────┐
│  JSON Response  │  ← 完整数据（静态 + 动态）
└─────────────────┘
```

---

## 🔧 实现细节

### 1. 配置加载（启动时）

```python
# api.py
_resort_config_cache = None

def load_resort_config():
    """加载雪场配置文件（缓存）"""
    global _resort_config_cache
    if _resort_config_cache is not None:
        return _resort_config_cache
    
    config_path = os.path.join(os.path.dirname(__file__), 'resorts_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        # 转换为字典，以 ID 为 key
        _resort_config_cache = {
            resort['id']: resort 
            for resort in config_data.get('resorts', [])
        }
    return _resort_config_cache
```

### 2. 数据合并（每次请求）

```python
def merge_resort_config(resort_data):
    """将配置文件中的静态数据合并到雪场数据中"""
    config = load_resort_config()
    resort_id = resort_data.get('id')
    
    if resort_id and resort_id in config:
        resort_config = config[resort_id]
        # 合并海拔数据（优先使用配置文件）
        if 'elevation_min' in resort_config:
            resort_data['elevation_min'] = resort_config['elevation_min']
        if 'elevation_max' in resort_config:
            resort_data['elevation_max'] = resort_config['elevation_max']
    
    return resort_data
```

### 3. API 端点调用

```python
@app.route('/api/resorts', methods=['GET'])
def get_all_resorts():
    resorts = db_manager.get_all_resorts_data()
    # 合并配置数据
    resorts = [merge_resort_config(r) for r in resorts]
    return jsonify({'resorts': resorts})
```

---

## 📊 性能影响

| 操作 | 性能影响 | 说明 |
|------|---------|------|
| API 启动 | +50ms | 一次性加载配置文件到内存 |
| 单次请求 | +0.1ms | 内存查找，几乎无影响 |
| 内存占用 | +50KB | 72 个雪场的配置数据 |

**结论**：性能影响可以忽略不计，换来了极大的灵活性。

---

## 🎯 优势总结

### 对比传统方案

| 特性 | 传统方案（数据库） | 新方案（配置文件） |
|-----|------------------|-------------------|
| 修改海拔 | ❌ 需要 SQL 更新 | ✅ 修改 JSON 文件 |
| 数据一致性 | ❌ 本地/远端可能不同 | ✅ 配置文件统一管理 |
| 版本控制 | ❌ 需要迁移脚本 | ✅ Git 直接追踪 |
| 部署流程 | ❌ 需要更新数据库 | ✅ 只需重启 API |
| 可扩展性 | ❌ 需要修改表结构 | ✅ 只需修改 JSON |

### 适用场景

✅ **适合放在配置文件**：
- 海拔数据（elevation_min, elevation_max）
- 雪场位置（lat, lon）
- 数据源配置（data_source, source_url）
- 更新间隔（update_interval）
- 启用状态（enabled）

❌ **必须存数据库**：
- 天气数据（temperature, windspeed）
- 雪况数据（lifts_open, trails_open）
- 历史记录（时序数据）
- 用户相关数据

---

## 🚀 使用指南

### 修改雪场海拔

1. 编辑 `resorts_config.json`：
```json
{
  "id": 5,
  "name": "Stratton",
  "elevation_min": 582,    ← 修改这里
  "elevation_max": 1185,   ← 修改这里
  ...
}
```

2. 重启 API：
```bash
# 停止当前 API
kill <pid>

# 重新启动
python api.py
```

3. **无需任何数据库操作！**

### 添加新雪场

1. 在 `resorts_config.json` 中添加配置
2. 在数据库中插入基础记录（仅 id, name, slug）
3. 运行采集器获取动态数据
4. API 自动合并配置和数据

---

## 🔒 注意事项

1. **配置文件修改后必须重启 API**（使用缓存机制）
2. **配置文件优先级高于数据库**（会覆盖数据库中的海拔数据）
3. **远端部署时确保配置文件一致**（通过 Git 或 CI/CD 同步）

---

## 📝 未来扩展

可以考虑将更多静态配置迁移到配置文件：
- 雪场图片 URL
- 官方网站链接
- 营业时间模板
- 价格信息

**原则**：静态的、不常变的、需要版本控制的 → 配置文件

