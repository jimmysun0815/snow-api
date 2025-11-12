# 并发采集测试指南

## 🚀 本地测试

1. **激活虚拟环境**:
   ```bash
   source venv/bin/activate
   ```

2. **设置 Open-Meteo API Key** (可选，但强烈推荐):
   ```bash
   export OPENMETEO_API_KEY="your-api-key-here"
   ```

3. **运行测试**:
   ```bash
   python test_concurrent_collection.py
   ```

## 📊 优化说明

### 已完成的优化:
1. ✅ **多线程并发**: 默认 20 个线程同时采集
2. ✅ **移除所有延迟**: base collector 的 `random_delay()` 已禁用
3. ✅ **Open-Meteo API Key**: 使用付费 API，无速率限制
4. ✅ **进度显示**: 实时显示采集进度

### 预期性能:
- **串行采集** (旧方法): ~每个雪场 4-5 秒 = 300 个雪场需要 20-25 分钟
- **并发采集** (新方法): ~每个雪场 0.3-0.5 秒 = 300 个雪场需要 2-3 分钟

## ⚙️ 配置参数

在 `resort_manager.py` 的 `collect_all()` 方法中:
- `max_workers`: 并发线程数（默认 20）
- 可以根据网络情况调整

## 📝 测试步骤

1. 先测试 20 个雪场，观察:
   - 总耗时
   - 成功率
   - 平均每个雪场耗时

2. 根据结果估算全部采集时间

3. 如果估算时间 < 14 分钟，可以全量采集

## 🔄 部署到 Lambda

代码已自动同步到 GitHub Actions 部署流程，推送到 main 分支后会自动部署。

## ⚠️ 注意事项

1. **Lambda 超时**: 最大 15 分钟，建议控制在 14 分钟内
2. **并发数**: 20 线程是一个平衡点，太多可能导致网络拥堵
3. **API Key**: 必须设置 OPENMETEO_API_KEY，否则会触发速率限制
