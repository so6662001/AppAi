-- =====================================================================
-- 租户级通知渠道配置
-- 调度器/早报/风控告警 推送时, 从这里读取各租户 webhook/SMTP/AppID 等
-- =====================================================================
USE steel_chat;

CREATE TABLE IF NOT EXISTS tenant_notify_config (
  config_id     BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id     BIGINT       NOT NULL,
  channel       VARCHAR(16)  NOT NULL,          -- WECOM/DINGTALK/EMAIL/UNI_PUSH/SMS/INAPP
  name          VARCHAR(128),                   -- 配置名称, 如 "销售大区群机器人"
  config_json   JSON         NOT NULL,          -- 各渠道差异化字段
       /*
         WECOM   : {"webhook":"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
                    "mention_mobiles":["13800000000"]}
         DINGTALK: {"webhook":"https://oapi.dingtalk.com/robot/send?access_token=xxx",
                    "secret":"SECxxx"}
         EMAIL   : {"smtp_host":"smtp.exmail.qq.com","smtp_port":465,
                    "smtp_user":"x@x.com","smtp_pass":"***","from":"x@x.com",
                    "default_recipients":["a@x.com","b@x.com"]}
         UNI_PUSH: {"uni_push_url":"https://restapi.getui.com/v2/push/...",
                    "appid":"xxx","appkey":"xxx","token":"xxx"}
         SMS     : {"provider":"aliyun","access_key_id":"xxx","secret":"xxx",
                    "sign_name":"钢铁经营","template_code":"SMS_xxx"}
       */
  is_default    TINYINT      DEFAULT 0,         -- 同一租户 + channel 至多一个 default
  is_active     TINYINT      DEFAULT 1,
  tags          JSON,                            -- 标签, 报表可选 "勾选 sales 群"
  created_by    VARCHAR(64),
  created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (config_id),
  KEY idx_tenant_channel (tenant_id, channel, is_active),
  KEY idx_tenant_default (tenant_id, channel, is_default)
) ENGINE=InnoDB COMMENT='租户级通知渠道配置 (webhook/SMTP/AppID 等)';
