-- =====================================================================
-- StarRocks 数据库初始化
-- 适用版本: StarRocks 3.1+ (推荐 3.2 LTS)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS steel_dw
PROPERTIES (
    "replication_num" = "3",
    "default_storage_medium" = "SSD"
);

USE steel_dw;

-- 角色与账号(只读账号给 query-engine 微服务)
CREATE ROLE IF NOT EXISTS role_query_readonly;
GRANT SELECT ON DATABASE steel_dw TO ROLE role_query_readonly;

-- ETL 写入账号
CREATE ROLE IF NOT EXISTS role_etl_writer;
GRANT ALL ON DATABASE steel_dw TO ROLE role_etl_writer;
