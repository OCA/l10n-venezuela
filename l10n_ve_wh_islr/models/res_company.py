# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_islr_wh_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de Retenciones ISLR por Enterar",
        check_company=True,
        help="Cuenta de pasivo donde se acumulan las retenciones de ISLR "
        "practicadas a proveedores (ej. 210401 Retenciones de ISLR por Enterar).",
    )
