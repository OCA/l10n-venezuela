from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_dispatch_guide_enabled = fields.Boolean(
        string="Guías de despacho",
        default=True,
        help=(
            "Active esta opción para emitir guías de despacho venezolanas y asignar "
            "correlativos de control al validar entregas que lo requieran."
        ),
    )
