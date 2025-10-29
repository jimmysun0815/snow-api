#!/bin/bash
# 启动雪场数据监控系统

echo "======================================================================"
echo "❄️  雪场数据监控系统 - 启动"
echo "======================================================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 错误: 找不到虚拟环境"
    echo "请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查是否已有数据
if [ ! -f "data/latest.json" ]; then
    echo "📥 首次启动，正在采集数据..."
    python collect_data.py
    echo ""
fi

# 启动 API 服务
echo "🚀 启动 API 服务..."
python api.py &
API_PID=$!
echo "   API 进程 ID: $API_PID"
echo "   API 地址: http://localhost:8000"
echo ""

# 等待 API 启动
echo "⏳ 等待 API 启动..."
sleep 3

# 检查 API 是否运行
if curl -s http://localhost:8000/api/resorts > /dev/null 2>&1; then
    echo "✅ API 启动成功"
else
    echo "⚠️  API 可能需要更多时间启动，请稍候..."
fi

echo ""
echo "======================================================================"
echo "✅ 系统启动完成"
echo "======================================================================"
echo ""
echo "📊 访问方式:"
echo "   • 前端页面: file://${PWD}/index.html"
echo "   • 或在浏览器打开: index.html"
echo ""
echo "🔧 API 端点:"
echo "   • GET  http://localhost:8000/api/resorts"
echo "   • GET  http://localhost:8000/api/resorts/<id>"
echo "   • GET  http://localhost:8000/api/resorts/open"
echo ""
echo "⚙️  停止服务:"
echo "   kill $API_PID"
echo ""
echo "======================================================================"
echo ""

# 在 macOS 上自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🌐 正在打开浏览器..."
    open index.html
fi

# 保持脚本运行，显示日志
echo "📋 API 日志 (Ctrl+C 停止):"
echo "----------------------------------------------------------------------"
tail -f api.log 2>/dev/null || wait $API_PID

