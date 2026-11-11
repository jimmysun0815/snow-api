#!/usr/bin/env bash
# =====================================================
# 推送相关 Lambda 部署后的只读检查（不推送任何人、不改任何配置）
#
# 用法：AWS_PROFILE=pp ./scripts/verify_push_deploy.sh dev|prod
#
#   1. 推送 Lambda：环境变量齐全（只显示长度）+ 健康检查（Supabase RPC + Firebase dry_run）
#   2. snow-checker（只在 prod 检查，它只服务 Prod）：
#        环境变量齐全 + dry_run —— 列出「现在跑的话会提醒哪些雪场 / 多少人」，不写日志、不发送
# =====================================================
set -euo pipefail
ENV="${1:-}"
case "${ENV}" in
  dev)  FN=resort-data-sqs-notification-processor ;;
  prod) FN=resort-data-prod-notification-processor ;;
  *) echo "用法: $0 dev|prod"; exit 1 ;;
esac
R=(--region us-west-2)
T=$(mktemp -d); trap 'rm -rf "${T}"' EXIT
FAIL=0

check_env() {   # $1 = 函数名, 其余 = 必须存在且非空的变量
  local fn="$1"; shift
  local vars
  vars=$(aws lambda get-function-configuration --function-name "${fn}" "${R[@]}" --query 'Environment.Variables' --output json)
  for k in "$@"; do
    local n
    n=$(echo "${vars}" | jq -r --arg k "${k}" '.[$k] // "" | length')
    if [[ "${n}" == "0" ]]; then echo "  ❌ ${k} 缺失"; FAIL=1; else echo "  ✓ ${k} (len=${n})"; fi
  done
}

echo "== ${FN}"
aws lambda get-function-configuration --function-name "${FN}" "${R[@]}" --query '{modified:LastModified,status:LastUpdateStatus}' --output text
check_env "${FN}" SUPABASE_URL SUPABASE_SERVICE_KEY FIREBASE_PROJECT_ID FIREBASE_PRIVATE_KEY FIREBASE_CLIENT_EMAIL
echo '{"action":"healthcheck"}' > "${T}/hc.json"
aws lambda invoke --function-name "${FN}" --payload "fileb://${T}/hc.json" "${R[@]}" "${T}/hc_out.json" >/dev/null
HC=$(jq -r '.body' "${T}/hc_out.json")
echo "  healthcheck: ${HC}"
[[ "$(echo "${HC}" | jq -r '.supabase + "/" + .firebase')" == "ok/ok" ]] || FAIL=1

if [[ "${ENV}" == "prod" ]]; then
  SC=resort-data-snow-checker
  echo "== ${SC}"
  aws lambda get-function-configuration --function-name "${SC}" "${R[@]}" --query '{modified:LastModified,status:LastUpdateStatus}' --output text
  check_env "${SC}" DATABASE_URL SUPABASE_URL SUPABASE_SERVICE_KEY FIREBASE_PROJECT_ID FIREBASE_PRIVATE_KEY
  echo '{"dry_run":true}' > "${T}/dry.json"
  aws lambda invoke --function-name "${SC}" --payload "fileb://${T}/dry.json" "${R[@]}" "${T}/dry_out.json" >/dev/null
  BODY=$(jq -r '.body' "${T}/dry_out.json")
  echo "  dry_run: push_enabled=$(echo "${BODY}" | jq -r 'if has("push_enabled") then (.push_enabled|tostring) else "?" end')"
  echo "${BODY}" | jq -r '.alerts[]? | "    会提醒 \(.resort)：\(.snow_date) 预计 \(.snowfall_cm)cm → \(.users) 人"'
  echo "${BODY}" | jq -e '.alerts' >/dev/null || { echo "  ❌ dry_run 失败: ${BODY}"; FAIL=1; }
fi

if [[ "${FAIL}" == 0 ]]; then echo "✅ 全部通过"; else echo "❌ 有检查未通过"; exit 1; fi
