#!/bin/bash
# 自动分批采集所有雪场的雪道数据

set -e

BATCHES=7
BATCH_SIZE=50
FUNCTION_NAME="resort-data-trails-collector"
PROFILE="pp"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        🏔️  自动分批采集雪道数据                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "配置："
echo "  批次数量: $BATCHES"
echo "  每批大小: $BATCH_SIZE"
echo "  总雪场数: $((BATCHES * BATCH_SIZE))"
echo "  Lambda: $FUNCTION_NAME"
echo ""

read -p "确认开始? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 0
fi

echo ""
echo "🚀 开始采集..."
echo ""

# 创建结果目录
mkdir -p trails_batch_results

# 记录开始时间
START_TIME=$(date +%s)

for i in $(seq 1 $BATCHES); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 执行批次 $i/$BATCHES (雪场 $(((i-1)*BATCH_SIZE+1))-$((i*BATCH_SIZE)))"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    BATCH_START=$(date +%s)
    
    # 调用 Lambda
    aws lambda invoke \
        --function-name $FUNCTION_NAME \
        --payload "{\"limit\": $BATCH_SIZE}" \
        --profile $PROFILE \
        trails_batch_results/batch_${i}_response.json \
        --log-type Tail \
        --query 'LogResult' \
        --output text 2>/dev/null | base64 -d || true
    
    BATCH_END=$(date +%s)
    BATCH_DURATION=$((BATCH_END - BATCH_START))
    
    echo ""
    echo "📄 批次 $i 响应："
    cat trails_batch_results/batch_${i}_response.json | jq '.' 2>/dev/null || cat trails_batch_results/batch_${i}_response.json
    
    echo ""
    echo "⏱️  批次 $i 完成！用时: ${BATCH_DURATION} 秒"
    
    if [ $i -lt $BATCHES ]; then
        echo ""
        echo "⏳ 等待 10 秒后继续下一批..."
        sleep 10
        echo ""
    fi
done

# 计算总时间
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ 所有批次完成！                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 统计："
echo "  总批次数: $BATCHES"
echo "  每批大小: $BATCH_SIZE"
echo "  总耗时: ${MINUTES} 分 ${SECONDS} 秒"
echo ""
echo "📁 结果文件："
echo "  trails_batch_results/batch_*.json"
echo ""
echo "🔍 查看详细日志："
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --profile $PROFILE"
echo ""

