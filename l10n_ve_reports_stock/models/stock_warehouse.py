# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

_LOCATION_DOMAIN = (
    "[('usage', 'in', ['internal', 'inventory']), "
    "'|', ('company_id', '=', False), ('company_id', '=', company_id)]"
)


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    l10n_ve_location_retiros_id = fields.Many2one(
        "stock.location",
        string="Ubicación Retiros",
        domain=_LOCATION_DOMAIN,
        check_company=True,
        help=(
            "Ubicación destino para movimientos de retiros "
            "(uso personal o del propietario)."
        ),
    )
    l10n_ve_location_autoconsumos_id = fields.Many2one(
        "stock.location",
        string="Ubicación Autoconsumos",
        domain=_LOCATION_DOMAIN,
        check_company=True,
        help="Ubicación destino para movimientos de autoconsumo (consumo interno).",
    )
