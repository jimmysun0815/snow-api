#!/usr/bin/env bash
# 把 5 个 Lambda 从 RDS/ElastiCache 切到 Supabase（2026-11）
#
#   scripts/cutover_lambdas.sh status     # 只看当前状态，不改任何东西
#   scripts/cutover_lambdas.sh switch     # 备份 → 改环境变量 → 移出 VPC
#   scripts/cutover_lambdas.sh rollback   # 按备份恢复环境变量和 VPC
#
# 为什么不用 terraform apply：terraform 会整体覆盖环境变量，而线上 Lambda 里有
# 很多 key 不在 terraform 里（SUPABASE_*、OPENMETEO_API_KEY、FIREBASE_* …），
# 直接 apply 会把它们清掉。这里的做法是「在现有环境变量上增删」，其余原样保留。
#
# DATABASE_URL 从 terraform/terraform.tfvars 的 database_url 读取（不经过命令行，
# 避免进 shell 历史）。备份写在 .cutover_backup/（已 gitignore，里面有密钥）。
set -euo pipefail

REGION=us-west-2
FUNCTIONS=(
  resort-data-snow-checker
  resort-data-trails-collector
  resort-data-contact-collector
  resort-data-collector
  resort-data-api
)
# 切换后要删掉的旧 key：有 REDIS_* 代码就会去连已经够不着的 ElastiCache
DROP_KEYS='["POSTGRES_HOST","POSTGRES_PORT","POSTGRES_USER","POSTGRES_PASSWORD","POSTGRES_DB","DB_HOST","DB_NAME","DB_USER","DB_PASSWORD","REDIS_HOST","REDIS_PORT","REDIS_DB","REDIS_URL"]'

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$ROOT/.cutover_backup"

cfg() { aws lambda get-function-configuration --region "$REGION" --function-name "$1"; }
wait_ready() { aws lambda wait function-updated --region "$REGION" --function-name "$1"; }

status() {
  for fn in "${FUNCTIONS[@]}"; do
    cfg "$fn" | jq -r --arg fn "$fn" '
      "\($fn)\n  VPC 子网: \(.VpcConfig.SubnetIds // [] | length)  状态: \(.State)/\(.LastUpdateStatus)\n  环境变量: \(.Environment.Variables // {} | keys | join(", "))"'
  done
}

read_database_url() {
  local url
  url=$(sed -n 's/^[[:space:]]*database_url[[:space:]]*=[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p' "$ROOT/terraform/terraform.tfvars")
  if [[ -z "$url" || "$url" != *pooler.supabase.com:6543* ]]; then
    echo "❌ terraform.tfvars 里的 database_url 缺失或不是 Supabase transaction pooler（…pooler.supabase.com:6543）" >&2
    exit 1
  fi
  printf '%s' "$url"
}

switch() {
  local url; url=$(read_database_url)
  mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"

  # 先全部备份，任何一个拿不到就不动手
  for fn in "${FUNCTIONS[@]}"; do
    if [[ -f "$BACKUP_DIR/$fn.json" ]]; then
      echo "ℹ️  $fn 已有备份，保留第一次的（不覆盖）"
    else
      cfg "$fn" > "$BACKUP_DIR/$fn.json"
      echo "💾 已备份 $fn"
    fi
  done

  for fn in "${FUNCTIONS[@]}"; do
    echo "── $fn"
    # 1) 环境变量：此时还在 VPC 里，经 NAT 也能连到 Supabase，所以先改这个不会断
    cfg "$fn" | jq --arg url "$url" --argjson drop "$DROP_KEYS" \
      '{Variables: ((.Environment.Variables // {}) | with_entries(select(.key as $k | $drop | index($k) | not)) + {DATABASE_URL: $url})}' \
      > "$BACKUP_DIR/.env.tmp.json"
    aws lambda update-function-configuration --region "$REGION" --function-name "$fn" \
      --environment "file://$BACKUP_DIR/.env.tmp.json" > /dev/null
    rm -f "$BACKUP_DIR/.env.tmp.json"
    wait_ready "$fn"
    echo "   ✅ 环境变量已切到 Supabase"

    # 2) 移出 VPC
    aws lambda update-function-configuration --region "$REGION" --function-name "$fn" \
      --vpc-config '{"SubnetIds":[],"SecurityGroupIds":[]}' > /dev/null
    wait_ready "$fn"
    echo "   ✅ 已移出 VPC"
  done
  echo; status
}

rollback() {
  for fn in "${FUNCTIONS[@]}"; do
    local b="$BACKUP_DIR/$fn.json"
    [[ -f "$b" ]] || { echo "⚠️  $fn 没有备份，跳过"; continue; }
    echo "── $fn"
    jq '{Variables: (.Environment.Variables // {})}' "$b" > "$BACKUP_DIR/.env.tmp.json"
    aws lambda update-function-configuration --region "$REGION" --function-name "$fn" \
      --environment "file://$BACKUP_DIR/.env.tmp.json" \
      --vpc-config "$(jq -c '{SubnetIds: (.VpcConfig.SubnetIds // []), SecurityGroupIds: (.VpcConfig.SecurityGroupIds // [])}' "$b")" \
      > /dev/null
    rm -f "$BACKUP_DIR/.env.tmp.json"
    wait_ready "$fn"
    echo "   ↩️  已恢复"
  done
  echo; status
}

case "${1:-}" in
  status) status ;;
  switch) switch ;;
  rollback) rollback ;;
  *) sed -n '2,7p' "$0"; exit 1 ;;
esac
