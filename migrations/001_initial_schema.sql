-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create pdf_document table
CREATE TABLE IF NOT EXISTS pdf_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_clerk_user_id VARCHAR NOT NULL,
    team_id UUID,
    title VARCHAR NOT NULL,
    num_pages INTEGER NOT NULL DEFAULT 0,
    storage_path VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pdf_document_owner ON pdf_document(owner_clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_pdf_document_team ON pdf_document(team_id);
CREATE INDEX IF NOT EXISTS idx_pdf_document_status ON pdf_document(status);

-- Create pdf_chunk table with vector embedding
CREATE TABLE IF NOT EXISTS pdf_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES pdf_document(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    page_from INTEGER NOT NULL,
    page_to INTEGER NOT NULL,
    embedding vector(1536) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pdf_chunk_doc ON pdf_chunk(doc_id);
-- Vector similarity search index (using HNSW for performance)
CREATE INDEX IF NOT EXISTS idx_pdf_chunk_embedding ON pdf_chunk USING hnsw (embedding vector_cosine_ops);

-- Create team table
CREATE TABLE IF NOT EXISTS team (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_clerk_user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    seat_limit INTEGER NOT NULL DEFAULT 3,
    clerk_organization_id VARCHAR UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_team_owner ON team(owner_clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_team_clerk_org ON team(clerk_organization_id);

-- Create team_member table
CREATE TABLE IF NOT EXISTS team_member (
    team_id UUID NOT NULL REFERENCES team(id) ON DELETE CASCADE,
    clerk_user_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (team_id, clerk_user_id)
);

-- Create subscription table
CREATE TABLE IF NOT EXISTS subscription (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_subscription_id VARCHAR NOT NULL UNIQUE,
    scope_type VARCHAR NOT NULL CHECK (scope_type IN ('personal', 'team')),
    owner_clerk_user_id VARCHAR,
    team_id UUID REFERENCES team(id) ON DELETE CASCADE,
    product VARCHAR NOT NULL CHECK (product IN ('starter', 'pro', 'team')),
    status VARCHAR NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'trialing')),
    current_period_end TIMESTAMP WITH TIME ZONE,
    seat_limit INTEGER NOT NULL DEFAULT 3,
    extra_seats INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscription_scope ON subscription(scope_type);
CREATE INDEX IF NOT EXISTS idx_subscription_owner ON subscription(owner_clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_team ON subscription(team_id);

-- Create usage_personal table
CREATE TABLE IF NOT EXISTS usage_personal (
    clerk_user_id VARCHAR NOT NULL,
    month_tag VARCHAR NOT NULL,
    credits_total INTEGER NOT NULL DEFAULT 0,
    credits_used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (clerk_user_id, month_tag)
);

-- Create usage_team table
CREATE TABLE IF NOT EXISTS usage_team (
    team_id UUID NOT NULL REFERENCES team(id) ON DELETE CASCADE,
    month_tag VARCHAR NOT NULL,
    credits_total INTEGER NOT NULL DEFAULT 0,
    credits_used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (team_id, month_tag)
);

