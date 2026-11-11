#!/usr/bin/env bash
# =====================================================
# 恢复 Dev 推送 Lambda（resort-data-sqs-notification-processor）的凭证
#
# 背景：2026-11-06 21:46Z 本地 terraform apply 用 terraform.tfvars 的旧值覆盖了
#       SUPABASE_SERVICE_KEY / FIREBASE_PRIVATE_KEY → Dev 推送 401 + 私钥解析失败。
# 做法：恢复成 deploy.yml（GitHub Secrets）写入的值 ——
#       SUPABASE_SERVICE_KEY 取自 resort-data-api（同一个 secrets.SUPABASE_SERVICE_KEY，同为 Dev 项目）
#       FIREBASE_*           取自 resort-data-snow-checker（同一组 secrets.FIREBASE_*）
#       其它变量保持不变。值不会打印，临时文件 600 权限、用完即删。
#
# 用法：AWS_PROFILE=pp ./scripts/restore_dev_push_lambda_env.sh
# =====================================================
set -euo pipefail
umask 077
R=(--region us-west-2)
FN=resort-data-sqs-notification-processor
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

DEV_URL=$(aws lambda get-function-configuration --function-name "$FN" "${R[@]}" --query 'Environment.Variables.SUPABASE_URL' --output text)
API_URL=$(aws lambda get-function-configuration --function-name resort-data-api "${R[@]}" --query 'Environment.Variables.SUPABASE_URL' --output text)
if [[ "$DEV_URL" != *avztlsrmiqigeivtmwha* || "$API_URL" != "$DEV_URL" ]]; then
  echo "❌ SUPABASE_URL 不一致（dev=$DEV_URL api=$API_URL），停止"; exit 1
fi

aws lambda get-function-configuration --function-name resort-data-api "${R[@]}" --query 'Environment.Variables' --output json > "$T/api.json"
aws lambda get-function-configuration --function-name resort-data-snow-checker "${R[@]}" --query 'Environment.Variables' --output json > "$T/snow.json"
aws lambda get-function-configuration --function-name "$FN" "${R[@]}" --query 'Environment.Variables' --output json > "$T/dev.json"

jq -n --slurpfile a "$T/api.json" --slurpfile s "$T/snow.json" --slurpfile d "$T/dev.json" \
  '{Variables: ($d[0]
     + {SUPABASE_SERVICE_KEY: $a[0].SUPABASE_SERVICE_KEY}
     + ($s[0] | with_entries(select(.key | startswith("FIREBASE_")))))}' > "$T/new.json"

echo "将写入（只显示长度）："
jq -r '.Variables | to_entries[] | "  \(.key) len=\(.value | length)"' "$T/new.json"

aws lambda update-function-configuration --function-name "$FN" --environment "file://$T/new.json" "${R[@]}" --query 'LastModified' --output text
aws lambda wait function-updated --function-name "$FN" "${R[@]}"
echo "✅ 已恢复"

echo "== 冒烟测试（随机 user_id，没有设备，期望 status=skipped）"
printf '{"user_id":"%s","notification_type":"smoke_test","title":"smoke","body":"smoke","data":{"type":"smoke_test"}}' \
  "$(uuidgen | tr 'A-Z' 'a-z')" > "$T/ev.json"
aws lambda invoke --function-name "$FN" --payload "fileb://$T/ev.json" "${R[@]}" "$T/out.json" --query 'FunctionError' --output text
cat "$T/out.json"; echo
