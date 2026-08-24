# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from psycopg2 import sql

_logger = logging.getLogger(__name__)

TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
AUDIT_LOG_TABLE = "l10n_ve_db_audit_log"
TRIGGER_FUNCTION = "l10n_ve_db_audit_trigger_func"

AUDIT_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION l10n_ve_db_audit_trigger_func()
RETURNS trigger AS $$
DECLARE
    v_record_id integer;
    v_app_name text;
    v_old jsonb;
    v_new jsonb;
    v_changed jsonb;
    v_key text;
BEGIN
    v_app_name := COALESCE(current_setting('application_name', true), '');
    IF v_app_name LIKE 'odoo-%' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        v_record_id := OLD.id;
        v_old := row_to_json(OLD)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_old)
        LOOP
            v_changed := v_changed || jsonb_build_object(
                v_key,
                jsonb_build_object('old', v_old -> v_key, 'new', NULL)
            );
        END LOOP;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'delete',
            v_old,
            NULL,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        v_record_id := NEW.id;
        v_old := row_to_json(OLD)::jsonb;
        v_new := row_to_json(NEW)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_new)
        LOOP
            IF v_old -> v_key IS DISTINCT FROM v_new -> v_key THEN
                v_changed := v_changed || jsonb_build_object(
                    v_key,
                    jsonb_build_object('old', v_old -> v_key, 'new', v_new -> v_key)
                );
            END IF;
        END LOOP;
        IF v_changed = '{}'::jsonb THEN
            RETURN NEW;
        END IF;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'update',
            v_old,
            v_new,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        v_record_id := NEW.id;
        v_new := row_to_json(NEW)::jsonb;
        v_changed := '{}'::jsonb;
        FOR v_key IN SELECT jsonb_object_keys(v_new)
        LOOP
            v_changed := v_changed || jsonb_build_object(
                v_key,
                jsonb_build_object('old', NULL, 'new', v_new -> v_key)
            );
        END LOOP;
        INSERT INTO l10n_ve_db_audit_log (
            table_name,
            record_id,
            operation,
            old_values,
            new_values,
            changed_values,
            db_user,
            client_addr,
            application_name,
            logged_at
        ) VALUES (
            TG_TABLE_NAME,
            v_record_id,
            'insert',
            NULL,
            v_new,
            v_changed,
            session_user,
            COALESCE(inet_client_addr()::text, ''),
            v_app_name,
            (NOW() AT TIME ZONE 'UTC')
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def _validate_table_name(table_name):
    if not table_name or not TABLE_NAME_RE.match(table_name):
        raise ValueError(f"Invalid PostgreSQL table name: {table_name}")


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cr.fetchone()[0]


def _install_trigger_on_table(cr, table_name):
    _validate_table_name(table_name)
    if table_name == AUDIT_LOG_TABLE:
        return False
    if not _table_exists(cr, table_name):
        _logger.warning(
            "Skipping DB audit trigger: table %s does not exist", table_name
        )
        return False
    trigger_name = f"l10n_ve_db_audit_{table_name}"
    cr.execute(
        sql.SQL(
            """
            DROP TRIGGER IF EXISTS {trigger} ON {table};
            CREATE TRIGGER {trigger}
                AFTER INSERT OR UPDATE OR DELETE
                ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION {function}();
            """
        ).format(
            trigger=sql.Identifier(trigger_name),
            table=sql.Identifier(table_name),
            function=sql.Identifier(TRIGGER_FUNCTION),
        )
    )
    return True


def _drop_trigger_on_table(cr, table_name):
    _validate_table_name(table_name)
    if not _table_exists(cr, table_name):
        return
    trigger_name = f"l10n_ve_db_audit_{table_name}"
    cr.execute(
        sql.SQL("DROP TRIGGER IF EXISTS {trigger} ON {table}").format(
            trigger=sql.Identifier(trigger_name),
            table=sql.Identifier(table_name),
        )
    )


def install_db_audit_triggers(env, table_names=None):
    cr = env.cr
    cr.execute(AUDIT_TRIGGER_FUNCTION_SQL)
    if table_names is None:
        table_names = (
            env["l10n.ve.db.audit.table"]
            .search([("active", "=", True)])
            .mapped("table_name")
        )
    installed = []
    for table_name in table_names:
        if _install_trigger_on_table(cr, table_name):
            installed.append(table_name)
    if installed:
        env["l10n.ve.db.audit.table"].sudo().search(
            [("table_name", "in", installed)]
        ).write({"trigger_installed": True})
    return installed


def uninstall_db_audit_triggers(env):
    cr = env.cr
    table_names = env["l10n.ve.db.audit.table"].search([]).mapped("table_name")
    for table_name in table_names:
        _drop_trigger_on_table(cr, table_name)
    cr.execute(
        sql.SQL("DROP FUNCTION IF EXISTS {function}()").format(
            function=sql.Identifier(TRIGGER_FUNCTION)
        )
    )
    env["l10n.ve.db.audit.table"].sudo().search([]).write({"trigger_installed": False})


DB_AUDIT_TABLE_XMLIDS = {
    "account_move": "db_audit_table_account_move",
    "account_account": "db_audit_table_account_account",
    "account_journal": "db_audit_table_account_journal",
    "account_tax": "db_audit_table_account_tax",
    "res_currency_rate": "db_audit_table_res_currency_rate",
    "ir_sequence": "db_audit_table_ir_sequence",
    "tax_unit": "db_audit_table_tax_unit",
    "res_company": "db_audit_table_res_company",
    "account_payment": "db_audit_table_account_payment",
    "account_retention": "db_audit_table_account_retention",
    "account_retention_line": "db_audit_table_account_retention_line",
}


def _move_xmlids(cr, src_module, dst_module, exclude_names=None):
    exclude_names = list(exclude_names or [])
    cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = %s
         WHERE src.module = %s
           AND NOT (src.name = ANY(%s))
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS dst
                 WHERE dst.module = %s
                   AND dst.name = src.name
           )
        """,
        (dst_module, src_module, exclude_names or [""], dst_module),
    )
    return cr.rowcount


def _ensure_module_db_audit_table_xmlid(cr, module, xmlid_name, res_id):
    cr.execute(
        """
        SELECT id, res_id
          FROM ir_model_data
         WHERE module = %s
           AND name = %s
         LIMIT 1
        """,
        (module, xmlid_name),
    )
    row = cr.fetchone()
    if row:
        if row[1] != res_id:
            cr.execute(
                """
                UPDATE ir_model_data
                   SET res_id = %s,
                       model = 'l10n.ve.db.audit.table',
                       noupdate = TRUE
                 WHERE id = %s
                """,
                (res_id, row[0]),
            )
        return 0
    cr.execute(
        """
        INSERT INTO ir_model_data (
            module, name, model, res_id, noupdate
        ) VALUES (
            %s, %s, 'l10n.ve.db.audit.table', %s, TRUE
        )
        """,
        (module, xmlid_name, res_id),
    )
    return 1


def _ensure_db_audit_table_xmlids(cr):
    if not _table_exists(cr, "l10n_ve_db_audit_table"):
        return 0
    created = 0
    for table_name, xmlid_name in DB_AUDIT_TABLE_XMLIDS.items():
        cr.execute(
            """
            SELECT id
              FROM l10n_ve_db_audit_table
             WHERE table_name = %s
             LIMIT 1
            """,
            (table_name,),
        )
        row = cr.fetchone()
        if not row:
            continue
        res_id = row[0]
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'l10n_ve_auditlog',
                   res_id = %s,
                   model = 'l10n.ve.db.audit.table',
                   noupdate = TRUE
             WHERE module = 'l10n_ve_audit'
               AND name = %s
               AND NOT EXISTS (
                    SELECT 1
                      FROM ir_model_data AS dst
                     WHERE dst.module = 'l10n_ve_auditlog'
                       AND dst.name = %s
               )
            """,
            (res_id, xmlid_name, xmlid_name),
        )
        created += _ensure_module_db_audit_table_xmlid(
            cr, "l10n_ve_auditlog", xmlid_name, res_id
        )
        created += _ensure_module_db_audit_table_xmlid(
            cr, "l10n_ve_audit", xmlid_name, res_id
        )
    return created


def _takeover_from_auditlog(env):
    cr = env.cr
    cr.execute(
        """
        SELECT state
          FROM ir_module_module
         WHERE name = 'auditlog'
        """
    )
    row = cr.fetchone()
    if not row or row[0] not in ("installed", "to upgrade", "to remove"):
        return False

    _logger.info(
        "Migrating OCA auditlog -> l10n_ve_auditlog "
        "(preserving auditlog.* tables and records)"
    )

    cr.execute(
        """
        SELECT m.name
          FROM ir_module_module m
          JOIN ir_module_module_dependency d ON d.module_id = m.id
         WHERE d.name = 'auditlog'
           AND m.state IN ('installed', 'to upgrade', 'to install')
           AND m.name NOT IN ('auditlog', 'l10n_ve_auditlog')
        """
    )
    dependents = [name for (name,) in cr.fetchall()]
    if dependents:
        _logger.warning(
            "Modules still depending on auditlog will be marked uninstalled: %s",
            ", ".join(sorted(dependents)),
        )
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'uninstalled',
                   latest_version = NULL
             WHERE name = ANY(%s)
            """,
            (dependents,),
        )

    _move_xmlids(cr, "auditlog", "l10n_ve_auditlog")
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled',
               latest_version = NULL
         WHERE name = 'auditlog'
        """
    )
    env["ir.module.module"].invalidate_model(["state", "latest_version"])
    env["ir.model.data"].invalidate_model(["module"])
    return True


def _takeover_from_l10n_ve_audit(env):
    cr = env.cr
    moved = _move_xmlids(
        cr,
        "l10n_ve_audit",
        "l10n_ve_auditlog",
        exclude_names=["module_l10n_ve_audit"],
    )
    ensured = _ensure_db_audit_table_xmlids(cr)
    if moved or ensured:
        _logger.info(
            "Migrating l10n_ve_audit -> l10n_ve_auditlog "
            "(moved %s xmlids, linked %s db audit tables)",
            moved,
            ensured,
        )
        env["ir.model.data"].invalidate_model(["module", "res_id", "model"])
    return bool(moved or ensured)


def pre_init_hook(env):
    _takeover_from_auditlog(env)
    _takeover_from_l10n_ve_audit(env)


def post_init_hook(env):
    install_db_audit_triggers(env)


def uninstall_hook(env):
    uninstall_db_audit_triggers(env)
