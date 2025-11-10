-- 为 resorts 表添加联系信息字段
-- 执行日期: 2025-11-10

ALTER TABLE resorts
ADD COLUMN address VARCHAR(500),
ADD COLUMN city VARCHAR(200),
ADD COLUMN zip_code VARCHAR(50),
ADD COLUMN phone VARCHAR(100),
ADD COLUMN website TEXT;

-- 添加注释
COMMENT ON COLUMN resorts.address IS '雪场街道地址';
COMMENT ON COLUMN resorts.city IS '雪场所在城市';
COMMENT ON COLUMN resorts.zip_code IS '邮政编码';
COMMENT ON COLUMN resorts.phone IS '联系电话';
COMMENT ON COLUMN resorts.website IS '官方网站';

