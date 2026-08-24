# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools import SQL

CLEANUP_XMLIDS = {
    "report_layout_l10n_ve_presupuesto": "report_layout",
    "external_layout_l10n_ve_presupuesto": "ir_ui_view",
    "report_saleorder_document_ve": "ir_ui_view",
    "quote_document_layout_preview_ve": "ir_ui_view",
    "paperformat_presupuesto_ve_letter_4cm": "report_paperformat",
}


def migrate(cr, version):
    names = tuple(CLEANUP_XMLIDS)
    cr.execute(
        """
        SELECT name, res_id
          FROM ir_model_data
         WHERE module = 'l10n_ve_seniat_sale'
           AND name IN %s
        """,
        (names,),
    )
    for xmlid_name, res_id in cr.fetchall():
        table = CLEANUP_XMLIDS[xmlid_name]
        cr.execute(
            SQL(
                "DELETE FROM %s WHERE id = %s",
                SQL.identifier(table),
                res_id,
            )
        )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'l10n_ve_seniat_sale'
           AND name IN %s
        """,
        (names,),
    )
