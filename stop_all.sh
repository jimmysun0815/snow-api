#!/bin/bash
# 完全停止所有相关进程

echo "========================================================================"
echo "🛑 停止所有服务"
echo "========================================================================"
echo ""

# 1. 停止所有占用 8000 端口的进程
echo "1️⃣  查找占用 8000 端口的进程..."
PORT_PIDS=$(lsof -ti:8000 2>/dev/null)

if [ ! -z "$PORT_PIDS" ]; then
    echo "   找到进程: $PORT_PIDS"
    for pid in $PORT_PIDS; do
        echo "   停止 PID: $pid"
        kill -9 $pid 2>/dev/null
    done
    echo "   ✅ 已停止所有 8000 端口进程"
else
    echo "   ℹ️  没有进程占用 8000 端口"
fi

echo ""

# 2. 停止所有 api.py 进程
echo "2️⃣  查找所有 api.py 进程..."
API_PIDS=$(ps aux | grep "[a]pi.py" | awk '{print $2}')

if [ ! -z "$API_PIDS" ]; then
    echo "   找到进程: $API_PIDS"
    for pid in $API_PIDS; do
        echo "   停止 PID: $pid"
        kill -9 $pid 2>/dev/null
    done
    echo "   ✅ 已停止所有 api.py 进程"
else
    echo "   ℹ️  没有 api.py 进程在运行"
fi

echo ""

# 3. 停止所有 start.sh 进程
echo "3️⃣  查找所有 start.sh 进程..."
START_PIDS=$(ps aux | grep "[s]tart.sh" | awk '{print $2}')

if [ ! -z "$START_PIDS" ]; then
    echo "   找到进程: $START_PIDS"
    for pid in $START_PIDS; do
        echo "   停止 PID: $pid"
        kill -9 $pid 2>/dev/null
    done
    echo "   ✅ 已停止所有 start.sh 进程"
else
    echo "   ℹ️  没有 start.sh 进程在运行"
fi

echo ""

# 4. 验证
echo "4️⃣  验证..."
sleep 1

if lsof -ti:8000 > /dev/null 2>&1; then
    echo "   ⚠️  警告: 8000 端口仍被占用"
    echo "   请手动检查: lsof -i:8000"
else
    echo "   ✅ 8000 端口已释放"
fi

echo ""
echo "========================================================================"
echo "✅ 清理完成"
echo "========================================================================"
echo ""
echo "💡 重新启动服务:"
echo "   ./start.sh"
echo ""

