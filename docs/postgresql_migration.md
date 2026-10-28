# Production Cloud & PostgreSQL Migration Guide

This document outlines the migration path from local SQLite storage to production-grade **PostgreSQL** and distributed cloud infrastructure.

---

## 1. Migration Overview

| Local Development Baseline | Cloud Production Target | Migration Rationale |
| :--- | :--- | :--- |
| SQLite (`data/app.db`) | PostgreSQL 16+ (AWS RDS / Azure Database) | Multi-writer concurrency, connection pooling, enterprise backup |
| `AsyncSqliteSaver` (`checkpoints.db`) | `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`) | Distributed graph checkpoints across multiple worker pods |
| In-memory Async Background Tasks | Celery / Temporal / Redis Worker Queue | Distributed task queuing, survivability across pod restarts |
| Local Fixture JSON Lookups | PostgreSQL + `pgvector` extension | Native vector similarity search (HNSW/IVFFlat) and indexing |

---

## 2. PostgreSQL Configuration & Dependencies

### Step 1: Install PostgreSQL Checkpointer Driver
```bash
pip install asyncpg psycopg[binary,pool] langgraph-checkpoint-postgres
```

### Step 2: Update Connection String in `.env`
```ini
DATABASE_URL=postgresql+asyncpg://appuser:securepassword@db.internal:5432/agentic_platform
CHECKPOINTER_DB_URL=postgresql://appuser:securepassword@db.internal:5432/agentic_checkpoints
```

### Step 3: Switch Checkpointer Implementation
In `app/graph/checkpointer.py`:
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import psycopg_pool

class PostgresCheckpointerManager:
    def __init__(self, conn_string: str):
        self.conn_string = conn_string
        self.pool = psycopg_pool.AsyncConnectionPool(conninfo=conn_string)

    async def get_saver(self):
        saver = AsyncPostgresSaver(self.pool)
        await saver.setup()
        return saver
```

---

## 3. High-Availability Cloud Architecture (AWS / Azure)

```
[ CloudFront / Azure Front Door ]
               |
               v
[ Application Load Balancer / Ingress Controller ]
               |
    +----------+----------+
    |                     |
    v                     v
[ ECS / EKS Pod 1 ]   [ ECS / EKS Pod 2 ]  (FastAPI Stateless Containers)
    |                     |
    +----------+----------+
               |
       +-------+-------+
       |               |
       v               v
[ RDS PostgreSQL 16 ]  [ ElastiCache Redis ]
 (App DB & pgvector)   (Rate-limits & Celery Broker)
```

---

## 4. Exactly-Once Execution Limits

> **Senior Architect Note on Reliability:**
> Checkpoint persistence guarantees that a workflow can resume from its last completed step after a crash. However, **checkpointing alone does not make external side effects exactly-once**.
>
> If an external API call succeeds (e.g., publishing to Slack), but the node crashes or loses power *before* committing the checkpoint to PostgreSQL, the recovery engine will re-execute the step upon restart.
> 
> **Production Countermeasure:** All state-changing tools must implement idempotency keys sent in outgoing request headers, and recipient APIs must enforce deduplication.
