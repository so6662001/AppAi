# metric-registry-service (Java)

实现 `docs/metric-registry/api.openapi.yaml` 中核心接口：

| Method | Path |
|--------|------|
| GET | /metrics |
| POST | /metrics |
| GET | /metrics/{code} |
| PATCH | /metrics/{code} |
| DELETE | /metrics/{code} (软废弃) |
| GET | /metrics/{code}/impact |
| GET | /metrics/{code}/lineage |
| GET | /overview |

```bash
mvn package
mvn spring-boot:run
mvn test    # 7 passed
```
