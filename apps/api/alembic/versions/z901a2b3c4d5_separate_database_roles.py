"""ADR-007 S4: aggregate monitor views and conditional least-privilege grants.

Roles and secrets belong to scripts/ops/db-roles.sql, never to Alembic.
Re-running upgrade() reconciles grants after an ops bootstrap. Without the
non-login aggregate owner, views remain private to the legacy access path.
"""
from alembic import op
import sqlalchemy as sa
from services.small_cell import small_cell_k

revision = "z901a2b3c4d5"
down_revision = "y803a2b3c4d5"
branch_labels = None
depends_on = None

# Limited readers use non-inlined SECURITY DEFINER functions. A view's
# security_barrier alone still exposes pre-suppression rows through EXPLAIN,
# so fallback views must never be granted to monitor/dashboard.
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
        WITH visible_bills AS (
            SELECT id, status FROM public.parliament_bills
            WHERE COALESCE(admin_hidden, FALSE) = FALSE
              AND COALESCE(source, 'PARLIAMENT') = 'PARLIAMENT'
              AND id NOT LIKE 'DEMO-%' AND id NOT LIKE 'ZK-CANARY-%'
              AND NOT (status::text = 'ACTIVE' AND COALESCE(results_visibility, 'HIDDEN') = 'HIDDEN')
        ), events AS (
            SELECT 'bill:' || v.bill_id AS vote_scope_id, v.vote::text AS choice,
                   'tier1' AS source, v.created_at AT TIME ZONE 'UTC' AS created_at,
                   NULL::integer AS group_size, NULL::boolean AS arweave_pending
            FROM public.citizen_votes v JOIN visible_bills b ON b.id = v.bill_id
            UNION ALL
            SELECT r.vote_scope_id, r.vote_commitment, 'zk', r.created_at,
                   root.group_size, r.arweave_pending
            FROM public.zk_vote_receipts r
            JOIN visible_bills b ON r.vote_scope_id = ('bill:' || b.id)
            LEFT JOIN public.zk_merkle_roots root
              ON root.vote_scope_id = r.vote_scope_id AND root.merkle_root = r.merkle_root
        ), source_cells AS (
            -- publishable_set: all four choices, including zero, in every
            -- present source. Safe sources also imply safe combined cells.
            SELECT vote_scope_id, source,
                   COUNT(*) FILTER (WHERE choice = 'YES') AS yes_count,
                   COUNT(*) FILTER (WHERE choice = 'NO') AS no_count,
                   COUNT(*) FILTER (WHERE choice = 'ABSTAIN') AS abstain_count,
                   COUNT(*) FILTER (WHERE choice = 'UNKNOWN') AS unknown_count
            FROM events GROUP BY vote_scope_id, source
        ), partitions AS (
            -- Use fixed UTC hours, never rolling receipt-age boundaries.
            -- Include published receipts: a small nonpending complement must
            -- not be recoverable from public source totals minus pending.
            SELECT vote_scope_id, source, group_size, arweave_pending,
                   DATE_TRUNC('hour', created_at AT TIME ZONE 'UTC') AS receipt_hour,
                   COUNT(*) AS receipt_count,
                   BOOL_AND(choice IN ('YES', 'NO', 'ABSTAIN', 'UNKNOWN')) AS valid_choices,
                   COUNT(*) FILTER (WHERE choice = 'YES') AS yes_count,
                   COUNT(*) FILTER (WHERE choice = 'NO') AS no_count,
                   COUNT(*) FILTER (WHERE choice = 'ABSTAIN') AS abstain_count,
                   COUNT(*) FILTER (WHERE choice = 'UNKNOWN') AS unknown_count
            FROM events
            GROUP BY vote_scope_id, source, group_size, arweave_pending, receipt_hour
        ), safe_scopes AS (
            SELECT vote_scope_id FROM source_cells GROUP BY vote_scope_id
            HAVING BOOL_AND(LEAST(yes_count, no_count, abstain_count, unknown_count) >= __SUPPRESSION_K__)
        ), safe_partitions AS (
            -- Withhold the whole scope if any partition is small; filtering
            -- individual buckets alone would allow complementary subtraction.
            SELECT vote_scope_id FROM partitions GROUP BY vote_scope_id
            HAVING BOOL_AND(LEAST(yes_count, no_count, abstain_count, unknown_count) >= __SUPPRESSION_K__
                AND valid_choices AND receipt_hour IS NOT NULL
                AND (source <> 'zk' OR (group_size IS NOT NULL AND group_size >= __SUPPRESSION_K__)))
        )
        -- Preserve the existing view's varchar(128) output for reconciliation.
        SELECT p.vote_scope_id::varchar(128) AS vote_scope_id, p.group_size,
               FLOOR(EXTRACT(EPOCH FROM (NOW() - ((p.receipt_hour + INTERVAL '1 hour') AT TIME ZONE 'UTC'))) / 3600) AS pending_hours,
               b.status::text IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END') AS parliament_eligible,
               p.receipt_count
        FROM partitions p JOIN visible_bills b ON p.vote_scope_id = ('bill:' || b.id)
        WHERE p.source = 'zk' AND p.arweave_pending = TRUE AND p.group_size IS NOT NULL
          AND (__SUPPRESSION_K__ = 0 OR (
              p.vote_scope_id IN (SELECT vote_scope_id FROM safe_scopes)
              AND p.vote_scope_id IN (SELECT vote_scope_id FROM safe_partitions)))
    """,
    "monitor_zk_health": """
        SELECT COUNT(*) AS invalid_roots FROM public.zk_merkle_roots
        WHERE status NOT IN ('OPEN', 'CLOSED', 'ARCHIVED')
    """,
}
RUNTIME_ROLES = ("ekklesia_api", "ekklesia_monitor", "ekklesia_dashboard", "ekklesia_backup")
AGGREGATE_OWNER = "ekklesia_monitor_owner"
AGGREGATE_SOURCES = ("parliament_bills", "bill_status_logs", "citizen_votes", "zk_vote_receipts", "zk_merkle_roots")


def _exists(role: str) -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = :role)"
    ), {"role": role}).scalar())


def upgrade() -> None:
    has_owner = _exists(AGGREGATE_OWNER)
    if has_owner and op.get_bind().execute(sa.text("""
        SELECT r.rolcanlogin OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
               OR EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles member ON member.oid = m.member
                          WHERE m.member = r.oid OR (m.roleid = r.oid AND member.rolname <> 'ekklesia_migrator'))
        FROM pg_roles r WHERE r.rolname = :role
    """), {"role": AGGREGATE_OWNER}).scalar():
        raise RuntimeError("Unsafe aggregate owner; rerun scripts/ops/db-roles.sh as bootstrap superuser")
    # Freeze the release threshold in owner-controlled SQL. A reader must not
    # be able to weaken it via SET, a connection option or its own environment.
    threshold = str(small_cell_k())
    # CREATE is needed only while installing functions as their dedicated owner.
    if has_owner:
        op.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {AGGREGATE_OWNER}")
    for name, query in VIEWS.items():
        query = query.replace("__SUPPRESSION_K__", threshold)
        # Infer the deployed column types, preserving typmods when replacing
        # existing views. With an owner, this raw definition is replaced in
        # the same transaction; without one it remains private to legacy use.
        op.execute(f"CREATE OR REPLACE VIEW public.{name} WITH (security_barrier = true) AS {query}")
        if not has_owner:
            # Preserve legacy monitoring via DATABASE_URL, without exposing
            # source plans to limited roles. Restores with --no-acl also give
            # PUBLIC function EXECUTE: close that path even without an owner.
            function = f"public.{name}_aggregate()"
            if op.get_bind().execute(sa.text(
                "SELECT to_regprocedure(:function) IS NOT NULL"
            ), {"function": function}).scalar():
                op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
                for role in RUNTIME_ROLES:
                    if _exists(role):
                        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM {role}")
            continue
        columns = op.get_bind().execute(sa.text("""
            SELECT attname, format_type(atttypid, atttypmod)
            FROM pg_attribute WHERE attrelid = CAST(:view AS regclass)
              AND attnum > 0 AND NOT attisdropped ORDER BY attnum
        """), {"view": f"public.{name}"}).all()
        quote = op.get_bind().dialect.identifier_preparer.quote
        returns = ", ".join(f"{quote(column)} {kind}" for column, kind in columns)
        projection = ", ".join(f"r.{quote(column)}::{kind} AS {quote(column)}" for column, kind in columns)
        function = f"public.{name}_aggregate()"
        # SET ROLE is confined to a single statement and restored even when
        # reapplying as the NOINHERIT migrator. SECURITY DEFINER prevents SQL
        # inlining, so caller EXPLAIN sees only released Function Scan rows.
        grants = f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC;"
        for role in RUNTIME_ROLES:
            if _exists(role):
                grants += f" REVOKE ALL ON FUNCTION {function} FROM {role};"
        if _exists("ekklesia_monitor"):
            grants += f" GRANT EXECUTE ON FUNCTION {function} TO ekklesia_monitor;"
        op.execute(f"""DO $install$
            DECLARE installer name := current_user;
            BEGIN
                SET LOCAL ROLE {AGGREGATE_OWNER};
                EXECUTE $ddl$CREATE OR REPLACE FUNCTION {function}
                    RETURNS TABLE ({returns}) LANGUAGE sql SECURITY DEFINER
                    SET search_path = pg_catalog, public
                    AS $body${query}$body$ $ddl$;
                {grants}
                EXECUTE format('SET LOCAL ROLE %I', installer);
            END $install$""")
        op.execute(f"CREATE OR REPLACE VIEW public.{name} WITH (security_barrier = true) AS SELECT {projection} FROM {function} r")
    if has_owner:
        op.execute(f"REVOKE CREATE ON SCHEMA public FROM {AGGREGATE_OWNER}")
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {AGGREGATE_OWNER}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {AGGREGATE_OWNER}")
        for table in AGGREGATE_SOURCES:
            op.execute(f"GRANT SELECT ON public.{table} TO {AGGREGATE_OWNER}")

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
    # A migrator cannot repair another creator's defaults. Bootstrap must
    # reconcile these as superuser before handing ownership to the migrator.
    unsafe_owners = op.get_bind().execute(sa.text("""
        SELECT DISTINCT owner.rolname FROM pg_default_acl d
        JOIN pg_roles owner ON owner.oid = d.defaclrole
        CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
        LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
        WHERE d.defaclnamespace = 0 AND d.defaclobjtype IN ('r', 'S')
          AND owner.rolname <> ALL(:owners)
          AND (acl.grantee = 0 OR grantee.rolname IN
              ('ekklesia_api', 'ekklesia_monitor', 'ekklesia_dashboard', 'ekklesia_backup'))
    """), {"owners": owners}).all()
    if unsafe_owners:
        raise RuntimeError("Unsafe global default privileges remain for other creators; rerun scripts/ops/db-roles.sh as bootstrap superuser")
    # Apply to both legacy and migrator creators during the transition.
    for owner in owners:
        quoted_owner = op.get_bind().dialect.identifier_preparer.quote(owner)
        for scope in ("", " IN SCHEMA public"):
            prefix = f"ALTER DEFAULT PRIVILEGES FOR ROLE {quoted_owner}{scope}"
            op.execute(f"{prefix} REVOKE ALL ON TABLES FROM PUBLIC")
            op.execute(f"{prefix} REVOKE ALL ON SEQUENCES FROM PUBLIC")
            for role in RUNTIME_ROLES:
                if not _exists(role):
                    continue
                op.execute(f"{prefix} REVOKE ALL ON TABLES FROM {role}")
                op.execute(f"{prefix} REVOKE ALL ON SEQUENCES FROM {role}")
        prefix = f"ALTER DEFAULT PRIVILEGES FOR ROLE {quoted_owner} IN SCHEMA public"
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
    if has_owner and _exists("ekklesia_monitor"):
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
        op.execute(f"""DO $drop$ DECLARE installer name := current_user; BEGIN
            IF EXISTS (SELECT FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner
                       WHERE p.oid = to_regprocedure('public.{name}_aggregate()')
                         AND r.rolname = '{AGGREGATE_OWNER}') THEN
                SET LOCAL ROLE {AGGREGATE_OWNER};
            END IF;
            DROP FUNCTION IF EXISTS public.{name}_aggregate();
            EXECUTE format('SET LOCAL ROLE %I', installer);
        END $drop$""")
