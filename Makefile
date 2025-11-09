.PHONY: help logs sqs-stats clean

# 默认目标
.DEFAULT_GOAL := help

# 变量
FUNCTION_NAME := $(shell cd terraform && terraform output -raw lambda_function_name 2>/dev/null || echo "resort-data-sqs-notification-processor")
S3_BUCKET := resort-data-lambda-artifacts-579866932024

help: ## 显示帮助信息
	@echo "可用的命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

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

clean: ## 清理临时文件
	@echo "🧹 清理临时文件..."
	@rm -rf lambda_package sqs-notification-processor.zip
	@echo "✅ 清理完成"
