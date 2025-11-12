#!/bin/bash
# 刷新 EventBridge 规则，确保使用最新的 Lambda 版本

set -e

echo "🔄 刷新 EventBridge 规则..."
echo ""

RULE_NAME="resort-data-data-collection"
PROFILE="pp"
REGION="us-west-2"

echo "1️⃣  禁用规则..."
aws events disable-rule \
  --name "$RULE_NAME" \
  --profile "$PROFILE" \
  --region "$REGION"

echo "✅ 规则已禁用"
echo ""

echo "2️⃣  等待 3 秒..."
sleep 3

echo "3️⃣  启用规则..."
aws events enable-rule \
  --name "$RULE_NAME" \
  --profile "$PROFILE" \
  --region "$REGION"

echo "✅ 规则已启用"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 完成！"
echo ""
echo "现在 EventBridge 定时任务应该会使用最新的 Lambda 代码并生成报告了。"
echo ""
echo "您可以手动触发一次来测试："
echo "  aws events put-events --entries '[{\"Source\":\"manual\",\"DetailType\":\"Test\",\"Detail\":\"{}\"}]' --profile $PROFILE --region $REGION"
echo ""

