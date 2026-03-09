# MCP Interface Spec — approved-language

**Server ID:** `approved-language`
**Phase:** 3
**Mock stub:** None yet — add `mcp/approved_language/mock_language.py` in Phase 3 prep
**Priority:** High for external docs — all external-facing language must come from here.

---

## Purpose

Serve the approved phrase library and mandatory disclosure templates used
in investor-facing and external documents.

The document-drafter must retrieve language packs from this server before
composing an investor summary or any external-facing section. It may not
invent regulatory language, risk factor descriptions, or mandatory disclaimers.

The compliance-reviewer checks that final drafts only use language
sourced from this server for regulated sections.

All data returned here must be tagged `[retrieved]`.

---

## Tool contracts

### `get_language_pack`

Retrieve approved text blocks for a specific audience, asset class, and region.

**Request:**
```json
{
  "audience": "institutional_investor",
  "asset_class": "US_CLO",
  "region": "US",
  "sections": ["risk_factors", "transaction_overview", "disclosures"]
}
```

`sections` is optional — if omitted, all available sections are returned.

**Response:**
```json
{
  "language_pack_id": "lp-us-clo-inst-2024-01",
  "audience": "institutional_investor",
  "asset_class": "US_CLO",
  "region": "US",
  "version": "2024-01",
  "effective_date": "2024-01-01",
  "source": "approved_language_library",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "sections": {
    "risk_factors": {
      "section_id": "lp-us-clo-inst-2024-01/risk_factors",
      "text_blocks": [
        {
          "block_id": "rf-clo-credit-risk",
          "label": "Credit Risk",
          "text": "CLO notes are subject to credit risk including the risk of default by obligors in the underlying collateral pool..."
        },
        {
          "block_id": "rf-clo-subordination",
          "label": "Subordination and Tranching",
          "text": "The notes are issued in multiple classes with varying degrees of credit enhancement provided by subordination..."
        }
      ]
    },
    "disclosures": {
      "section_id": "lp-us-clo-inst-2024-01/disclosures",
      "text_blocks": [
        {
          "block_id": "disc-not-registered",
          "label": "Securities Act Disclaimer",
          "text": "These securities have not been registered under the Securities Act of 1933, as amended..."
        }
      ]
    }
  }
}
```

**Audience values:** `institutional_investor` | `ic_internal` | `rating_agency` | `trustee`
**Asset class values:** `US_CLO` | `EUR_CLO` | `US_MM_CLO`
**Region values:** `US` | `EU` | `UK`

**Errors:**
- `400 UNKNOWN_AUDIENCE` — audience value not recognised
- `400 UNKNOWN_ASSET_CLASS`
- `404 NO_PACK_FOUND` — no language pack exists for the given combination
- `410 PACK_EXPIRED` — language pack exists but is past its expiry date; must use newer version
- `503 LANGUAGE_LIBRARY_UNAVAILABLE`

---

### `get_required_disclosures`

Return the set of mandatory disclosure blocks that must appear in documents
distributed through a given channel.

**Request:**
```json
{
  "channel": "external_investor",
  "asset_class": "US_CLO",
  "region": "US"
}
```

**Response:**
```json
{
  "channel": "external_investor",
  "asset_class": "US_CLO",
  "region": "US",
  "source": "approved_language_library",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "required_disclosures": [
    {
      "block_id": "disc-not-registered",
      "label": "Securities Act Disclaimer",
      "mandatory": true,
      "placement": "footer",
      "text": "These securities have not been registered under the Securities Act of 1933, as amended..."
    },
    {
      "block_id": "disc-qualified-purchaser",
      "label": "Qualified Purchaser Notice",
      "mandatory": true,
      "placement": "cover",
      "text": "This document is being provided only to investors who are 'qualified purchasers'..."
    },
    {
      "block_id": "disc-forward-looking",
      "label": "Forward-Looking Statements",
      "mandatory": true,
      "placement": "header",
      "text": "This document contains forward-looking statements that are based on current expectations..."
    }
  ]
}
```

**Channel values:** `external_investor` | `rating_agency` | `trustee` | `internal`

**Errors:**
- `400 UNKNOWN_CHANNEL`
- `404 NO_DISCLOSURES_FOUND`
- `503 LANGUAGE_LIBRARY_UNAVAILABLE`

---

### `validate_language_usage`

Verify that the text blocks used in a draft all trace back to approved sources.
*(Phase 3+ — compliance-reviewer integration)*

**Request:**
```json
{
  "draft_id": "draft-abc123",
  "used_block_ids": ["rf-clo-credit-risk", "disc-not-registered", "disc-forward-looking"],
  "language_pack_id": "lp-us-clo-inst-2024-01",
  "channel": "external_investor"
}
```

**Response:**
```json
{
  "draft_id": "draft-abc123",
  "source": "approved_language_library",
  "valid": true,
  "issues": [],
  "missing_required": []
}
```

**Response (invalid):**
```json
{
  "draft_id": "draft-abc123",
  "source": "approved_language_library",
  "valid": false,
  "issues": [
    {
      "block_id": "disc-qualified-purchaser",
      "severity": "error",
      "code": "MISSING_REQUIRED_BLOCK",
      "message": "Required disclosure 'Qualified Purchaser Notice' is missing from the draft."
    }
  ],
  "missing_required": ["disc-qualified-purchaser"]
}
```

**Errors:**
- `404 PACK_NOT_FOUND`
- `503 LANGUAGE_LIBRARY_UNAVAILABLE`

---

## Security and provenance rules

- All responses carry `"source": "approved_language_library"`. Documents
  must cite `language_pack_id` and `block_id` for every approved text block
  used. Tag: `[retrieved]`.
- The document-drafter must not modify approved text blocks. It may only
  insert them verbatim or omit them with an explicit `[PLACEHOLDER]`.
- If `get_required_disclosures` returns blocks and the draft omits any
  `mandatory: true` block, the publish check must block.
- Language packs have an `effective_date` and may expire. The compliance
  hook must reject drafts built from expired packs.

---

## Phase timeline

| Phase | Action |
|---|---|
| 1–2 (current) | Disclosures are `[PLACEHOLDER]` sections in generated drafts |
| 3 prep | Add `mcp/approved_language/mock_language.py` with representative text blocks |
| 3 | Implement `infra/mcp/approved_language/server.py` |
| 3 | Update document-drafter to call `get_language_pack` before drafting external sections |
| 3 | Update compliance-reviewer to call `validate_language_usage` |
| 3 | Update publish_check_workflow to fail on missing required disclosures |

---

## Open questions

1. Is the approved language library a single system of record, or aggregated from legal/compliance/deal team sources?
2. How frequently do language packs update? (Quarterly regulatory updates? Deal-specific overrides?)
3. Should `validate_language_usage` be blocking in the pre_tool_use hook, or only advisory in compliance-review?
4. Are there deal-type-specific overrides (e.g., static CLO vs managed CLO have different risk factor language)?
