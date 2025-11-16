-- 为 resorts 表添加营业时间字段

-- 添加营业时间相关字段
ALTER TABLE resorts 
ADD COLUMN IF NOT EXISTS opening_hours_weekday TEXT,
ADD COLUMN IF NOT EXISTS opening_hours_data JSONB,
ADD COLUMN IF NOT EXISTS is_open_now BOOLEAN DEFAULT NULL;

-- 添加注释
COMMENT ON COLUMN resorts.opening_hours_weekday IS '人类可读的每周营业时间（数组）';
COMMENT ON COLUMN resorts.opening_hours_data IS '详细营业时间数据（JSON格式，包含 periods）';
COMMENT ON COLUMN resorts.is_open_now IS '当前是否营业（可能为空）';

-- 查看字段
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'resorts'
  AND column_name IN ('opening_hours_weekday', 'opening_hours_data', 'is_open_now');

