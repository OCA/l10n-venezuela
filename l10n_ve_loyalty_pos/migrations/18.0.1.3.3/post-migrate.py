# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE l10n_ve_fiscal_payment_method
           SET name = 'Monedero D'
         WHERE code = '24'
           AND name IN ('OTRO', 'Otro', 'otro')
        """
    )
