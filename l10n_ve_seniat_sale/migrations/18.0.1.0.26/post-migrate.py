# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = 'pba_web_external_layout'
           AND name = 'external_layout_pba_presupuesto'
         LIMIT 1
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_company company
           SET external_report_layout_id = new_layout.id
          FROM ir_ui_view old_layout
          JOIN ir_model_data old_data
            ON old_data.model = 'ir.ui.view'
           AND old_data.res_id = old_layout.id
           AND old_data.module = 'l10n_ve_seniat_sale'
           AND old_data.name = 'external_layout_l10n_ve_presupuesto'
          JOIN ir_ui_view new_layout ON new_layout.id IS NOT NULL
          JOIN ir_model_data new_data
            ON new_data.model = 'ir.ui.view'
           AND new_data.res_id = new_layout.id
           AND new_data.module = 'pba_web_external_layout'
           AND new_data.name = 'external_layout_pba_presupuesto'
         WHERE company.external_report_layout_id = old_layout.id
        """
    )
