-- Run through db-roles.sh using a bootstrap superuser, psql >= 15.
-- No passwords in argv or files. Re-running rotates the supplied passwords.
\set ON_ERROR_STOP on
\set ECHO none
\getenv api_password EKKLESIA_API_PASSWORD
\getenv migrator_password EKKLESIA_MIGRATOR_PASSWORD
\getenv monitor_password EKKLESIA_MONITOR_PASSWORD
\getenv dashboard_password EKKLESIA_DASHBOARD_PASSWORD
\getenv backup_password EKKLESIA_BACKUP_PASSWORD
BEGIN;
-- Prevent credential statements from appearing in ordinary server logs.
SET LOCAL log_statement = 'none';
SET LOCAL log_min_duration_statement = -1;
SET LOCAL log_min_duration_sample = -1;
SET LOCAL log_min_error_statement = 'panic';
SET LOCAL password_encryption = 'scram-sha-256';
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['ekklesia_api', 'ekklesia_migrator', 'ekklesia_monitor', 'ekklesia_dashboard', 'ekklesia_backup'] LOOP
        IF EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
                   JOIN pg_roles parent ON parent.oid = m.roleid WHERE r.rolname = role_name
                   AND NOT (role_name = 'ekklesia_migrator' AND parent.rolname = 'ekklesia_monitor_owner')) THEN
            RAISE EXCEPTION 'Role % has memberships; remove them before bootstrap', role_name;
        END IF;
        IF role_name <> 'ekklesia_migrator' AND EXISTS (
            SELECT FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba WHERE r.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'Runtime role % owns a database; resolve ownership before bootstrap', role_name;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I', role_name);
        END IF;
        EXECUTE format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS', role_name);
    END LOOP;
END $$;
-- Only the migrator may assume the aggregate owner, explicitly via SET ROLE.
-- Runtime logins must never inherit its source-table privileges.
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ekklesia_monitor_owner') THEN
        CREATE ROLE ekklesia_monitor_owner;
    END IF;
    IF EXISTS (SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
               JOIN pg_roles parent ON parent.oid = m.roleid
               WHERE r.rolname = 'ekklesia_monitor_owner'
                  OR (parent.rolname = 'ekklesia_monitor_owner' AND r.rolname <> 'ekklesia_migrator')) THEN
        RAISE EXCEPTION 'Unexpected aggregate-owner membership; resolve before bootstrap';
    END IF;
END $$;
ALTER ROLE ekklesia_monitor_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD NULL;
GRANT ekklesia_monitor_owner TO ekklesia_migrator;
ALTER ROLE ekklesia_api PASSWORD :'api_password';
ALTER ROLE ekklesia_migrator PASSWORD :'migrator_password';
ALTER ROLE ekklesia_monitor PASSWORD :'monitor_password';
ALTER ROLE ekklesia_dashboard PASSWORD :'dashboard_password';
ALTER ROLE ekklesia_backup PASSWORD :'backup_password';

-- Schema-level revokes cannot cancel global defaults. Reconcile every existing
-- creator with table/sequence defaults, plus both transition creators, while
-- still connected as the bootstrap superuser. Migration adds public-only grants.
DO $$
DECLARE creator text; scope text; grantee text; object_kind text;
BEGIN
    FOR creator IN
        SELECT current_user::text UNION SELECT 'ekklesia_migrator'
        UNION SELECT r.rolname::text FROM pg_default_acl d
              JOIN pg_roles r ON r.oid = d.defaclrole WHERE d.defaclobjtype IN ('r', 'S')
    LOOP
        FOREACH scope IN ARRAY ARRAY['', ' IN SCHEMA public'] LOOP
            FOREACH grantee IN ARRAY ARRAY['PUBLIC', 'ekklesia_api', 'ekklesia_monitor', 'ekklesia_dashboard', 'ekklesia_backup'] LOOP
                FOREACH object_kind IN ARRAY ARRAY['TABLES', 'SEQUENCES'] LOOP
                    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I%s REVOKE ALL ON %s FROM %s',
                        creator, scope, object_kind,
                        CASE WHEN grantee = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(grantee) END);
                END LOOP;
            END LOOP;
        END LOOP;
    END LOOP;
END $$;

-- Scope ownership transfer to application objects, never REASSIGN OWNED (which
-- could transfer bootstrap-owned extension/system objects or other databases).
ALTER SCHEMA public OWNER TO ekklesia_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO ekklesia_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$
DECLARE obj record; runtime_role text;
BEGIN
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
    FOREACH runtime_role IN ARRAY ARRAY['ekklesia_api', 'ekklesia_monitor', 'ekklesia_dashboard', 'ekklesia_backup'] LOOP
        EXECUTE format('REVOKE ALL ON DATABASE %I FROM %I', current_database(), runtime_role);
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), runtime_role);
    END LOOP;
    EXECUTE format('GRANT CONNECT, CREATE, TEMPORARY ON DATABASE %I TO ekklesia_migrator', current_database());
    FOR obj IN
        SELECT c.relname, CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW'
            WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END AS kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
          AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
        ORDER BY c.relkind = 'S' -- tables first: attached sequences follow ownership
    LOOP
        EXECUTE format('ALTER %s public.%I OWNER TO ekklesia_migrator', obj.kind, obj.relname);
    END LOOP;
    FOR obj IN
        SELECT t.typname, CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END AS kind
        FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd')
          AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('ALTER %s public.%I OWNER TO ekklesia_migrator', obj.kind, obj.typname);
    END LOOP;
    -- pg_restore --no-owner --no-acl leaves these owned by the restoring
    -- login. Transfer only the six zero-argument aggregate functions so the
    -- NOINHERIT migrator can replace them after SET ROLE monitor_owner.
    FOR obj IN
        SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prokind = 'f' AND p.pronargs = 0
          AND p.proname IN ('monitor_bill_health_aggregate', 'monitor_lifecycle_stuck_aggregate',
              'monitor_lifecycle_fast_forward_aggregate', 'monitor_forum_missing_aggregate',
              'monitor_zk_pending_aggregate', 'monitor_zk_health_aggregate')
          AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('ALTER FUNCTION public.%I() OWNER TO ekklesia_monitor_owner', obj.proname);
    END LOOP;
END $$;
COMMIT;
