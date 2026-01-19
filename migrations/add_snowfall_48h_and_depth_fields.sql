-- 添加降雪48h和山顶积雪深度字段
-- 执行日期: 2026-01-17

-- 添加山顶积雪深度字段
ALTER TABLE resort_conditions 
ADD COLUMN IF NOT EXISTS snow_depth_summit FLOAT;

-- 添加未来48h降雪预测字段
ALTER TABLE resort_weather 
ADD COLUMN IF NOT EXISTS snowfall_48h FLOAT;

-- 添加注释
COMMENT ON COLUMN resort_conditions.snow_depth_summit IS '山顶积雪深度 (cm)';
COMMENT ON COLUMN resort_weather.snowfall_48h IS '未来48小时降雪预测 (cm)';

-- 验证字段是否添加成功
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'resort_conditions'
  AND column_name IN ('snow_depth_summit');

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'resort_weather'
  AND column_name IN ('snowfall_48h');
