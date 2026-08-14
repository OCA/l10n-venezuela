import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _ensure_column(cr, table, column, ddl_type):
    if not _column_exists(cr, table, column):
        cr.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def migrate(cr, version):
    _ensure_column(cr, "res_company", "l10n_ve_fiscal_flag_21", "VARCHAR")
    _ensure_column(cr, "res_company", "l10n_ve_fiscal_flag_50", "VARCHAR")
    _ensure_column(cr, "res_company", "l10n_ve_fiscal_use_barcode", "BOOLEAN")
    _ensure_column(cr, "res_company", "l10n_ve_fiscal_footer", "TEXT")

    if not _column_exists(cr, "l10n_ve_fiscal_machine", "flag_21"):
        return

    cr.execute(
        """
        UPDATE res_company AS company
        SET l10n_ve_fiscal_flag_21 = COALESCE(
            (
                SELECT machine.flag_21
                FROM l10n_ve_fiscal_machine AS machine
                WHERE machine.company_id = company.id
                  AND machine.flag_21 IS NOT NULL
                  AND machine.flag_21 != '00'
                ORDER BY machine.active DESC, machine.id
                LIMIT 1
            ),
            (
                SELECT machine.flag_21
                FROM l10n_ve_fiscal_machine AS machine
                WHERE machine.company_id = company.id
                  AND machine.flag_21 IS NOT NULL
                ORDER BY machine.active DESC, machine.id
                LIMIT 1
            ),
            company.l10n_ve_fiscal_flag_21,
            '30'
        )
        WHERE company.l10n_ve_fiscal_flag_21 IS NULL
           OR company.l10n_ve_fiscal_flag_21 = ''
           OR company.l10n_ve_fiscal_flag_21 = '00'
        """
    )
    if cr.rowcount:
        _logger.info(
            "Migrated FLAG_21 from fiscal machines to %s companies",
            cr.rowcount,
        )

    cr.execute(
        """
        UPDATE res_company
        SET l10n_ve_fiscal_flag_50 = '01'
        WHERE l10n_ve_fiscal_flag_50 IS NULL
           OR l10n_ve_fiscal_flag_50 = ''
        """
    )
