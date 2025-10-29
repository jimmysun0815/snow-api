#!/bin/bash
# 重启 API 服务

echo "🔄 重启 API 服务..."
echo ""

# 查找并停止现有的 API 进程
API_PID=$(lsof -ti:8000)

if [ ! -z "$API_PID" ]; then
    echo "⏹️  停止现有 API 进程 (PID: $API_PID)..."
    kill $API_PID
    sleep 2
    echo "✅ 已停止"
else
    echo "ℹ️  没有运行中的 API 进程"
fi

echo ""

# 激活虚拟环境并启动 API
echo "🚀 启动 API 服务..."
cd /Users/jimmysun/Desktop/workspace/resort-data
source venv/bin/activate
python api.py > api.log 2>&1 &

NEW_PID=$!
echo "✅ API 已启动 (PID: $NEW_PID)"
echo "📍 API 地址: http://localhost:8000"
echo ""

# 等待并验证
sleep 2
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ API 运行正常"
else
    echo "❌ API 启动失败，请检查日志:"
    echo "   tail -f api.log"
fi

echo ""
echo "💡 查看日志: tail -f api.log"
echo "💡 停止服务: kill $NEW_PID"

