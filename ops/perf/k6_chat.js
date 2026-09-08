// k6 压测脚本: 模拟 100 并发用户问问题
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const latency = new Trend('chat_latency');

export const options = {
  stages: [
    { duration: '30s', target: 20 },     // 慢慢加到 20 vu
    { duration: '2m',  target: 100 },    // 加到 100 vu
    { duration: '2m',  target: 100 },    // 稳定 100 vu
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'chat_latency': ['p(95)<5000'],      // P95 < 5s
    'http_req_failed': ['rate<0.01'],    // 错误率 < 1%
  },
};

const QUERIES = [
  '昨天我们的销售额',
  '本月华东达交率',
  '按客户的吨毛利 Top10',
  '上周库存周转天数',
  '为什么本周吨毛利下降',
  '沙钢系 Q355B 的挂价毛利',
];

export default function () {
  const text = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const r = http.post('http://gateway:8000/v1/chat/preview',
    JSON.stringify({ text }),
    { headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${__ENV.JWT_TOKEN}`,
      }});
  check(r, { 'status 200': (r) => r.status === 200 });
  latency.add(r.timings.duration);
  sleep(1);
}
