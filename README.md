# Strata

**Headless semantic and safety data plane for enterprise file systems.**

Strata is a storage-native semantic layer that sits beside existing file infrastructure (NFS/SMB shares, NAS, object stores) and makes file estates legible, queryable, and governable for AI agents.

## What It Does

- **Ingests file metadata and content** from SMB shares via a lightweight connector agent
- **Classifies documents** as CONTRACT, POLICY, RFC, or OTHER using LLM-based classification
- **Extracts structured fields** from documents (parties, terms, obligations, etc.) based on document type
- **Type-aware chunking** preserves semantic boundaries (clauses, sections, headings)
- **Detects sensitive content** using regex-based PII/secret scanners (emails, SSNs, credit cards, API keys)
- **Computes exposure scores** based on ACL breadth and sensitivity findings
- **Policy engine** controls what AI agents can see (raw, redacted, or summary views)
- **Semantic diff** tracks changes between document versions with LLM-generated summaries
- **Answer with evidence** API for RAG with source citations and policy enforcement
- **RAG observability** tracks all interactions for audit and debugging

## Architecture

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
│  │  │   Ingest    │  │   Query     │  │  Dashboard  │  │   Admin     │  │   │
│  │  │     API     │  │    API      │  │     API     │  │    API      │  │   │
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
│  │   chunking      │ │ • Redaction     │ │ • Diff compute  │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     PostgreSQL + pgvector                             │   │
│  │                                                                       │   │
│  │  tenants │ estates │ shares │ files │ principals │ ACLs │ documents  │   │
│  │  chunks │ embeddings │ sensitivity_findings │ document_exposure │ jobs│   │
│  │  agents │ policies │ interactions │ semantic_diff_results            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Manifest

```
strata/
├── README.md                    # This file
├── CLAUDE.md                    # Claude Code guidance
├── docker-compose.yml           # Docker services (db, api, worker, agent, samba)
│
├── backend/                     # Control plane (FastAPI)
│   ├── pyproject.toml           # Python dependencies
│   ├── Dockerfile               # Container image
│   ├── alembic.ini              # Migration config
│   ├── alembic/
│   │   ├── env.py               # Alembic environment
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_semantic_features.py
│   └── app/
│       ├── main.py              # FastAPI entrypoint
│       ├── config.py            # Settings (pydantic-settings)
│       ├── db.py                # Database session management
│       ├── models.py            # SQLAlchemy ORM models
│       ├── schemas.py           # Pydantic request/response schemas
│       ├── auth.py              # API key authentication
│       ├── api/
│       │   ├── admin.py         # Tenant/estate/share/agent management
│       │   ├── ingest.py        # POST /v0/ingest/events
│       │   └── query.py         # Sensitivity/search/RAG APIs
│       ├── services/
│       │   ├── extraction.py    # Text extraction + type-aware chunking
│       │   ├── sensitivity.py   # PII/secret regex detection
│       │   ├── exposure.py      # Exposure score calculation
│       │   ├── classification.py    # Document type classification
│       │   ├── semantic_extraction.py  # Structured field extraction
│       │   ├── semantic_diff.py     # Version diff computation
│       │   ├── policy_engine.py     # Agent policy enforcement
│       │   └── observability.py     # RAG interaction tracking
│       └── workers/
│           ├── base.py          # Base worker with job claiming
│           ├── extraction.py    # EXTRACT_CONTENT job processor
│           ├── enrichment.py    # ENRICH_CHUNKS job processor
│           ├── semantics.py     # EXTRACT_SEMANTICS job processor
│           └── runner.py        # Worker process entrypoint
│
├── agent/                       # SMB connector agent
│   ├── pyproject.toml           # Python dependencies
│   ├── Dockerfile               # Agent container image
│   ├── config.example.yaml      # Example configuration
│   └── agent/
│       ├── config.py            # YAML config loading
│       ├── scanner.py           # File system scanner
│       ├── client.py            # Strata API client
│       └── main.py              # CLI entrypoint
│
├── docker/                      # Docker environment
│   ├── Dockerfile.init          # Init container for bootstrapping
│   ├── init-dev.py              # Bootstrap tenant/estate/share
│   ├── agent-config.yaml        # Agent config for Docker env
│   ├── samba/
│   │   └── smb.conf             # Samba configuration
│   └── samples/                 # Sample documents
│       ├── contracts/           # Sample contracts (MSA, NDA)
│       ├── policies/            # Sample policies (AUP, data classification)
│       └── rfcs/                # Sample RFCs (K8s migration, API versioning)
│
└── docs/                        # Design documents
    ├── ARCHITECTURE.md          # Technical architecture (definitive)
    ├── CONCEPT.md               # Architecture concepts
    ├── USE_CASES.md             # Product use cases
    ├── POSITIONING.md           # Market positioning
    └── FOUNDER_THESIS.md        # Founder thesis
```

## Quick Start

```bash
# Start everything (db, api, worker, samba, agent)
docker-compose up --build

# The init container automatically:
# 1. Waits for the API to be ready
# 2. Creates a dev tenant with API key
# 3. Creates an estate and share
# 4. Passes the API key to the agent
#
# The agent then scans the sample documents in docker/samples/
```

Sample documents include:
- **Contracts**: Master Service Agreement, NDA
- **Policies**: Data Classification Policy, Acceptable Use Policy
- **RFCs**: Kubernetes Migration, API Versioning Strategy

## API Reference

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/admin/tenant` | POST | Create tenant (returns API key) |
| `/v0/admin/estate` | POST | Create estate |
| `/v0/admin/estates` | GET | List estates |
| `/v0/admin/share` | POST | Create share |
| `/v0/admin/shares` | GET | List shares |
| `/v0/admin/agent` | POST | Create agent (returns API key) |
| `/v0/admin/agents` | GET | List agents |
| `/v0/admin/agents/{id}` | GET | Get agent details |
| `/v0/admin/agents/{id}` | DELETE | Delete agent |
| `/v0/admin/agents/{id}/policies/{id}` | POST | Assign policy to agent |
| `/v0/admin/agents/{id}/policies/{id}` | DELETE | Remove policy from agent |

### Ingestion & Query Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/ingest/events` | POST | Ingest file events from agent |
| `/v0/sensitivity/find` | POST | Query sensitive documents |
| `/v0/search/chunks` | POST | Basic text search over chunks |
| `/v0/dashboard/metrics` | GET | Dashboard statistics |
| `/v0/documents/{id}` | GET | Document details with findings |
| `/health` | GET | Health check |

### Semantic & Observability APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v0/search/chunks` | POST | Agent-aware search with policy enforcement |
| `/v0/answer_with_evidence` | POST | RAG with source citations |
| `/v0/semantic_diff` | POST | Compute diff between document versions |
| `/v0/interactions` | GET | List RAG interactions (audit) |
| `/v0/interactions/{id}` | GET | Get interaction trace details |
| `/v0/agents/{id}/stats` | GET | Agent interaction statistics |

## Sensitivity Detection

The enrichment worker detects the following sensitive content types:

| Type | Patterns | Level |
|------|----------|-------|
| **PERSONAL_DATA** | Email addresses, phone numbers, SSN-like patterns | MEDIUM-HIGH |
| **FINANCIAL_DATA** | Credit card numbers (with Luhn validation) | HIGH |
| **SECRETS** | AWS keys, API keys, bearer tokens, private keys, GitHub/Slack tokens | HIGH |

## Exposure Scoring

Exposure is calculated based on:

1. **Principal breadth** (0-10 principals = 20pts, 11-100 = 50pts, >100 = 80pts)
2. **Broad groups** (+20pts if "Domain Users", "Everyone", etc. have access)
3. **Sensitivity score** (SECRETS/FINANCIAL = 80pts, PERSONAL = 60pts)

Final score: `min(100, sensitivity_score + principal_breadth_score)`

Exposure levels: LOW (0-39), MEDIUM (40-69), HIGH (70-100)

## Development

### Running Tests

```bash
docker-compose exec api pytest
docker-compose exec api pytest -v tests/test_sensitivity.py  # Single file
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection string |
| `ENABLE_EMBEDDINGS` | `false` | Enable OpenAI embeddings |
| `OPENAI_API_KEY` | - | OpenAI API key (if embeddings enabled) |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |

## Document Classification

Documents are automatically classified into types:

| Type | Description | Extracted Fields |
|------|-------------|------------------|
| **CONTRACT** | Legal agreements, NDAs, SOWs | parties, effective_date, term_months, governing_law, payment_terms |
| **POLICY** | Company policies, procedures | policy_name, policy_type, scope, key_requirements, violations |
| **RFC** | Technical specs, design docs | title, authors, status, affected_systems, proposed_solution |
| **OTHER** | Unclassified documents | (none) |

## Policy Engine

Agents can be assigned policies that control document access:

```yaml
# Example policy configuration
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
```

View types: **raw** (full content), **redacted** (PII/secrets masked), **summary** (chunk summaries only)

## v0 Scope

**In Scope:**

- Single SMB connector type
- Single Postgres instance
- PDF, DOCX, PPTX, TXT extraction
- Regex-based sensitivity detection
- Static API key auth (tenant + agent keys)
- Document type classification (CONTRACT, POLICY, RFC)
- Structured field extraction via LLM
- Document versioning and semantic diff
- Agent-based policy enforcement
- RAG observability (interaction traces)

**Out of Scope:**

- SharePoint/OneDrive/Box connectors
- Write operations to file systems
- OCR for scanned documents
- Remediation APIs
- Production-grade auth (OAuth, SAML)
- Embedding-based semantic search (prepared but not active)

## License

Proprietary - All rights reserved.
