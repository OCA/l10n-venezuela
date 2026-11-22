# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

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
    l10n_ve_islr_wh_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de Retenciones ISLR",
        check_company=True,
        domain="[('type', '=', 'general')]",
        help="Diario de los asientos de retención de ISLR generados al "
        "contabilizar facturas de proveedor.",
    )
