# Data Model & Auth Scopes Summary

## Overview

This document describes the data relationships, authentication scopes, and access patterns for the Chat with PDF backend.

## Authentication

### Clerk JWT Verification
- All protected routes require a valid Clerk JWT token in the `Authorization: Bearer <token>` header
- Token verification uses Clerk's JWKS endpoint to validate signatures
- Returns `clerk_user_id` (from token's `sub` claim) as the authenticated user identifier
- No session management required - stateless JWT-based authentication

### Auth Scopes

**Personal Scope:**
- User owns resources via `owner_clerk_user_id`
- Access limited to resources where `clerk_user_id = owner_clerk_user_id`

**Team Scope:**
- User is a member of a team (via `team_member` table)
- Access to team resources via `team_id`
- Role-based permissions: `owner`, `admin`, `member`

## Data Relationships

### Core Entities

```
User (Clerk)
  ├── PDF Documents (personal)
  │   └── PDF Chunks (with embeddings)
  ├── Teams (owned)
  │   ├── Team Members
  │   ├── PDF Documents (team)
  │   └── Subscriptions (team)
  ├── Subscriptions (personal)
  └── Usage Records (personal)
```

### Entity Relationships

#### 1. PDF Documents
- **Owner**: `owner_clerk_user_id` (required)
- **Team**: `team_id` (optional - null for personal, set for team documents)
- **Access Control**:
  - Personal: User must be the owner
  - Team: User must be a member of the team (any role)

#### 2. PDF Chunks
- **Parent**: `doc_id` → `pdf_document.id` (CASCADE delete)
- **Embedding**: Vector(1536) for OpenAI text-embedding-3-small
- **Page Range**: `page_from` to `page_to` for citation tracking
- **Access**: Inherited from parent document

#### 3. Teams
- **Owner**: `owner_clerk_user_id` (team creator)
- **Seat Limit**: Default 3, can be increased via subscription
- **Access Control**:
  - Owner: Full access
  - Admin: Manage members, view/edit documents
  - Member: View documents, upload documents

#### 4. Team Members
- **Composite Key**: `(team_id, clerk_user_id)`
- **Roles**: `owner`, `admin`, `member`
- **Access**: Determines permissions within team

#### 5. Subscriptions
- **Scope Types**:
  - `personal`: `owner_clerk_user_id` set, `team_id` null
  - `team`: `team_id` set, `owner_clerk_user_id` null
- **Products**: `starter`, `pro`, `team`
- **Status**: `active`, `canceled`, `past_due`, `trialing`
- **Seats**: `seat_limit` (base) + `extra_seats` (metered billing)

#### 6. Usage Tracking
- **Personal Usage**: `(clerk_user_id, month_tag)` - monthly credits
- **Team Usage**: `(team_id, month_tag)` - monthly credits
- **Month Tag**: Format "YYYY-MM" (e.g., "2025-01")
- **Credits**: `credits_total` (plan limit) vs `credits_used` (actual usage)

## Access Patterns

### Document Access
1. **Personal Documents**:
   ```sql
   WHERE owner_clerk_user_id = :clerk_user_id AND team_id IS NULL
   ```

2. **Team Documents**:
   ```sql
   WHERE team_id IN (
     SELECT team_id FROM team_member 
     WHERE clerk_user_id = :clerk_user_id
   )
   ```

### Subscription Access
1. **Personal Subscription**:
   ```sql
   WHERE scope_type = 'personal' 
     AND owner_clerk_user_id = :clerk_user_id
   ```

2. **Team Subscription**:
   ```sql
   WHERE scope_type = 'team' 
     AND team_id IN (
       SELECT team_id FROM team_member 
       WHERE clerk_user_id = :clerk_user_id
     )
   ```

### Usage Tracking
1. **Personal Usage**:
   ```sql
   WHERE clerk_user_id = :clerk_user_id 
     AND month_tag = :current_month
   ```

2. **Team Usage**:
   ```sql
   WHERE team_id IN (
     SELECT team_id FROM team_member 
     WHERE clerk_user_id = :clerk_user_id
   ) AND month_tag = :current_month
   ```

## Vector Search

### Embedding Storage
- **Model**: OpenAI `text-embedding-3-small`
- **Dimension**: 1536
- **Index**: HNSW (Hierarchical Navigable Small World) for cosine similarity
- **Search**: Find chunks with similar embeddings to query embedding

### Citation Format
- **Page Range**: `[p{page_from}–{page_to}]`
- **Example**: `[p3–4]` for content spanning pages 3-4

## Billing & Usage

### Credit Limits (by Product)
- **Starter**: 10 PDFs/month (personal)
- **Pro**: Unlimited PDFs (personal)
- **Team**: Unlimited PDFs (team), 3 base seats, +$5/extra seat

### Usage Tracking
- Monthly reset on `month_tag` change
- `credits_used` incremented on PDF upload/processing
- `credits_total` set based on active subscription

## Storage

### Supabase Storage
- **Path Structure**: `pdfs/{clerk_user_id}/{document_id}.pdf`
- **Team Paths**: `pdfs/teams/{team_id}/{document_id}.pdf`
- **Access**: Via Supabase Storage API with service role key

## Background Processing

### Celery Tasks
- **PDF Upload**: Extract text, chunk, generate embeddings
- **Async Processing**: Non-blocking for user requests
- **Redis**: Message broker and result backend

## Security Considerations

1. **JWT Verification**: All protected routes verify Clerk JWT
2. **Row-Level Security**: Access control via SQL WHERE clauses
3. **Team Membership**: Users can only access teams they belong to
4. **Document Ownership**: Users can only access their own or team documents
5. **Subscription Validation**: Check active subscription before allowing operations

## Database Indexes

- `pdf_document`: `owner_clerk_user_id`, `team_id`
- `pdf_chunk`: `doc_id`, `embedding` (HNSW vector index)
- `team`: `owner_clerk_user_id`
- `team_member`: Composite primary key `(team_id, clerk_user_id)`
- `subscription`: `scope_type`, `owner_clerk_user_id`, `team_id`
- `usage_personal`: Composite primary key `(clerk_user_id, month_tag)`
- `usage_team`: Composite primary key `(team_id, month_tag)`

