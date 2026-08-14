# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'l10n_ve_auditlog'
         WHERE module = 'l10n_ve_audit'
           AND name != 'module_l10n_ve_audit'
        """
    )
