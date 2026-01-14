# Data Model & Schema Definitions

## Regulation Document Schema

```sql
-- Documents table
CREATE TABLE regulations (
    document_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL,
    publication_date DATE NOT NULL,
    effective_date DATE,
    enforcement_date DATE,
    regulatory_body VARCHAR(200) NOT NULL,
    document_type VARCHAR(50) NOT NULL, -- RTS, MOU, Guidance, Amendment, etc.
    asset_classes TEXT, -- JSON array
    document_url VARCHAR(2000),
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    parent_document_id VARCHAR(255), -- For amendments/versions
    full_text LONGTEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_jurisdiction (jurisdiction),
    INDEX idx_publication_date (publication_date),
    INDEX idx_document_type (document_type),
    FULLTEXT KEY ft_search (title, summary)
);

-- Document versions/amendments table
CREATE TABLE regulation_versions (
    version_id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    version_number VARCHAR(20) NOT NULL,
    published_date DATE NOT NULL,
    change_summary TEXT,
    change_type ENUM('NEW', 'AMENDMENT', 'REPEAL', 'CLARIFICATION'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES regulations(document_id),
    UNIQUE KEY unique_doc_version (document_id, version_number),
    INDEX idx_document_id (document_id)
);

-- Document chunks for RAG
CREATE TABLE regulation_chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    version_number VARCHAR(20) NOT NULL,
    chunk_text LONGTEXT NOT NULL,
    page_number INT,
    section VARCHAR(50), -- E.g., "Article 15.2"
    subsection VARCHAR(50),
    chunk_sequence INT,
    token_count INT,
    embedding_vector JSON, -- Store as JSON for flexibility
    embedding_dimensions INT,
    relevance_metadata JSON, -- {obligation_type, entities, key_terms}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES regulations(document_id),
    INDEX idx_document_id (document_id),
    INDEX idx_section (section),
    FULLTEXT KEY ft_chunk_search (chunk_text)
);

-- Relationships between regulations
CREATE TABLE regulation_relationships (
    relationship_id VARCHAR(255) PRIMARY KEY,
    source_document_id VARCHAR(255) NOT NULL,
    related_document_id VARCHAR(255) NOT NULL,
    relationship_type ENUM('AMENDS', 'REFERENCES', 'SUPERSEDES', 'CLARIFIES', 'RELATED_TOPIC'),
    description VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_document_id) REFERENCES regulations(document_id),
    FOREIGN KEY (related_document_id) REFERENCES regulations(document_id),
    INDEX idx_source_doc (source_document_id),
    INDEX idx_related_doc (related_document_id)
);
```

## User & Query Schema

```sql
-- Users table
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    organization_id VARCHAR(255),
    role ENUM('ANALYST', 'MANAGER', 'ADMIN', 'TECHNOLOGY_LEAD'),
    jurisdictions_assigned JSON, -- Array of jurisdiction codes
    business_lines_assigned JSON, -- Array of business line codes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_email (email),
    INDEX idx_organization_id (organization_id)
);

-- Organizations
CREATE TABLE organizations (
    organization_id VARCHAR(255) PRIMARY KEY,
    organization_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    country VARCHAR(50),
    team_size INT,
    subscription_tier ENUM('TRIAL', 'STANDARD', 'PREMIUM', 'ENTERPRISE'),
    max_concurrent_users INT,
    subscription_start_date DATE,
    subscription_end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_name (organization_name)
);

-- Queries (audit trail)
CREATE TABLE user_queries (
    query_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    query_text LONGTEXT NOT NULL,
    query_type ENUM('SEARCH', 'ANALYSIS', 'COMPARE', 'BROWSE'),
    filters_applied JSON, -- {jurisdictions, document_types, date_range, etc}
    result_count INT,
    top_result_score FLOAT,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_query_type (query_type)
);

-- Query Results (for retrieval quality assessment)
CREATE TABLE query_results (
    result_id VARCHAR(255) PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    rank INT, -- Position in result set (1 = first)
    relevance_score FLOAT, -- From vector similarity (0-1)
    user_rated_relevance INT, -- 1-5 rating from user (optional)
    was_helpful BOOLEAN, -- Did user rate this result as useful?
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_id) REFERENCES user_queries(query_id),
    FOREIGN KEY (chunk_id) REFERENCES regulation_chunks(chunk_id),
    INDEX idx_query_id (query_id),
    INDEX idx_user_rated (user_rated_relevance)
);

-- Saved analyses (user work products)
CREATE TABLE analyses (
    analysis_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    regulation_document_id VARCHAR(255) NOT NULL,
    analysis_status ENUM('DRAFT', 'SUBMITTED', 'APPROVED', 'ARCHIVED'),
    impact_summary LONGTEXT,
    affected_business_lines JSON,
    affected_systems JSON,
    implementation_deadline DATE,
    estimated_effort_hours INT,
    citations JSON, -- [{chunk_id, quote, page}, ...]
    owner_user_id VARCHAR(255), -- For manager review
    assigned_to_user_id VARCHAR(255), -- For task assignment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    approved_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id),
    FOREIGN KEY (regulation_document_id) REFERENCES regulations(document_id),
    INDEX idx_organization_id (organization_id),
    INDEX idx_status (analysis_status),
    INDEX idx_deadline (implementation_deadline)
);
```

## Analytics Schema

```sql
-- Daily metrics snapshot (for dashboards)
CREATE TABLE daily_metrics (
    metric_date DATE,
    organization_id VARCHAR(255),
    active_users INT,
    total_queries INT,
    avg_search_latency_ms INT,
    search_relevance_avg_rating FLOAT,
    citation_accuracy_pct FLOAT,
    analyses_completed INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (metric_date, organization_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id)
);
```

## Key Design Decisions

1. **Embeddings Storage**: Stored as JSON blobs to enable flexible vector DB changes (Weaviate/Pinecone/Milvus)
2. **Audit Trail**: All queries logged for compliance and quality assessment
3. **Chunk Granularity**: Paragraph-level chunks with section metadata preserved
4. **Relationship Tracking**: Explicit table for regulation relationships (amends, references, supersedes)
5. **Version Control**: Support for multiple versions of same regulation (amendments tracked)
6. **Multi-tenancy**: organization_id in key tables for SaaS multi-tenant isolation

## Indices Strategy

**Search Optimization:**
- FULLTEXT indices on document text for keyword matching
- Regular indices on jurisdiction, document_type, publication_date for filtering
- Composite indices on commonly combined filters

**Query Performance:**
- user_id and organization_id indexed for query audit trails
- created_at indexed for time-range queries in analytics
- FK indices for join operations
