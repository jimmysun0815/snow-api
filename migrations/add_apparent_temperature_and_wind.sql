-- 添加体感温度和风速/风向字段到 resort_weather 表
-- 执行日期: 2024-11-08

-- 添加体感温度字段
ALTER TABLE resort_weather ADD COLUMN IF NOT EXISTS apparent_temperature FLOAT;

-- 添加风速字段（用于前端显示）
ALTER TABLE resort_weather ADD COLUMN IF NOT EXISTS wind_speed FLOAT;

-- 添加风向字段（用于前端显示）
ALTER TABLE resort_weather ADD COLUMN IF NOT EXISTS wind_direction VARCHAR(10);

-- 添加注释
COMMENT ON COLUMN resort_weather.apparent_temperature IS '体感温度 (°C)';
COMMENT ON COLUMN resort_weather.wind_speed IS '风速 (km/h)';
COMMENT ON COLUMN resort_weather.wind_direction IS '风向 (N/S/E/W/NE/NW/SE/SW)';

-- 验证字段是否添加成功
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'resort_weather'
  AND column_name IN ('apparent_temperature', 'wind_speed', 'wind_direction');

