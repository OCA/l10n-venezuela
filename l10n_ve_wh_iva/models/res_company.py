# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_is_spe = fields.Boolean(
        string="Sujeto Pasivo Especial (SPE)",
        help="Marque si la compañía fue designada Sujeto Pasivo Especial por el "
        "SENIAT. Activa la retención de IVA como agente.",
    )
    l10n_ve_spe_date = fields.Date(
        string="Fecha de Designación SPE",
        help="Fecha de inicio como Sujeto Pasivo Especial según la notificación "
        "del SENIAT.",
    )
    l10n_ve_iva_wh_agent_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta Retenciones de IVA por Enterar (Agente)",
        check_company=True,
        help="Cuenta pasiva donde se acredita el IVA retenido a proveedores "
        "cuando la compañía actúa como agente de retención (ej. 210303).",
    )
    l10n_ve_iva_wh_received_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta Retenciones de IVA Recibidas de Clientes",
        check_company=True,
        help="Cuenta activa donde se registran los comprobantes de retención "
        "recibidos de clientes SPE (ej. 110302, Forma 30 casilla 66).",
    )
