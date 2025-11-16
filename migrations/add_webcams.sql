-- 为 resort_webcams 表创建摄像头数据表
-- 执行日期: 2025-11-15

CREATE TABLE IF NOT EXISTS resort_webcams (
    id SERIAL PRIMARY KEY,
    resort_id INTEGER NOT NULL REFERENCES resorts(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 摄像头标识
    webcam_uuid VARCHAR(100),
    title VARCHAR(300),
    
    -- 图片链接
    image_url TEXT,
    thumbnail_url TEXT,
    
    -- 视频流
    video_stream_url TEXT,
    webcam_type INTEGER,
    
    -- 状态
    is_featured BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP,
    
    -- 元数据
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_resort_webcams_resort_id ON resort_webcams(resort_id);
CREATE INDEX IF NOT EXISTS idx_resort_webcams_timestamp ON resort_webcams(timestamp);
CREATE INDEX IF NOT EXISTS idx_resort_webcams_uuid ON resort_webcams(webcam_uuid);

-- 添加注释
COMMENT ON TABLE resort_webcams IS '雪场摄像头数据表（时序数据）';
COMMENT ON COLUMN resort_webcams.webcam_uuid IS 'OnTheSnow 的摄像头 UUID';
COMMENT ON COLUMN resort_webcams.title IS '摄像头名称';
COMMENT ON COLUMN resort_webcams.image_url IS '高清图片链接';
COMMENT ON COLUMN resort_webcams.thumbnail_url IS '缩略图链接';
COMMENT ON COLUMN resort_webcams.video_stream_url IS '视频流链接（如 YouTube embed）';
COMMENT ON COLUMN resort_webcams.webcam_type IS '类型：0=静态图, 3=视频流';
COMMENT ON COLUMN resort_webcams.is_featured IS '是否为特色摄像头';
COMMENT ON COLUMN resort_webcams.last_updated IS '摄像头数据最后更新时间';

-- 验证表是否创建成功
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'resort_webcams'
ORDER BY ordinal_position;

