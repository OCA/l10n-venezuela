# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ve_islr_concept_id = fields.Many2one(
        "l10n.ve.islr.concept",
        string="Concepto de Retención ISLR",
        help="Concepto del art. 9 del Decreto 1.808 propuesto en las líneas de "
        "factura de proveedor con este producto. Tiene prioridad sobre el "
        "concepto del proveedor.",
    )
