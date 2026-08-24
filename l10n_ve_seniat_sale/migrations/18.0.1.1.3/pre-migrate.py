def migrate(cr, version):
    cr.execute(
        """
        WITH replacements(old_name, new_module, new_name) AS (
            VALUES
                ('external_layout_l10n_ve_presupuesto', 'web', 'external_layout'),
                ('report_saleorder_document_ve', 'sale', 'report_saleorder_document'),
                (
                    'quote_document_layout_preview_ve',
                    'sale',
                    'quote_document_layout_preview',
                )
        )
        UPDATE ir_ui_view AS child
           SET inherit_id = new_data.res_id
          FROM replacements
          JOIN ir_model_data AS old_data
            ON old_data.module = 'l10n_ve_seniat_sale'
           AND old_data.name = replacements.old_name
           AND old_data.model = 'ir.ui.view'
          JOIN ir_model_data AS new_data
            ON new_data.module = replacements.new_module
           AND new_data.name = replacements.new_name
           AND new_data.model = 'ir.ui.view'
         WHERE child.inherit_id = old_data.res_id
        """
    )
