# Service × dependency matrix

Used by `stability-review-prompt.md` Phase 6 (architecture lens). Tells the routine which backing stores a service can lose tolerantly vs which constitute hard dependencies.

Rows: services. Columns: backing stores and other services. Cells:
- **H** = hard dependency. Service is unhealthy if this is unhealthy.
- **S** = soft dependency. Service degrades but continues (cache miss, optional feature).
- **A** = async dependency. Service writes to it; failure is buffered or retryable; user-visible only on the read side.
- blank = not applicable.

## Backing stores

| Service / Worker                  | SQL | Mongo | Redis | RabbitMQ | ES   | S3   | OAuth2/Auth |
|-----------------------------------|:---:|:-----:|:-----:|:--------:|:----:|:----:|:-----------:|
| ms-gateway-api                    |     |       |   H   |          |      |      |     H       |
| ms-authentication-api             |  H  |       |   S   |          |      |      |             |
| oauth2                            |  H  |       |       |          |      |      |             |
| runtime-core (Runtime.Core.Api)   |  H  |   H   |   S   |    A     |  S   |      |     H       |
| runtime-core (Designer.Core.Api)  |  H  |   H   |       |    A     |      |      |     H       |
| runtime-core (Subscriber.Agent)   |  S  |   S   |   H   |    H     |      |      |             |
| runtime-core (AppUpdate.Agent)    |  H  |   H   |       |    A     |      |      |             |
| ms-tables-fields-api              |  H  |       |   S   |    A     |  S   |      |     H       |
| ms-account-api                    |  H  |       |   S   |          |      |      |     H       |
| ms-tags-api                       |  H  |       |       |          |      |      |     H       |
| ms-preferences-api                |  H  |       |       |          |      |      |     H       |
| ms-documents-api                  |  H  |       |       |          |      |  H   |     H       |
| ms-email-api                      |  H  |       |       |    A     |      |      |     H       |
| ms-scheduler-api                  |  H  |       |       |    A     |      |      |     H       |
| qbo-sync-api                      |  H  |       |       |    H     |      |      |     H       |
| ms-reminder-agent                 |  H  |       |       |    H     |      |      |             |
| legacy-email-agent                |  H  |       |       |    A     |      |      |             |
| Method.Search                     |     |       |       |          |  H   |      |     H       |

## Service-to-service hard dependencies

```
ms-gateway-api      → ms-authentication-api (JWT validate; Redis-cached)
runtime-core        → ms-tables-fields-api (no-code metadata)
runtime-core        → ms-account-api       (account registry)
qbo-sync-api        → runtime-core         (action execution)
ms-* (most)         → ms-authentication-api (JWT validate, Redis-cached)
```

## How the routine uses this matrix

When clustering Phase 2 produces a recurring failure mode for service X, Phase 6 looks up X's row to enumerate the dependency surface. The recommendation can then propose:

- **For an H column with frequent unavailability** — circuit-breaker on the dependency (`level-10/circuit-breakers-and-bulkheads.json`), retry policy review, or eliminate the dependency altogether.
- **For an S column with frequent unavailability** — soft-dependency degradation is working; verify the user impact is small and decide whether to harden.
- **For an A column with frequent unavailability** — back-pressure / DLQ depth alerting (`level-10/back-pressure-and-flow-control.json`, `level-5/message-queues.json`).
- **For a backing store with frequent unavailability** — multiple services share it, so the recommendation is structural (capacity, replication, replacement) rather than per-service.

## Cross-tenant blast radius

Some services are per-tenant (each request scoped to one account). Others are platform-shared. A failure in a platform-shared service has a different blast-radius shape:

| Service | Scope |
|---------|-------|
| ms-gateway-api          | platform-shared |
| ms-authentication-api   | platform-shared |
| oauth2                  | platform-shared |
| Redis                   | platform-shared |
| RabbitMQ                | platform-shared |
| Elasticsearch           | platform-shared |
| ms-account-api          | platform-shared |
| runtime-core            | per-request, but shared instance |
| Per-tenant SQL DB       | per-tenant (one cluster's DBs) |
| Per-tenant Mongo DB     | per-tenant |

A platform-shared failure → blast radius = entire active user base. A per-tenant failure → blast radius = one account.

## Maintenance

Update this file when:
- A new service appears in `CLAUDE.md`'s service catalog.
- A service's dependencies change (e.g., Redis added/removed; new RabbitMQ consumer).
- The triage-bot's cluster analysis surfaces a dependency the matrix didn't capture (the routine should append to the matrix as part of Phase 6 if it discovers a gap).

Keep this file in sync with `CLAUDE.md`. When in conflict, `CLAUDE.md` wins; this file follows.
