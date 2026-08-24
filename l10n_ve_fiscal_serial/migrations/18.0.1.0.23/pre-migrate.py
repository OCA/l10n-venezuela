import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'l10n_ve_fiscal_serial_use_emulator'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'l10n_ve_fiscal_machine'
          AND column_name = 'use_emulator'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        UPDATE l10n_ve_fiscal_machine AS machine
        SET use_emulator = company.l10n_ve_fiscal_serial_use_emulator,
            send_default_code_in_name =
                company.l10n_ve_fiscal_serial_send_default_code_in_name
        FROM res_company AS company
        WHERE machine.company_id = company.id
          AND (
              machine.use_emulator IS DISTINCT FROM
                  company.l10n_ve_fiscal_serial_use_emulator
              OR machine.send_default_code_in_name IS DISTINCT FROM
                  company.l10n_ve_fiscal_serial_send_default_code_in_name
          )
        """
    )
    if cr.rowcount:
        _logger.info(
            "Migrated fiscal serial company settings to %s fiscal machines",
            cr.rowcount,
        )

    cr.execute(
        """
        UPDATE l10n_ve_fiscal_machine AS machine
        SET flag_21 = company.l10n_ve_fiscal_serial_flag_21
        FROM res_company AS company
        WHERE machine.company_id = company.id
          AND machine.flag_21 = '00'
          AND company.l10n_ve_fiscal_serial_flag_21 IS NOT NULL
          AND company.l10n_ve_fiscal_serial_flag_21 != '00'
        """
    )
    if cr.rowcount:
        _logger.info(
            "Migrated FLAG_21 from company to %s fiscal machines",
            cr.rowcount,
        )
