# Strata Architecture

**Version:** 1.0
**Status:** Current implementation

This document describes the architecture of Strata, a headless semantic and safety data plane for enterprise file systems.

---

## 1. Overview

Strata is a storage-native semantic layer that sits beside existing file infrastructure (NFS/SMB shares, NAS, object stores) and makes file estates legible, queryable, and governable for AI agents.

### Core Capabilities

1. **Connectors & Ingestion** - Pull file content + ACLs into a normalized model
2. **Document Classification** - Classify documents as CONTRACT, POLICY, RFC, or OTHER
3. **Semantic Extraction** - Extract structured fields based on document type
4. **Type-Aware Chunking** - Preserve semantic boundaries (clauses, sections, headings)
5. **Sensitivity Detection** - Detect PII, secrets, and financial data
6. **Policy Engine** - Control what AI agents can see (raw, redacted, or summary views)
7. **Semantic Diff** - Track changes between document versions
8. **RAG with Evidence** - Answer questions with source citations
9. **Observability** - Track all interactions for audit and debugging

### Design Principles

- **Headless & API-First** - No end-user UI; designed for integration
- **Multi-Tenant** - All data isolated by `tenant_id`
- **Agent-Aware** - Policies enforced per-agent identity
- **Observable** - Every interaction traceable

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Customer Environment                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  SMB Share   │    │  SMB Share   │    │  SMB Share   │                   │
│  │   (mounted)  │    │   (mounted)  │    │   (mounted)  │                   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                   │                            │
│         └───────────────────┼───────────────────┘                            │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  Strata Agent   │  Scans files, computes hashes,        │
│                    │    (Python)     │  collects ACLs, sends events          │
│                    └────────┬────────┘                                       │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │ HTTPS
                              │ POST /v0/ingest/events
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Strata Control Plane                               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Server                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │   Ingest    │  │   Query     │  │    RAG      │  │   Admin     │  │   │
│  │  │     API     │  │    API      │  │    API      │  │    API      │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        Job Queue (Postgres)                           │   │
│  │                   SELECT ... FOR UPDATE SKIP LOCKED                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│           ┌──────────────────┼──────────────────┐                           │
│           ▼                  ▼                  ▼                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │   Extraction    │ │   Enrichment    │ │   Semantics     │               │
│  │     Worker      │ │     Worker      │ │     Worker      │               │
│  │                 │ │                 │ │                 │               │
│  │ • Read files    │ │ • Embeddings    │ │ • Extract       │               │
│  │ • Classify type │ │ • PII detection │ │   structured    │               │
│  │ • Type-aware    │ │ • Exposure calc │ │   fields        │               │
│  │   chunking      │ │ • Redaction     │ │                 │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     PostgreSQL + pgvector                             │   │
│  │                                                                       │   │
│  │  tenants │ estates │ shares │ files │ principals │ ACLs │ documents  │   │
│  │  chunks │ embeddings │ sensitivity_findings │ document_exposure      │   │
│  │  agents │ policies │ interactions │ semantic_diff_results            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 On-Prem SMB Connector Agent

**Location:** `agent/`

The agent runs in the customer environment and:
- Mounts SMB shares read-only
- Scans directories periodically
- Computes file metadata and content hashes
- Collects ACL entries
- Sends batched events to the Strata API

**Configuration (YAML):**
```yaml
agent_id: "agent-uuid"
tenant_api_key: "<redacted>"
api_base_url: "https://api.strata.example.com"
scan_interval_seconds: 600

shares:
  - name: "HRShare"
    mount_point: "/mnt/hrshare"
    include_paths: ["/"]
    exclude_patterns: ["*.tmp", "~*"]
    max_file_size_bytes: 104857600
```

### 3.2 FastAPI Server

**Location:** `backend/app/`

The control plane API server with these routers:

| Router | Path | Purpose |
|--------|------|---------|
| Admin | `/v0/admin/` | Tenant, estate, share, agent management |
| Ingest | `/v0/ingest/` | Receive file events from agents |
| Query | `/v0/` | Search, RAG, observability endpoints |

### 3.3 Workers

**Location:** `backend/app/workers/`

Workers poll the job queue using `SELECT ... FOR UPDATE SKIP LOCKED`:

| Worker | Job Type | Purpose |
|--------|----------|---------|
| ExtractionWorker | `EXTRACT_CONTENT` | Read files, classify, chunk, create document |
| EnrichmentWorker | `ENRICH_CHUNKS` | Embeddings, sensitivity detection, exposure |
| SemanticExtractionWorker | `EXTRACT_SEMANTICS` | Extract structured fields via LLM |

### 3.4 Services

**Location:** `backend/app/services/`

| Service | Purpose |
|---------|---------|
| `extraction.py` | Text extraction + type-aware chunking |
| `classification.py` | Document type classification |
| `semantic_extraction.py` | Structured field extraction via LLM |
| `semantic_diff.py` | Version diff computation |
| `policy_engine.py` | Agent policy evaluation |
| `observability.py` | Interaction tracking |
| `sensitivity.py` | PII/secret detection |
| `exposure.py` | Exposure score calculation |

---

## 4. Data Model

### 4.1 Core Entities

```
tenant
  └── estate
        └── share
              └── file
                    └── document (versioned)
                          ├── chunk
                          │     └── chunk_embedding
                          ├── sensitivity_finding
                          └── document_exposure
```

### 4.2 Identity & Access

```
tenant
  ├── principal (USER, GROUP, SERVICE)
  │     └── group_membership
  └── agent
        └── agent_policy
              └── policy
```

### 4.3 Observability

```
tenant
  └── interaction
        └── interaction_chunk
```

### 4.4 Key Tables

| Table | Purpose |
|-------|---------|
| `tenant` | Multi-tenant isolation |
| `estate` | Logical grouping of shares |
| `share` | SMB share configuration |
| `file` | File metadata and hashes |
| `principal` | Users and groups from AD/ACLs |
| `file_acl_entry` | Raw ACL entries |
| `file_effective_access` | Computed read access |
| `document` | Indexed document with versioning |
| `chunk` | Text chunks with section_path |
| `chunk_embedding` | Vector embeddings (pgvector) |
| `sensitivity_finding` | Detected PII/secrets |
| `document_exposure` | Exposure level and score |
| `agent` | Registered AI agents |
| `policy` | Access and redaction policies |
| `agent_policy` | Policy assignments |
| `interaction` | RAG interaction traces |
| `interaction_chunk` | Chunks used in interactions |
| `semantic_diff_result` | Cached version diffs |
| `job` | Background job queue |

### 4.5 Document Fields

| Field | Type | Purpose |
|-------|------|---------|
| `doc_type` | Enum | CONTRACT, POLICY, RFC, OTHER |
| `structured_fields` | JSONB | Extracted semantic fields |
| `version_number` | Integer | Version counter |
| `previous_version_id` | UUID | Link to previous version |

### 4.6 Chunk Fields

| Field | Type | Purpose |
|-------|------|---------|
| `section_path` | JSONB | Hierarchical path (e.g., ["1", "1.2", "Payment Terms"]) |
| `redacted_text` | Text | PII-masked version |
| `summary_text` | Text | LLM-generated summary |

---

## 5. Document Processing Pipeline

### 5.1 Ingestion Flow

```
Agent Scan → POST /v0/ingest/events → Upsert File → Create EXTRACT_CONTENT Job
```

### 5.2 Extraction Flow

```
EXTRACT_CONTENT Job
  │
  ├── Load file from share mount
  ├── Extract text (PDF/DOCX/PPTX/TXT)
  ├── Classify document type (LLM or heuristic)
  ├── Type-aware chunking with section_path
  ├── Create/update Document (versioned)
  ├── Create Chunks
  ├── Create ENRICH_CHUNKS job
  └── Create EXTRACT_SEMANTICS job (if CONTRACT/POLICY/RFC)
```

### 5.3 Enrichment Flow

```
ENRICH_CHUNKS Job
  │
  ├── Compute embeddings (OpenAI)
  ├── Run sensitivity detection (regex)
  ├── Create sensitivity_finding records
  ├── Compute exposure score
  └── Generate redacted_text
```

### 5.4 Semantic Extraction Flow

```
EXTRACT_SEMANTICS Job
  │
  ├── Load document chunks
  ├── Call LLM with type-specific schema
  └── Store structured_fields on Document
```

---

## 6. Document Classification

Documents are classified into types with specific extraction schemas:

### 6.1 Contract Schema

```json
{
  "parties": ["Party A", "Party B"],
  "effective_date": "2024-01-01",
  "term_months": 24,
  "auto_renew": true,
  "governing_law": "State of Delaware",
  "payment_terms": "Net 30",
  "termination_clauses": "Either party may terminate with 30 days notice",
  "key_obligations": ["Deliver services", "Pay invoices"],
  "sla_details": "99.9% uptime"
}
```

### 6.2 Policy Schema

```json
{
  "policy_name": "Data Classification Policy",
  "policy_type": "Security",
  "effective_date": "2024-01-01",
  "review_date": "2025-01-01",
  "owner": "Security Team",
  "scope": "All employees",
  "key_requirements": ["Classify all data", "Label sensitive files"],
  "violations": "Disciplinary action",
  "related_policies": ["Privacy Policy", "Acceptable Use Policy"]
}
```

### 6.3 RFC Schema

```json
{
  "title": "Migrate to Kubernetes",
  "authors": ["Jane Doe", "John Smith"],
  "status": "accepted",
  "created_date": "2024-01-15",
  "affected_systems": ["API Gateway", "Worker Services"],
  "problem_statement": "Current deployment is manual and error-prone",
  "proposed_solution": "Containerize all services and deploy to K8s",
  "alternatives_considered": ["ECS", "Lambda"],
  "decision": "Use GKE for managed Kubernetes",
  "implementation_notes": "Start with stateless services"
}
```

---

## 7. Type-Aware Chunking

### 7.1 Contract Chunking

Detects clause boundaries using patterns:
- Numbered clauses: `1.`, `1.1`, `Article 1`, `Section 1`
- Roman numerals: `I.`, `II.`, `III.`
- Lettered sections: `(a)`, `(b)`, `(i)`, `(ii)`

### 7.2 RFC/Policy Chunking

Detects section boundaries using:
- Markdown headings: `# Title`, `## Section`
- Numbered sections: `1. Introduction`, `1.1 Background`
- ALL CAPS headings

### 7.3 Chunk Metadata

Each chunk includes:
- `section_path`: Hierarchical path for navigation
- `char_start`/`char_end`: Position in original text
- Target size: ~300-600 tokens (~1200-2400 chars)

---

## 8. Policy Engine

### 8.1 Policy Configuration

```yaml
policies:
  - id: "external_assistant"
    applies_to_agents: ["external_assistant"]
    visibility:
      include_doc_types: ["POLICY", "RFC"]
      exclude_doc_types: ["CONTRACT"]
      include_paths: ["/public/", "/docs/"]
      exclude_paths: ["/internal/", "/hr/"]
    redaction:
      mask_pii: true
      mask_secrets: true
      use_summaries: false
    content:
      max_sensitivity_level: "MEDIUM"

  - id: "legal_assistant"
    applies_to_agents: ["legal_assistant"]
    visibility:
      include_doc_types: ["CONTRACT", "POLICY"]
    redaction:
      mask_pii: false
      mask_secrets: true
```

### 8.2 View Types

| View | Description |
|------|-------------|
| `raw` | Full original text |
| `redacted` | PII/secrets replaced with `[PERSONAL_DATA]`, `[SECRETS]` |
| `summary` | LLM-generated summary of chunk |

### 8.3 Policy Evaluation

For each chunk access:
1. Check visibility rules (doc_type, path)
2. If blocked, record `was_filtered=true` with reason
3. If allowed, determine view_type based on redaction rules
4. Return appropriate text representation

---

## 9. RAG Observability

### 9.1 Interaction Tracking

Every search or answer request creates an `Interaction` record:

```python
@dataclass
class InteractionTrace:
    interaction_id: UUID
    interaction_type: str  # "search_chunks", "answer_with_evidence"
    query: str
    scope: dict | None
    chunks_retrieved: list[RetrievedChunk]
    answer: str | None
    evidence_coverage: float | None
    latency_ms: int | None
    agent_id: UUID | None
    user_id: str | None
```

### 9.2 Chunk Recording

Each retrieved chunk is recorded with:
- `rank`: Position in results
- `score`: Relevance score
- `view_type`: raw/redacted/summary
- `was_filtered`: Whether blocked by policy
- `filter_reason`: Why it was blocked

### 9.3 Agent Statistics

Per-agent metrics available:
- Total interactions
- Interactions by type
- Average latency
- Total chunks retrieved
- Filtered chunk count

---

## 10. API Reference

### 10.1 Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/admin/tenant` | POST | Create tenant |
| `/v0/admin/estate` | POST | Create estate |
| `/v0/admin/share` | POST | Create share |
| `/v0/admin/agent` | POST | Create agent |
| `/v0/admin/agents` | GET | List agents |
| `/v0/admin/agents/{id}` | GET/DELETE | Get/delete agent |
| `/v0/admin/agents/{id}/policies/{id}` | POST/DELETE | Assign/remove policy |

### 10.2 Query Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/ingest/events` | POST | Ingest file events |
| `/v0/sensitivity/find` | POST | Find sensitive documents |
| `/v0/search/chunks` | POST | Basic text search |
| `/v0/dashboard/metrics` | GET | Dashboard statistics |
| `/v0/documents/{id}` | GET | Document details |

### 10.3 Semantic Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/search/chunks` | POST | Agent-aware search with policy |
| `/v0/answer_with_evidence` | POST | RAG with citations |
| `/v0/semantic_diff` | POST | Compute version diff |

### 10.4 Observability Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/interactions` | GET | List interactions |
| `/v0/interactions/{id}` | GET | Get interaction trace |
| `/v0/agents/{id}/stats` | GET | Agent statistics |

---

## 11. Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | PostgreSQL with pgvector |
| Job Queue | DB-backed with `SKIP LOCKED` |
| Auth | Static API keys (tenant + agent) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Content Extraction | pdfminer.six, python-docx, python-pptx |

---

## 12. Deployment

### 12.1 Docker Compose

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head
```

### 12.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection |
| `ENABLE_EMBEDDINGS` | `false` | Enable OpenAI embeddings |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `CHUNK_SIZE` | `1000` | Default chunk size (chars) |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |

---

## 13. Security Considerations

### 13.1 Multi-Tenancy

- All tables include `tenant_id`
- Every query filtered by tenant
- API keys scoped to tenant

### 13.2 Agent Identity

- Agents have separate API keys
- Policies enforced per-agent
- All interactions logged with agent_id

### 13.3 Data Protection

- API key hashes stored (not plaintext)
- PII detection and redaction
- Configurable sensitivity filtering

---

## 14. Current Limitations

**In Scope:**
- Single SMB connector type
- Single Postgres instance
- PDF, DOCX, PPTX, TXT extraction
- Regex-based sensitivity detection
- Static API key auth
- Document classification (CONTRACT, POLICY, RFC)
- Structured field extraction via LLM
- Document versioning and semantic diff
- Agent-based policy enforcement
- RAG observability

**Out of Scope:**
- SharePoint/OneDrive/Box connectors
- Write operations to file systems
- OCR for scanned documents
- Remediation APIs
- Production-grade auth (OAuth, SAML)
- Embedding-based semantic search (infrastructure ready)
