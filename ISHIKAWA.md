# Ishikawa: Medallion Data Lake MCP

> Intelligence gathering from structured data sources.

## Overview

Ishikawa is an MCP server interface for exposing medallion architecture data lakes to Major. It provides read-only access to Silver (processed records) and Gold (aggregated views) layers.

```
SOURCE DOCUMENTS          MEDALLION LAKE              MAJOR

Raw files ──────► Bronze ──► Silver ──► Gold ───► Ishikawa MCP ───► Agent
                              │          │
                              │          └── Rollups, summaries
                              └── Processed records, evidence
```

## Core Principles

1. **Read-only** - Ishikawa only reads. Writes go through application APIs.
2. **Org-scoped** - All queries implicitly scoped to authenticated org. No cross-org access.
3. **Silver + Gold** - Exposes processed and aggregated layers, not raw bronze.
4. **Schema-driven** - Each implementation describes its entities dynamically.
5. **Lineage** - Can trace gold aggregations back to silver evidence.

## MCP Tools

### Discovery

#### `ishikawa_get_schema`

Returns the schema for this data lake - what entities exist, their fields, and relationships.

```json
{
  "name": "ishikawa_get_schema",
  "description": "Get the schema for this medallion data lake",
  "input_schema": {
    "type": "object",
    "properties": {}
  }
}
```

**Response:**
```json
{
  "name": "qualivai",
  "description": "School quality indicator assessments",
  "gold_entities": [
    {
      "name": "indicator_rollups",
      "description": "Aggregated scores per indicator per school",
      "fields": [
        {"name": "indicator_id", "type": "string", "description": "Indicator identifier"},
        {"name": "school_id", "type": "string", "description": "School identifier"},
        {"name": "average_score", "type": "number", "description": "Average score 0-100"},
        {"name": "assessment_count", "type": "integer", "description": "Number of assessments"},
        {"name": "status", "type": "string", "enum": ["meets_standard", "needs_review", "does_not_meet", "no_data"]}
      ],
      "filters": ["school_id", "indicator_id", "domain", "status", "min_score", "max_score"]
    },
    {
      "name": "standard_rollups",
      "description": "Aggregated scores per standard per school",
      "fields": ["..."]
    },
    {
      "name": "school_summaries",
      "description": "Overall school-level summary",
      "fields": ["..."]
    }
  ],
  "silver_entities": [
    {
      "name": "assessments",
      "description": "Individual chunk assessments with evidence",
      "fields": [
        {"name": "indicator_id", "type": "string"},
        {"name": "school_id", "type": "string"},
        {"name": "document_id", "type": "string"},
        {"name": "score", "type": "number"},
        {"name": "evidence_quotes", "type": "array"},
        {"name": "explanation", "type": "string"}
      ],
      "filters": ["school_id", "indicator_id", "document_id", "min_score"]
    }
  ],
  "context_keys": ["school_id"],
  "hierarchy": {
    "description": "Indicator hierarchy for QualivAI",
    "levels": ["domain", "standard", "indicator"]
  }
}
```

### Gold Layer (Aggregated Views)

#### `ishikawa_query_gold`

Query aggregated/rolled up data from the gold layer.

```json
{
  "name": "ishikawa_query_gold",
  "description": "Query aggregated data from the gold layer",
  "input_schema": {
    "type": "object",
    "properties": {
      "entity": {
        "type": "string",
        "description": "Gold entity to query (e.g., 'indicator_rollups')"
      },
      "context": {
        "type": "object",
        "description": "Context keys (e.g., {school_id: 'xxx'})"
      },
      "filters": {
        "type": "object",
        "description": "Filter criteria"
      },
      "limit": {
        "type": "integer",
        "description": "Max records to return",
        "default": 50
      }
    },
    "required": ["entity", "context"]
  }
}
```

**Example call:**
```json
{
  "entity": "indicator_rollups",
  "context": {"school_id": "school_123"},
  "filters": {"domain": "academic", "min_score": 70},
  "limit": 20
}
```

**Response:**
```json
{
  "entity": "indicator_rollups",
  "records": [
    {
      "indicator_id": "aca_1_1",
      "school_id": "school_123",
      "average_score": 85.5,
      "assessment_count": 12,
      "status": "meets_standard",
      "_lineage_key": "aca_1_1:school_123"
    }
  ],
  "total": 45,
  "returned": 20
}
```

### Silver Layer (Evidence/Detail)

#### `ishikawa_query_silver`

Query processed records from the silver layer.

```json
{
  "name": "ishikawa_query_silver",
  "description": "Query processed records from the silver layer",
  "input_schema": {
    "type": "object",
    "properties": {
      "entity": {
        "type": "string",
        "description": "Silver entity to query (e.g., 'assessments')"
      },
      "context": {
        "type": "object",
        "description": "Context keys"
      },
      "filters": {
        "type": "object",
        "description": "Filter criteria"
      },
      "limit": {
        "type": "integer",
        "default": 20
      }
    },
    "required": ["entity", "context"]
  }
}
```

#### `ishikawa_get_lineage`

Trace a gold record back to its silver evidence.

```json
{
  "name": "ishikawa_get_lineage",
  "description": "Get silver records that contribute to a gold aggregation",
  "input_schema": {
    "type": "object",
    "properties": {
      "gold_entity": {
        "type": "string",
        "description": "Gold entity name"
      },
      "lineage_key": {
        "type": "string",
        "description": "Lineage key from gold record"
      },
      "limit": {
        "type": "integer",
        "default": 10
      }
    },
    "required": ["gold_entity", "lineage_key"]
  }
}
```

**Example:** Get evidence for an indicator rollup
```json
{
  "gold_entity": "indicator_rollups",
  "lineage_key": "aca_1_1:school_123",
  "limit": 5
}
```

**Response:**
```json
{
  "gold_entity": "indicator_rollups",
  "lineage_key": "aca_1_1:school_123",
  "silver_entity": "assessments",
  "records": [
    {
      "id": "task_abc123",
      "indicator_id": "aca_1_1",
      "document_id": "doc_xyz",
      "score": 90,
      "evidence_quotes": ["The school demonstrates strong..."],
      "explanation": "Clear evidence of standards-aligned curriculum"
    }
  ],
  "total": 12,
  "returned": 5
}
```

## Implementation Contract

Each Ishikawa implementation must:

1. **Implement all 4 tools** - `get_schema`, `query_gold`, `query_silver`, `get_lineage`
2. **Enforce org scoping** - Extract org_id from MCP auth context, apply to all queries
3. **Validate context keys** - Ensure required context (e.g., school_id) is provided
4. **Return consistent shapes** - Follow response formats above
5. **Handle pagination** - Support limit/offset for large result sets

## Security Model

```
┌─────────────────────────────────────────┐
│  MCP Connection (authenticated)         │
│  └── org_id extracted from auth         │
├─────────────────────────────────────────┤
│  Every query:                           │
│  1. Validate org_id present             │
│  2. Apply org_id filter to ALL queries  │
│  3. Reject if context violates org      │
└─────────────────────────────────────────┘
```

No query can ever return data from another org. This is enforced at the Ishikawa layer, not trusted to callers.

## QualivAI Implementation

```
ishikawa-qualivai/
├── server.py          # MCP server entry point
├── schema.py          # QualivAI schema definition
├── gold.py            # Gold layer queries (Firestore)
├── silver.py          # Silver layer queries (Firestore)
└── auth.py            # Org extraction from MCP context
```

**Gold entities:**
- `indicator_rollups` - Per-indicator scores
- `standard_rollups` - Per-standard aggregations
- `question_rollups` - Per-domain aggregations
- `school_summaries` - Overall school summary

**Silver entities:**
- `assessments` - Chunk assessments (tasks collection)

**Context keys:**
- `school_id` (required for most queries)

**Hierarchy:**
- Domain (3) → Standard (10) → Indicator (82)

## Integration with Major

Major discovers Ishikawa via MCP config:

```json
{
  "mcpServers": {
    "ishikawa-qualivai": {
      "command": "python",
      "args": ["-m", "ishikawa_qualivai.server"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "..."
      }
    }
  }
}
```

Major uses schema discovery to understand what's available, then queries as needed during conversations.

## Future Implementations

- **ishikawa-marketo** - Marketing data lake
- **ishikawa-salesforce** - CRM data
- **ishikawa-analytics** - Product analytics

Same interface, different underlying data sources.
