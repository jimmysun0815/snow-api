#!/bin/bash
# 雪场数据监控 - 启动本地 Web 服务器查看报告

PORT=8888
DATA_DIR="data"
HTML_FILE="monitor_report.html"

echo "======================================================================"
echo "❄️  雪场数据监控系统"
echo "======================================================================"
echo ""

# 检查 HTML 报告是否存在
if [ ! -f "$DATA_DIR/$HTML_FILE" ]; then
    echo "⚠️  监控报告不存在，正在生成..."
    python3 monitor.py --data-file $DATA_DIR/latest.json --html
    echo ""
fi

echo "🚀 启动 Web 服务器..."
echo "📊 监控报告地址: http://localhost:$PORT/$HTML_FILE"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "======================================================================"
echo ""

# 启动简单的 HTTP 服务器
cd $DATA_DIR
python3 -m http.server $PORT

