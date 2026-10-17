"""ADR-007 S4: aggregate monitor views and conditional least-privilege grants.

Roles and secrets belong to scripts/ops/db-roles.sql, never to Alembic.
Re-running upgrade() reconciles grants after an ops bootstrap. No role is
required for the initial deployment with the legacy DATABASE_URL.
"""
from alembic import op
import sqlalchemy as sa

revision = "z901a2b3c4d5"
down_revision = "y803a2b3c4d5"
branch_labels = None
depends_on = None

# Owner-rights views are intentional: callers cannot read their source tables.
# security_barrier prevents caller predicates from leaking source rows.
VIEWS = {
    "monitor_bill_health": """
        SELECT MAX(created_at) AS latest_created_at,
               MAX(GREATEST(COALESCE(parliament_vote_date, TIMESTAMP '1970-01-01'),
                            COALESCE(submitted_date, TIMESTAMP '1970-01-01')))
                   FILTER (WHERE source = 'PARLIAMENT' AND id NOT LIKE 'DEMO-%')
                   AS latest_parliament_activity,
               COUNT(*) FILTER (
                   WHERE status IN ('PARLIAMENT_VOTED', 'OPEN_END')
                     AND arweave_tx_id IS NULL AND party_votes_parliament IS NOT NULL
                     AND id NOT LIKE 'DEMO-%' AND source = 'PARLIAMENT'
                     AND (status_changed_at IS NULL OR status_changed_at < NOW() - INTERVAL '24 hours')
               ) AS arweave_pending,
               COUNT(*) FILTER (WHERE source IS NULL AND id NOT LIKE 'DEMO-%') AS null_source,
               COUNT(*) FILTER (WHERE governance_level IS NULL AND id NOT LIKE 'DEMO-%') AS null_governance
        FROM public.parliament_bills
    """,
    "monitor_lifecycle_stuck": """
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
                   'id', id, 'status', status, 'parliament_vote_date', parliament_vote_date
               )), '[]'::jsonb) AS bills
        FROM public.parliament_bills
        WHERE parliament_vote_date < NOW() - INTERVAL '1 day'
          AND COALESCE(updated_at, TIMESTAMP '1970-01-01') < NOW() - INTERVAL '30 minutes'
          AND status IN ('ANNOUNCED', 'ACTIVE', 'WINDOW_24H')
    """,
    "monitor_lifecycle_fast_forward": """
        WITH lifecycle AS (
            SELECT l.bill_id,
                   MIN(l.changed_at) FILTER (WHERE l.from_status = 'ANNOUNCED' AND l.to_status = 'ACTIVE') AS active_at,
                   MIN(l.changed_at) FILTER (WHERE l.from_status = 'ACTIVE' AND l.to_status = 'WINDOW_24H') AS window_at,
                   MIN(l.changed_at) FILTER (WHERE l.from_status = 'WINDOW_24H' AND l.to_status = 'PARLIAMENT_VOTED') AS voted_at
            FROM public.bill_status_logs l JOIN public.parliament_bills b ON b.id = l.bill_id
            WHERE l.changed_at > NOW() - INTERVAL '24 hours'
              AND b.id NOT LIKE 'DEMO-%' AND COALESCE(b.admin_hidden, FALSE) = FALSE
              AND COALESCE(b.source, 'PARLIAMENT') = 'PARLIAMENT'
            GROUP BY l.bill_id
        )
        SELECT bill_id, active_at, window_at, voted_at FROM lifecycle
        WHERE active_at IS NOT NULL AND window_at IS NOT NULL AND voted_at IS NOT NULL
          AND voted_at - window_at < INTERVAL '24 hours'
    """,
    "monitor_forum_missing": """
        WITH classified AS (
            SELECT id, title_el, CASE
                WHEN COALESCE(source, '') = 'ZK_CANARY' OR id LIKE 'ZK-CANARY-%' THEN 'technical_test'
                WHEN id LIKE 'DEMO-%' THEN 'demo_legacy'
                WHEN COALESCE(admin_hidden, FALSE) = TRUE THEN 'operator_hidden'
                WHEN source = 'DIAVGEIA' AND (
                    LOWER(COALESCE(title_el, '')) LIKE ANY (ARRAY['%αμκα%', '%α.μ.κ.α%', '%amka%', '%ασθεν%', '%εοπυυ%', '%eopyy%'])
                    OR LOWER(COALESCE(summary_short_el, '')) LIKE ANY (ARRAY['%αμκα%', '%α.μ.κ.α%', '%amka%', '%ασθεν%', '%εοπυυ%', '%eopyy%'])
                    OR LOWER(COALESCE(summary_long_el, '')) LIKE ANY (ARRAY['%αμκα%', '%α.μ.κ.α%', '%amka%', '%ασθεν%', '%εοπυυ%', '%eopyy%'])
                ) THEN 'sensitive_diavgeia'
                WHEN status IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END') AND (
                    (COALESCE(source, 'PARLIAMENT') = 'PARLIAMENT' AND created_at < NOW() - INTERVAL '1 hour')
                    OR (COALESCE(source, 'PARLIAMENT') != 'PARLIAMENT' AND created_at < NOW() - INTERVAL '6 hours')
                ) THEN 'public_actionable'
                WHEN status IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END') THEN 'sync_grace'
                ELSE 'lifecycle_not_eligible' END AS category
            FROM public.parliament_bills WHERE forum_topic_id IS NULL
        )
        SELECT category, COUNT(*) AS bill_count,
               COALESCE(jsonb_agg(jsonb_build_object('id', id, 'title_el', title_el))
                        FILTER (WHERE category = 'public_actionable'), '[]'::jsonb) AS actionable_bills
        FROM classified GROUP BY category
    """,
    "monitor_zk_pending": """
        SELECT r.vote_scope_id, root.group_size,
               FLOOR(EXTRACT(EPOCH FROM (NOW() - r.created_at)) / 3600) AS pending_hours,
               COALESCE(b.source = 'PARLIAMENT'
                   AND b.status::text IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END')
                   AND b.id NOT LIKE 'DEMO-%', FALSE) AS parliament_eligible,
               COUNT(*) AS receipt_count
        FROM public.zk_vote_receipts r
        LEFT JOIN public.parliament_bills b ON r.vote_scope_id = ('bill:' || b.id)
        JOIN public.zk_merkle_roots root ON root.vote_scope_id = r.vote_scope_id AND root.merkle_root = r.merkle_root
        WHERE r.arweave_pending = TRUE
          AND COALESCE(b.admin_hidden, FALSE) IS NOT TRUE AND COALESCE(b.source, '') <> 'ZK_CANARY'
        GROUP BY r.vote_scope_id, root.group_size, pending_hours, parliament_eligible
    """,
    "monitor_zk_health": """
        SELECT COUNT(*) AS invalid_roots FROM public.zk_merkle_roots
        WHERE status NOT IN ('OPEN', 'CLOSED', 'ARCHIVED')
    """,
}
RUNTIME_ROLES = ("ekklesia_api", "ekklesia_monitor", "ekklesia_dashboard", "ekklesia_backup")


def _exists(role: str) -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = :role)"
    ), {"role": role}).scalar())


def upgrade() -> None:
    for name, query in VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW public.{name} WITH (security_barrier = true) AS {query}")

    # PG14's public schema allows CREATE by default.
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    # Database-level ACLs are set by the bootstrap superuser in db-roles.sql;
    # the migrator deliberately does not own the database.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC")
    # Table-level REVOKE does not remove pre-existing column-level grants.
    op.execute("""DO $$ DECLARE a record; BEGIN
        FOR a IN SELECT DISTINCT c.relname, att.attname, acl.grantee,
                     CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(r.rolname) END AS grantee_name
                 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 JOIN pg_attribute att ON att.attrelid = c.oid
                 CROSS JOIN LATERAL aclexplode(att.attacl) acl
                 LEFT JOIN pg_roles r ON r.oid = acl.grantee
                 WHERE n.nspname = 'public' AND (acl.grantee = 0 OR r.rolname IN
                     ('ekklesia_api', 'ekklesia_monitor', 'ekklesia_dashboard', 'ekklesia_backup'))
        LOOP EXECUTE format('REVOKE ALL (%I) ON public.%I FROM %s', a.attname, a.relname, a.grantee_name); END LOOP;
    END $$""")
    for role in RUNTIME_ROLES:
        if not _exists(role):
            continue
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}")
        op.execute(f"REVOKE ALL ON SCHEMA public FROM {role}")
        op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")

    owners = [op.get_bind().execute(sa.text("SELECT current_user")).scalar_one()]
    if _exists("ekklesia_migrator") and "ekklesia_migrator" not in owners:
        owners.append("ekklesia_migrator")
    # Apply to both legacy and migrator creators during the transition.
    for owner in owners:
        quoted_owner = op.get_bind().dialect.identifier_preparer.quote(owner)
        prefix = f"ALTER DEFAULT PRIVILEGES FOR ROLE {quoted_owner} IN SCHEMA public"
        op.execute(f"{prefix} REVOKE ALL ON TABLES FROM PUBLIC")
        op.execute(f"{prefix} REVOKE ALL ON SEQUENCES FROM PUBLIC")
        for role in RUNTIME_ROLES:
            if _exists(role):
                op.execute(f"{prefix} REVOKE ALL ON TABLES FROM {role}")
                op.execute(f"{prefix} REVOKE ALL ON SEQUENCES FROM {role}")
        if _exists("ekklesia_api"):
            op.execute(f"{prefix} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ekklesia_api")
            op.execute(f"{prefix} GRANT USAGE, SELECT ON SEQUENCES TO ekklesia_api")
        if _exists("ekklesia_backup"):
            op.execute(f"{prefix} GRANT SELECT ON TABLES TO ekklesia_backup")
            op.execute(f"{prefix} GRANT SELECT ON SEQUENCES TO ekklesia_backup")

    if _exists("ekklesia_api"):
        # Grant only on base tables, never the Alembic version or reporting views.
        op.execute("""DO $$ DECLARE t record; BEGIN
            FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'
            LOOP EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO ekklesia_api', t.tablename); END LOOP;
        END $$""")
        op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ekklesia_api")
    if _exists("ekklesia_monitor"):
        for name in VIEWS:
            op.execute(f"GRANT SELECT ON public.{name} TO ekklesia_monitor")
    # Dashboard uses HTTP only (src/lib/api.ts and api/proxy); no views/grants.
    if _exists("ekklesia_backup"):
        op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO ekklesia_backup")
        op.execute("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ekklesia_backup")


def downgrade() -> None:
    # Keep ownership, DML/backup access and security revocations. Restoring
    # PUBLIC access would reopen sensitive data. Rollback uses the old URLs.
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS public.{name}")
