# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Archive orphan VE discount reasons duplicated after seniat?loyalty move."""
    cr.execute(
        """
        UPDATE l10n_ve_discount_reason AS reason
           SET active = FALSE
         WHERE reason.active IS TRUE
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS data
                 WHERE data.model = 'l10n.ve.discount.reason'
                   AND data.res_id = reason.id
                   AND data.module = 'l10n_ve_loyalty'
           )
           AND EXISTS (
                SELECT 1
                  FROM l10n_ve_discount_reason AS other
                  JOIN ir_model_data AS data
                    ON data.model = 'l10n.ve.discount.reason'
                   AND data.res_id = other.id
                   AND data.module = 'l10n_ve_loyalty'
                 WHERE other.active IS TRUE
                   AND other.id != reason.id
                   AND other.name = reason.name
           )
        """
    )
