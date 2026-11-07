-- Apply with the backend table-owning role before deploying the new backend.
-- Transactional creation avoids a window of Data API access before RLS.
BEGIN;

CREATE TABLE "public"."OAuthLinkTransaction" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "verifierHash" TEXT NOT NULL,
    "stateHash" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "OAuthLinkTransaction_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "OAuthLinkTransaction_userId_fkey" FOREIGN KEY ("userId")
        REFERENCES "public"."User"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX "OAuthLinkTransaction_stateHash_key" ON "public"."OAuthLinkTransaction"("stateHash");
CREATE UNIQUE INDEX "OAuthLinkTransaction_userId_provider_key" ON "public"."OAuthLinkTransaction"("userId", "provider");
CREATE INDEX "OAuthLinkTransaction_expiresAt_idx" ON "public"."OAuthLinkTransaction"("expiresAt");

ALTER TABLE "public"."OAuthLinkTransaction" ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE "public"."OAuthLinkTransaction" FROM PUBLIC;
-- No browser policies. Prisma uses the trusted backend role, never anon or
-- authenticated. Revoke Supabase's default grants when those roles exist.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE "public"."OAuthLinkTransaction" FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE "public"."OAuthLinkTransaction" FROM authenticated;
    END IF;
END $$;

COMMIT;
