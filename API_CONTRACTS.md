# API Contracts - Chat with PDF

## Phase 3: Document Upload & Management

### Upload PDF

**Endpoint:** `POST /api/documents/upload`

**Auth:** Required (Bearer token)

**Request:**
```http
POST /api/documents/upload
Authorization: Bearer <clerk_jwt_token>
Content-Type: multipart/form-data

file: <pdf_file>
team_id: <optional_uuid>
```

**Response (202 Accepted):**
```json
{
  "message": "PDF uploaded successfully. Processing in background.",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing"
}
```

**Errors:**
- `400 Bad Request`: Invalid file type or size (>10MB)
- `401 Unauthorized`: Invalid or missing token
- `500 Internal Server Error`: Upload or storage failure

---

### List Documents

**Endpoint:** `GET /api/documents/`

**Auth:** Required (Bearer token)

**Request:**
```http
GET /api/documents/
Authorization: Bearer <clerk_jwt_token>
```

**Response (200 OK):**
```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "example.pdf",
      "num_pages": 10,
      "status": "ready",
      "created_at": "2024-11-07T10:30:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "title": "another.pdf",
      "num_pages": 0,
      "status": "processing",
      "created_at": "2024-11-07T11:00:00Z"
    }
  ]
}
```

**Status values:**
- `processing`: PDF is being extracted, chunked, and embedded
- `ready`: PDF is ready for chat
- `failed`: Processing failed

---

### Get Single Document

**Endpoint:** `GET /api/documents/{document_id}`

**Auth:** Required (Bearer token)

**Request:**
```http
GET /api/documents/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <clerk_jwt_token>
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "example.pdf",
  "num_pages": 10,
  "status": "ready",
  "created_at": "2024-11-07T10:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid document ID format
- `404 Not Found`: Document not found or no access
- `401 Unauthorized`: Invalid or missing token

---

## Phase 4: RAG Chat Interface

### Ask Question (RAG)

**Endpoint:** `POST /api/documents/{document_id}/ask`

**Auth:** Required (Bearer token)

**Request:**
```http
POST /api/documents/550e8400-e29b-41d4-a716-446655440000/ask
Authorization: Bearer <clerk_jwt_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "question": "What was the revenue in Q4?",
  "k": 5
}
```

**Parameters:**
- `question` (required, string): The user's question
- `k` (optional, integer): Number of chunks to retrieve (default: 5, max: 10)

**Response (200 OK):**
```json
{
  "answer": "The revenue was $2.5M in Q4 [p12]. The growth rate was 15% year-over-year [p13–14].",
  "citations": ["[p12]", "[p13–14]"],
  "context_used": 3,
  "similarity_scores": [0.89, 0.85, 0.78]
}
```

**Response Fields:**
- `answer` (string): The generated answer with inline citations
- `citations` (array of strings): Extracted page citations in format `[pX]` or `[pX–Y]`
- `context_used` (integer): Number of chunks used as context (may be less than `k` if similarity threshold not met)
- `similarity_scores` (array of floats): Cosine similarity scores for retrieved chunks (0-1 scale)

**Special Responses:**

*No relevant information found:*
```json
{
  "answer": "I can't find relevant information about that in the document. The question may be outside the scope of this PDF.",
  "citations": [],
  "context_used": 0,
  "similarity_scores": []
}
```

*Information not in document:*
```json
{
  "answer": "I can't find that information in the document.",
  "citations": [],
  "context_used": 2,
  "similarity_scores": [0.65, 0.62]
}
```

**Errors:**
- `400 Bad Request`: Invalid document ID or document not ready
  ```json
  {
    "detail": "Document is not ready for chat. Current status: processing"
  }
  ```
- `404 Not Found`: Document not found or no access
  ```json
  {
    "detail": "Document not found or you don't have access"
  }
  ```
- `401 Unauthorized`: Invalid or missing token
- `500 Internal Server Error`: Embedding, search, or OpenAI failure

---

## Phase 5: Billing & Usage Enforcement

### Clerk Billing Webhook

**Endpoint:** `POST /api/billing/webhook`

**Auth:** Clerk Svix signature (`svix-id`, `svix-timestamp`, `svix-signature`)

**Purpose:** Sync subscription status and reset usage when invoices are paid.

**Handled Events:**
- `billing.subscription.created`
- `billing.subscription.updated`
- `billing.subscription.deleted`
- `billing.invoice.paid`

**Behaviour:**
- Upserts subscription record (`subscription` table)
- Updates team seat limits (`team.seat_limit`)
- Resets usage credit totals for the current billing month (`usage_personal`, `usage_team`)

No response body beyond `{ "ok": true }`.

---

### Create Checkout Session

**Endpoint:** `POST /api/billing/checkout`

**Auth:** Required (Bearer token)

**Request:**
```http
POST /api/billing/checkout
Authorization: Bearer <clerk_jwt>
Content-Type: application/json

{
  "price_id": "starter_monthly",
  "scope": "personal",
  "clerk_user_id": "user_123",
  "success_url": "https://app.localhost/account",
  "cancel_url": "https://app.localhost/pricing"
}
```

**Response (200 OK):**
```json
{
  "url": "https://billing.clerk.com/session/..."
}
```

**Errors:**
- `400`: Unknown plan or missing required identifiers
- `502`: Clerk API error creating billing session

---

### Create Billing Portal Session

**Endpoint:** `POST /api/billing/portal`

**Auth:** Required (Bearer token)

**Request:**
```http
{
  "entity_id": "user_123",
  "entity_type": "user",
  "return_url": "https://app.localhost/account"
}
```

For team billing portals use `entity_type: "organization"` and provide `clerk_organization_id`.

**Response:**
```json
{
  "url": "https://billing.clerk.com/portal/..."
}
```

---

### Get Subscription & Usage Summary

**Endpoint:** `GET /api/subscriptions/`

**Auth:** Required (Bearer token)

**Response (200 OK):**
```json
{
  "personal": {
    "subscription": {
      "subscription_id": "sub_123",
      "scope_type": "personal",
      "product": "starter",
      "status": "active",
      "seat_limit": 1,
      "extra_seats": 0,
      "current_period_end": "2025-02-05T10:00:00Z",
      "monthly_credits": 100,
      "extra_seat_credit": 0
    },
    "credits_remaining": 74,
    "credits_total": 100,
    "month_tag": "2025-02"
  },
  "teams": [
    {
      "team": {
        "id": "7c1b...",
        "name": "Research",
        "seat_limit": 5
      },
      "subscription": {
        "subscription_id": "sub_456",
        "status": "active",
        "scope_type": "team",
        "product": "team",
        "seat_limit": 5,
        "extra_seats": 2,
        "current_period_end": "2025-02-05T10:00:00Z",
        "monthly_credits": 200,
        "extra_seat_credit": 50
      },
      "credits_remaining": 120,
      "credits_total": 300,
      "month_tag": "2025-02"
    }
  ]
}
```

---

### Invite Team Member (Seat Enforcement)

**Endpoint:** `POST /api/teams/{team_id}/invite`

**Auth:** Required (Bearer token) — only team owner may invite.

**Request:**
```http
POST /api/teams/7c1b.../invite
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "teammate@example.com"
}
```

**Response (200 OK):**
```json
{
  "status": "pending",
  "email": "teammate@example.com",
  "message": "Seat available. Invitation workflow not implemented yet."
}
```

**Errors:**
- `403`: Seat limit reached or caller is not team owner
- `404`: Team not found

---

### Usage Enforcement in `/api/documents/{doc_id}/ask`

If the monthly credit quota is exhausted, the endpoint returns:

```json
{
  "answer": "You've used all 100 monthly chat credits on the Starter plan. Visit /pricing to upgrade or wait for the next billing cycle.",
  "citations": [],
  "context_used": 0,
  "similarity_scores": []
}
```

HTTP status remains 200 so the UI can render the friendly upgrade message.

---

## RAG Implementation Details

### Flow:

1. **Authentication**: Verify JWT token → extract `clerk_user_id`
2. **Authorization**: Check document ownership (or team membership if `team_id` set)
3. **Status Check**: Verify document status is `ready`
4. **Embedding**: Generate query embedding using `text-embedding-3-small`
5. **Vector Search**: 
   - Use pgvector cosine similarity (`<=>` operator)
   - Retrieve top-k chunks
   - Apply similarity threshold (0.70)
6. **Context Building**: Format chunks with page ranges
7. **Prompt Engineering**: Strict RAG prompt with citation requirements
8. **Chat Completion**: Call `gpt-4o-mini` with context
9. **Citation Extraction**: Parse answer for `[pX]` and `[pX–Y]` patterns
10. **Response**: Return answer with citations and metadata

### Similarity Threshold:

- **Minimum score**: 0.70 (cosine similarity on 0-1 scale)
- **Below threshold**: Chunks are excluded
- **No chunks pass threshold**: Return "can't find relevant information" message

### Citation Format:

- Single page: `[p3]`
- Page range: `[p3–4]` (en-dash)
- Multiple citations: `[p3] ... [p5–6]` (inline in answer)

### Prompt Strategy:

The system uses a strict RAG prompt that:
- Explicitly forbids external knowledge
- Requires citations for all facts
- Instructs to say "I can't find that..." if info not present
- Shows examples of good vs. bad answers

---

## Example Usage Flow

### Complete Chat Session Example:

```bash
# 1. Upload a PDF
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@report.pdf"

# Response:
# {
#   "message": "PDF uploaded successfully. Processing in background.",
#   "document_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "processing"
# }

# 2. Check status (poll until ready)
curl http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>"

# Response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "title": "report.pdf",
#   "num_pages": 25,
#   "status": "ready",
#   "created_at": "2024-11-07T10:30:00Z"
# }

# 3. Ask a question
curl -X POST http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000/ask \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was the Q4 revenue?",
    "k": 5
  }'

# Response:
# {
#   "answer": "The Q4 revenue was $2.5M [p12], representing a 15% increase year-over-year [p13].",
#   "citations": ["[p12]", "[p13]"],
#   "context_used": 3,
#   "similarity_scores": [0.91, 0.87, 0.82]
# }
```

---

## Frontend Integration

### Authentication:

All requests must include the Clerk JWT token from the "pdfs" template:

```typescript
const token = await getToken({ template: "pdfs" });

fetch(`${API_URL}/api/documents/...`, {
  headers: {
    Authorization: `Bearer ${token}`,
  },
});
```

### Chat Message Format:

```typescript
interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
}
```

### Citation Rendering:

Citations should be clickable buttons that navigate to the PDF viewer at the specified page (future Phase 5 feature).

---

## Performance Considerations

### Response Times:

- **Upload**: < 1s (PDF storage only)
- **Processing**: 10-60s (depends on PDF size)
- **Chat**: 2-5s (embedding + search + GPT-4o-mini)

### Rate Limits:

- Inherited from OpenAI API limits
- Consider implementing per-user rate limiting in future

### Token Usage:

- Embedding: ~$0.00002 per query
- Chat: ~$0.0001-0.0005 per question (depends on context size)

---

## Next Phases

**Phase 5**: PDF Viewer with click-to-page navigation
**Phase 6**: Teams, subscriptions, and usage tracking (Clerk Billing)
