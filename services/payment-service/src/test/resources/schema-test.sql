DROP TABLE IF EXISTS billing_order;
CREATE TABLE billing_order (
  order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_no VARCHAR(64) UNIQUE,
  tenant_id BIGINT,
  plan_id BIGINT,
  pay_amount DECIMAL(12,2),
  pay_status VARCHAR(16),
  pay_channel VARCHAR(32),
  pay_trade_no VARCHAR(64),
  paid_at TIMESTAMP,
  effective_at TIMESTAMP,
  expire_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
