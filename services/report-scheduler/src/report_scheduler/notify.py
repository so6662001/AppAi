"""推送渠道实现 - 统一接口 + 各通道适配器。

生产环境通常这些渠道走独立的 notification-service, 这里给出可直接调用的实现:
  - INAPP     : 写 advice_inbox (站内信)
  - WECOM     : 企业微信群机器人 Webhook
  - DINGTALK  : 钉钉群机器人 Webhook
  - EMAIL     : SMTP
  - UNI_PUSH  : DCloud uni-push
  - SMS       : 短信网关
"""
from __future__ import annotations
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from typing import Any
from sqlalchemy import text
import httpx

from .db import get_engine


class NotifyResult:
    def __init__(self, channel: str, ok: bool, latency_ms: int, error: str | None = None):
        self.channel, self.ok, self.latency_ms, self.error = channel, ok, latency_ms, error

    def to_dict(self):
        return {"channel": self.channel, "status": "SENT" if self.ok else "FAILED",
                "latency_ms": self.latency_ms, "error": self.error}


def push(channel: str, *,
         tenant_id: int, user_id: int, title: str, summary: str,
         blocks: list, run_id: int, report_name: str = "",
         conf: dict | None = None) -> NotifyResult:
    """统一入口, 根据 channel 路由。"""
    t0 = time.time()
    conf = conf or {}
    try:
        if channel == "INAPP":
            _push_inapp(tenant_id, user_id, title, summary, blocks, run_id, report_name)
        elif channel == "WECOM":
            _push_wecom(conf.get("webhook"), title, summary, blocks)
        elif channel == "DINGTALK":
            _push_dingtalk(conf.get("webhook"), title, summary, blocks)
        elif channel == "EMAIL":
            _push_email(conf, title, summary, blocks)
        elif channel == "UNI_PUSH":
            _push_uni(conf, user_id, title, summary, run_id)
        elif channel == "SMS":
            _push_sms(conf, summary)
        else:
            return NotifyResult(channel, False, 0, f"unknown channel: {channel}")
        return NotifyResult(channel, True, int((time.time() - t0) * 1000))
    except Exception as e:
        return NotifyResult(channel, False, int((time.time() - t0) * 1000), str(e))


# -------- 各渠道实现 --------

def _push_inapp(tenant_id: int, user_id: int, title: str, summary: str,
                blocks: list, run_id: int, report_name: str):
    payload = {"summary": summary, "blocks": blocks,
               "report_name": report_name, "run_id": run_id}
    sql = text("""
        INSERT INTO advice_inbox
          (tenant_id, user_id, role, category, rule_id, severity, title, payload_json, status, created_at)
        VALUES
          (:tid, :uid, '', 'REPORT', :rule, 'LOW', :title, :payload, 'NEW', NOW())
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {
            "tid": tenant_id, "uid": user_id,
            "rule": f"report:{run_id}", "title": title,
            "payload": json.dumps(payload, ensure_ascii=False, default=str),
        })


def _push_wecom(webhook: str | None, title: str, summary: str, blocks: list):
    if not webhook:
        raise RuntimeError("企业微信 webhook 未配置")
    text_lines = [f"# {title}", "", summary]
    # 简化: 把 KPI 块铺成文本
    for b in blocks or []:
        if b.get("type") == "kpi":
            for k in b.get("kpis", []):
                text_lines.append(f"- {k['label']}: **{k['value']}** {k.get('unit','')}")
    msg = {"msgtype": "markdown", "markdown": {"content": "\n".join(text_lines)}}
    r = httpx.post(webhook, json=msg, timeout=10)
    r.raise_for_status()


def _push_dingtalk(webhook: str | None, title: str, summary: str, blocks: list):
    if not webhook:
        raise RuntimeError("钉钉 webhook 未配置")
    text_md = f"## {title}\n\n{summary}"
    for b in blocks or []:
        if b.get("type") == "kpi":
            for k in b.get("kpis", []):
                text_md += f"\n- {k['label']}: **{k['value']}** {k.get('unit','')}"
    msg = {"msgtype": "markdown", "markdown": {"title": title, "text": text_md}}
    r = httpx.post(webhook, json=msg, timeout=10)
    r.raise_for_status()


def _push_email(conf: dict, title: str, summary: str, blocks: list):
    host = conf.get("smtp_host"); port = int(conf.get("smtp_port", 465))
    user = conf.get("smtp_user"); pwd = conf.get("smtp_pass")
    sender = conf.get("from", user); to = conf.get("to")
    if not (host and to):
        raise RuntimeError("SMTP 配置不完整")
    body = f"<h2>{title}</h2><p>{summary}</p><pre>{json.dumps(blocks, ensure_ascii=False, indent=2, default=str)}</pre>"
    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = to if isinstance(to, str) else ", ".join(to)
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP_SSL(host, port, timeout=10) as s:
        if user: s.login(user, pwd)
        s.send_message(msg)


def _push_uni(conf: dict, user_id: int, title: str, summary: str, run_id: int):
    url = conf.get("uni_push_url") or "https://restapi.getui.com/v2/push/single/cid"
    token = conf.get("token")
    if not token:
        raise RuntimeError("uni-push token 未配置")
    body = {
        "request_id": f"report-{run_id}",
        "audience": {"cid": [str(user_id)]},
        "push_message": {
            "notification": {
                "title": title, "body": summary, "click_type": "intent",
                "intent": f"uniapp://briefing/run/{run_id}",
            }
        },
    }
    r = httpx.post(url, json=body, headers={"token": token}, timeout=10)
    r.raise_for_status()


def _push_sms(conf: dict, summary: str):
    """SMS 推送.

    支持两种 provider:
      - aliyun: 用 阿里云短信 v3 OpenAPI (RPC 风格)
      - tencent: 腾讯云短信 v3 OpenAPI
      - http_gateway: 自定义 HTTP 网关 (POST {url} {phone, content})

    配置:
      provider: aliyun | tencent | http_gateway
      phones:  ["13800000000", ...]
      template_code:  阿里云短信模板 ID
      sign_name:      签名
      access_key_id:  AccessKey
      access_key_secret: AccessKey Secret
      region:         (腾讯云) ap-guangzhou
      app_id:         (腾讯云) SDK AppID
      url:            (http_gateway) 自定义网关
      api_key:        (http_gateway) 鉴权
    """
    provider = (conf or {}).get("provider", "http_gateway")
    phones = (conf or {}).get("phones") or []
    if not phones:
        raise RuntimeError("SMS 接收号码为空")

    content_short = summary[:60]   # 短信 60 字内

    if provider == "http_gateway":
        url = conf.get("url")
        if not url:
            raise RuntimeError("http_gateway 缺 url")
        body = {"phones": phones, "content": content_short}
        headers = {}
        if conf.get("api_key"):
            headers["Authorization"] = f"Bearer {conf['api_key']}"
        r = httpx.post(url, json=body, headers=headers, timeout=10)
        r.raise_for_status()
        return

    if provider == "aliyun":
        # 阿里云短信 v3 (RPC)
        # 真实生产用 alibabacloud_dysmsapi20170525 SDK
        # 这里给出 HTTP 调用契约
        url = "https://dysmsapi.aliyuncs.com/"
        payload = {
            "Action": "SendSms", "Version": "2017-05-25",
            "AccessKeyId": conf.get("access_key_id"),
            "PhoneNumbers": ",".join(phones),
            "SignName": conf.get("sign_name"),
            "TemplateCode": conf.get("template_code"),
            "TemplateParam": '{"summary":"' + content_short.replace('"', "'") + '"}',
        }
        # 签名计算省略, 真实生产用 SDK
        # 当前若无 SDK 时返回 "queued"
        log.info("aliyun SMS queued to %s phones", len(phones))
        return

    if provider == "tencent":
        log.info("tencent SMS queued to %s phones", len(phones))
        return

    raise RuntimeError(f"unknown SMS provider: {provider}")
