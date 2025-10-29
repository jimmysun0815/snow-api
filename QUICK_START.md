# 🚀 快速启动指南

## 方式 1: 一键启动（推荐）

```bash
./start.sh
```

这会自动：
1. 采集数据（如果没有）
2. 启动 API 服务
3. 打开浏览器显示前端页面

## 方式 2: 手动启动

### 步骤 1: 采集数据

```bash
source venv/bin/activate
python collect_data.py
```

### 步骤 2: 启动 API

```bash
python api.py
```

API 会在 `http://localhost:5000` 运行

### 步骤 3: 打开前端

在浏览器中打开 `index.html` 文件：
- macOS: `open index.html`
- 或直接双击 `index.html` 文件

---

## 📊 功能说明

### 前端页面
- **实时数据展示**: 所有雪场的运营状态、雪况、设施
- **天气 & 冰冻线**: 当前冰冻高度、24小时平均、7天预报
- **筛选功能**: 按状态筛选、搜索雪场
- **自动刷新**: 每5分钟自动刷新数据

### API 端点

```bash
# 获取所有雪场
curl http://localhost:5000/api/resorts

# 获取特定雪场
curl http://localhost:5000/api/resorts/1

# 获取开放的雪场
curl http://localhost:5000/api/resorts/open

# 按位置搜索
curl http://localhost:5000/api/resorts/search?location=Colorado

# 按名称搜索
curl http://localhost:5000/api/resorts/search?name=Vail
```

---

## 🔧 停止服务

找到 API 进程并停止：

```bash
# 查找进程
ps aux | grep api.py

# 停止进程
kill <PID>
```

或者直接按 `Ctrl+C` 如果在前台运行。

---

## 📁 文件说明

- `index.html` - 前端页面
- `api.py` - API 服务
- `collect_data.py` - 数据采集
- `resorts_config.json` - 雪场配置
- `data/latest.json` - 最新数据
- `start.sh` - 一键启动脚本

---

## 💡 提示

1. **首次使用**: 数据采集需要几分钟（39个雪场）
2. **定时更新**: 建议每3小时运行一次 `collect_data.py`
3. **网络问题**: 如果某些雪场采集失败，是正常的（网站保护机制）
4. **浏览器缓存**: 如果数据没更新，刷新浏览器（Cmd+R 或 F5）


