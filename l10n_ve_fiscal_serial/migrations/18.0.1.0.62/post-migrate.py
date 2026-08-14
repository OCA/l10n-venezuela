# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'account_payment_method_line'
           AND column_name = 'l10n_ve_fiscal_payment_method_id'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'account_journal'
           AND column_name = 'l10n_ve_fiscal_payment_code'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        UPDATE account_payment_method_line AS line
           SET l10n_ve_fiscal_payment_method_id = method.id
          FROM account_journal AS journal
          JOIN l10n_ve_fiscal_payment_method AS method
            ON method.company_id = journal.company_id
           AND method.code = LPAD(TRIM(journal.l10n_ve_fiscal_payment_code), 2, '0')
         WHERE line.journal_id = journal.id
           AND line.l10n_ve_fiscal_payment_method_id IS NULL
           AND journal.l10n_ve_fiscal_payment_code IS NOT NULL
           AND TRIM(journal.l10n_ve_fiscal_payment_code) <> ''
        """
    )
    if cr.rowcount:
        _logger.info(
            "Migrated fiscal payment method on %s payment method line(s)",
            cr.rowcount,
        )

    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'res_company'
           AND column_name = 'l10n_ve_fiscal_default_payment_method_id'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        UPDATE res_company AS company
           SET l10n_ve_fiscal_default_payment_method_id = method.id
          FROM l10n_ve_fiscal_payment_method AS method
         WHERE method.company_id = company.id
           AND method.code = '01'
           AND company.l10n_ve_fiscal_default_payment_method_id IS NULL
        """
    )
