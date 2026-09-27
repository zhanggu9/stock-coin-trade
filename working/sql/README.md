# sql/ — DB별 읽기 쿼리

Lambda 서비스 함수가 사용하는 조회 SQL만 모았습니다. 애플리케이션 코드에
문자열로 흩어져 있던 쿼리를 파일로 분리해 리뷰·재사용을 쉽게 합니다.

| 파일 | 대상 DB | 사용하는 Lambda |
|---|---|---|
| `mariadb_member.sql` | MariaDB 서비스 DB | `lambda/member` |
| `quant_recent_prices.sql` | PostgreSQL Quant DB | `lambda/quant` |
| `ohlcv_summary.sql` | PostgreSQL pg-stock | `lambda/ohlcv` |

Redis(세션)와 Qdrant(벡터)는 SQL을 쓰지 않습니다. 각각 키 TTL 조회와
`query_points` 벡터 검색을 사용하며 해당 코드는 `lambda/session`,
`lambda/knowledge`에 있습니다.
