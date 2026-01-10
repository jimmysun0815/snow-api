.PHONY: help logs sqs-stats clean update-trails update-trails-single build-trails-lambda deploy-trails-lambda invoke-trails-test invoke-trails-all build-notification-lambda deploy-notification-dev deploy-notification-prod deploy-notification-all notification-dev-logs notification-prod-logs

# 默认目标
.DEFAULT_GOAL := help

# 变量
FUNCTION_NAME := $(shell cd terraform && terraform output -raw lambda_function_name 2>/dev/null || echo "resort-data-sqs-notification-processor")
S3_BUCKET := resort-data-lambda-artifacts-579866932024
TRAILS_FUNCTION := resort-data-trails-collector
DEV_NOTIFICATION_FUNCTION := resort-data-sqs-notification-processor
PROD_NOTIFICATION_FUNCTION := resort-data-prod-notification-processor

help: ## 显示帮助信息
	@echo "可用的命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

logs: ## 查看 Lambda 日志
	@echo "📜 查看 Lambda 日志..."
	@aws logs tail /aws/lambda/$(FUNCTION_NAME) --follow --profile pp

sqs-stats: ## 查看 SQS 队列统计
	@echo "📊 SQS 队列统计..."
	@aws sqs get-queue-attributes \
		--queue-url $(shell cd terraform && terraform output -raw sqs_queue_url) \
		--attribute-names All \
		--profile pp \
		| jq '.Attributes'

update-trails: ## 更新生产环境所有雪场的trail数据
	@echo "🏔️  更新生产环境雪道数据..."
	@python3 update_prod_trails.py

update-trails-test: ## 测试更新(只更新前5个雪场)
	@echo "🧪 测试更新前5个雪场..."
	@python3 update_prod_trails.py --limit 5 --skip-verify

update-trails-single: ## 更新单个雪场 (使用: make update-trails-single RESORT_ID=123)
	@echo "🎯 更新单个雪场 ID=$(RESORT_ID)..."
	@python3 update_prod_trails.py --resort-id $(RESORT_ID)

build-trails-lambda: ## 打包 Trail Collector Lambda
	@echo "📦 打包 Trail Collector Lambda..."
	@./build_trails_lambda.sh

deploy-trails-lambda: build-trails-lambda ## 部署 Trail Collector Lambda 到 AWS
	@echo "🚀 上传到 S3..."
	@aws s3 cp trails-collector-lambda.zip s3://$(S3_BUCKET)/trails-collector-lambda.zip --profile pp
	@echo "🔄 更新 Lambda 函数..."
	@aws lambda update-function-code \
		--function-name $(TRAILS_FUNCTION) \
		--s3-bucket $(S3_BUCKET) \
		--s3-key trails-collector-lambda.zip \
		--profile pp
	@echo "✅ 部署完成！"

invoke-trails-test: ## 测试运行 Trail Collector (采集5个雪场)
	@echo "🧪 测试运行 Trail Collector..."
	@aws lambda invoke \
		--function-name $(TRAILS_FUNCTION) \
		--payload '{"limit": 5}' \
		--profile pp \
		trails_test_response.json
	@echo ""
	@echo "📄 响应:"
	@cat trails_test_response.json | jq '.'

invoke-trails-batch: ## 分批采集雪道 (使用: make invoke-trails-batch LIMIT=50)
	@echo "📊 批量采集雪道数据 (limit=$(LIMIT))..."
	@aws lambda invoke \
		--function-name $(TRAILS_FUNCTION) \
		--payload '{"limit": $(LIMIT)}' \
		--profile pp \
		trails_batch_response.json
	@cat trails_batch_response.json | jq '.'

invoke-trails-all: ## 采集所有雪场的雪道数据
	@echo "⚠️  警告: 将采集所有309个雪场，需要分批执行"
	@echo "建议使用: make invoke-trails-batch LIMIT=50"

trails-logs: ## 查看 Trail Collector 日志
	@echo "📜 查看 Trail Collector 日志..."
	@aws logs tail /aws/lambda/$(TRAILS_FUNCTION) --follow --profile pp

# =====================================================
# Notification Lambda 部署
# =====================================================

build-notification-lambda: ## 打包 Notification Processor Lambda
	@echo "📦 打包 Notification Processor Lambda..."
	@rm -rf lambda_package sqs-notification-processor.zip
	@mkdir -p lambda_package
	@cp sqs_notification_processor.py push_service.py lambda_package/
	@pip3 install -r requirements.txt -t lambda_package/ --quiet
	@cd lambda_package && zip -r ../sqs-notification-processor.zip . -q
	@echo "✅ 打包完成: sqs-notification-processor.zip"

deploy-notification-dev: build-notification-lambda ## 部署 Dev 通知 Lambda
	@echo "🚀 部署 Dev Notification Lambda..."
	@aws s3 cp sqs-notification-processor.zip s3://$(S3_BUCKET)/ --profile pp
	@aws lambda update-function-code \
		--function-name $(DEV_NOTIFICATION_FUNCTION) \
		--s3-bucket $(S3_BUCKET) \
		--s3-key sqs-notification-processor.zip \
		--profile pp
	@echo "✅ Dev Notification Lambda 部署完成！"

deploy-notification-prod: build-notification-lambda ## 部署 Prod 通知 Lambda
	@echo "🚀 部署 Prod Notification Lambda..."
	@aws s3 cp sqs-notification-processor.zip s3://$(S3_BUCKET)/ --profile pp
	@aws lambda update-function-code \
		--function-name $(PROD_NOTIFICATION_FUNCTION) \
		--s3-bucket $(S3_BUCKET) \
		--s3-key sqs-notification-processor.zip \
		--profile pp
	@echo "✅ Prod Notification Lambda 部署完成！"

deploy-notification-all: build-notification-lambda ## 同时部署 Dev 和 Prod 通知 Lambda
	@echo "🚀 部署所有 Notification Lambda..."
	@aws s3 cp sqs-notification-processor.zip s3://$(S3_BUCKET)/ --profile pp
	@echo "🔄 更新 Dev Lambda..."
	@aws lambda update-function-code \
		--function-name $(DEV_NOTIFICATION_FUNCTION) \
		--s3-bucket $(S3_BUCKET) \
		--s3-key sqs-notification-processor.zip \
		--profile pp > /dev/null
	@echo "🔄 更新 Prod Lambda..."
	@aws lambda update-function-code \
		--function-name $(PROD_NOTIFICATION_FUNCTION) \
		--s3-bucket $(S3_BUCKET) \
		--s3-key sqs-notification-processor.zip \
		--profile pp > /dev/null
	@echo "✅ 所有 Notification Lambda 部署完成！"

notification-dev-logs: ## 查看 Dev Notification Lambda 日志
	@echo "📜 查看 Dev Notification Lambda 日志..."
	@aws logs tail /aws/lambda/$(DEV_NOTIFICATION_FUNCTION) --follow --profile pp

notification-prod-logs: ## 查看 Prod Notification Lambda 日志
	@echo "📜 查看 Prod Notification Lambda 日志..."
	@aws logs tail /aws/lambda/$(PROD_NOTIFICATION_FUNCTION) --follow --profile pp

clean: ## 清理临时文件
	@echo "🧹 清理临时文件..."
	@rm -rf lambda_package trails_lambda_package sqs-notification-processor.zip trails-collector-lambda.zip
	@rm -f trails_test_response.json trails_batch_response.json
	@echo "✅ 清理完成"
