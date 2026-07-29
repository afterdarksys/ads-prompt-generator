-- Prompt Generator Pro Database Schema

-- Prompts Library
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    task TEXT NOT NULL,
    target VARCHAR(50) NOT NULL,
    tone VARCHAR(255),
    context TEXT,
    constraints TEXT,
    deliverables TEXT,
    generated_prompt TEXT,
    tags TEXT[] DEFAULT '{}',
    favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API Keys Storage
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Security Scans
CREATE TABLE IF NOT EXISTS security_scans (
    id VARCHAR(100) PRIMARY KEY,
    prompt_hash VARCHAR(64),
    target_model VARCHAR(100),
    scan_types TEXT[] DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'pending',
    results JSONB DEFAULT '{}',
    risk_score INTEGER,
    risk_level VARCHAR(20),
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Red Team Sessions
CREATE TABLE IF NOT EXISTS redteam_sessions (
    id VARCHAR(100) PRIMARY KEY,
    prompt_hash VARCHAR(64),
    target_model VARCHAR(100),
    attack_types TEXT[] DEFAULT '{}',
    tools TEXT[] DEFAULT '{}',
    iterations INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    results JSONB DEFAULT '{}',
    attacks_attempted INTEGER DEFAULT 0,
    attacks_successful INTEGER DEFAULT 0,
    vulnerability_score FLOAT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ART Attack Results
CREATE TABLE IF NOT EXISTS art_attacks (
    id VARCHAR(100) PRIMARY KEY,
    model_endpoint VARCHAR(500),
    attack_type VARCHAR(50),
    samples_count INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    results JSONB DEFAULT '{}',
    evasion_rate FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Security Findings (aggregated from all tools)
CREATE TABLE IF NOT EXISTS security_findings (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    source_task_id VARCHAR(100),
    finding_type VARCHAR(100),
    severity VARCHAR(20),
    confidence FLOAT,
    payload TEXT,
    target_model VARCHAR(100),
    description TEXT,
    mitigation TEXT,
    metadata JSONB DEFAULT '{}',
    reported_to_llmsecurity BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prompts_target ON prompts(target);
CREATE INDEX IF NOT EXISTS idx_prompts_favorite ON prompts(favorite);
CREATE INDEX IF NOT EXISTS idx_security_scans_status ON security_scans(status);
CREATE INDEX IF NOT EXISTS idx_redteam_sessions_status ON redteam_sessions(status);
CREATE INDEX IF NOT EXISTS idx_security_findings_source ON security_findings(source);
CREATE INDEX IF NOT EXISTS idx_security_findings_severity ON security_findings(severity);
