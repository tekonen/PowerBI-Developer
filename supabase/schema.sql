-- Supabase schema for PBI Developer
-- Run this in the Supabase SQL Editor to set up the database.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- user_settings: per-user configuration (sensitive fields encrypted)
-- ============================================================
CREATE TABLE public.user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Claude / AI config
    claude_api_key_encrypted TEXT,
    claude_base_url TEXT DEFAULT '',
    claude_model TEXT DEFAULT 'claude-sonnet-4-20250514',
    claude_max_tokens INT DEFAULT 8192,
    claude_temperature NUMERIC(3,2) DEFAULT 0.2,
    -- Power BI credentials
    pbi_tenant_id_encrypted TEXT,
    pbi_client_id_encrypted TEXT,
    pbi_client_secret_encrypted TEXT,
    pbi_workspace_id TEXT DEFAULT '',
    -- Snowflake credentials
    sf_account_encrypted TEXT,
    sf_user_encrypted TEXT,
    sf_password_encrypted TEXT,
    sf_warehouse TEXT DEFAULT '',
    sf_database TEXT DEFAULT '',
    sf_schema TEXT DEFAULT '',
    -- Report style preferences
    color_palette JSONB DEFAULT '["#118DFF","#12239E","#E66C37","#6B007B","#E044A7","#744EC2","#D9B300","#D64550"]',
    preferred_visuals JSONB DEFAULT '["card","clusteredBarChart","lineChart","table","slicer"]',
    page_width INT DEFAULT 1280,
    page_height INT DEFAULT 720,
    max_visuals_per_page INT DEFAULT 8,
    -- Metadata
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

-- ============================================================
-- runs: pipeline run history (replaces runs.json)
-- ============================================================
CREATE TABLE public.runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    report_name TEXT DEFAULT 'Report',
    dry_run BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed')),
    stages JSONB DEFAULT '{}',
    output_path TEXT,
    tokens JSONB DEFAULT '{"input_tokens":0,"output_tokens":0}',
    cost_usd NUMERIC(10,6) DEFAULT 0.0,
    latency_ms NUMERIC(12,2) DEFAULT 0.0,
    error TEXT,
    wizard_step TEXT DEFAULT 'init'
);

CREATE INDEX idx_runs_user_id ON public.runs(user_id);
CREATE INDEX idx_runs_created_at ON public.runs(created_at DESC);

-- ============================================================
-- run_files: tracks uploaded input files per run
-- ============================================================
CREATE TABLE public.run_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES public.runs(run_id) ON DELETE CASCADE,
    file_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    original_name TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_run_files_run_id ON public.run_files(run_id);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.run_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own settings"
    ON public.user_settings FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own runs"
    ON public.runs FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own run files"
    ON public.run_files FOR ALL
    USING (
        run_id IN (SELECT r.run_id FROM public.runs r WHERE r.user_id = auth.uid())
    )
    WITH CHECK (
        run_id IN (SELECT r.run_id FROM public.runs r WHERE r.user_id = auth.uid())
    );

-- ============================================================
-- Supabase Storage bucket (run via dashboard or uncomment below)
-- ============================================================
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('run-uploads', 'run-uploads', false);

-- ============================================================
-- Auto-update trigger for updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_settings_updated_at
    BEFORE UPDATE ON public.user_settings
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- Helper: encrypt/decrypt credentials via server-side key
-- Called via supabase RPC from the application.
-- ============================================================
CREATE OR REPLACE FUNCTION public.encrypt_value(plain_text TEXT, encryption_key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN encode(pgp_sym_encrypt(plain_text, encryption_key), 'base64');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.decrypt_value(cipher_text TEXT, encryption_key TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN pgp_sym_decrypt(decode(cipher_text, 'base64'), encryption_key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
