# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import api, fields, models

from .islr_concept import PERSON_TYPES


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ve_person_type = fields.Selection(
        PERSON_TYPES,
        string="Tipo de Persona (ISLR)",
        default="pj_dom",
        help="Determina la tarifa de retención de ISLR y el código SENIAT del "
        "anexo 6.1.",
    )
    l10n_ve_islr_concept_id = fields.Many2one(
        "l10n.ve.islr.concept",
        string="Concepto de Retención ISLR",
        help="Concepto por defecto del art. 9 del Decreto 1.808. "
        "Sin concepto no se retiene ISLR (ej. compras de bienes).",
    )
    l10n_ve_islr_rate = fields.Float(
        string="% Retención ISLR",
        digits=(5, 2),
        compute="_compute_l10n_ve_islr_rate",
        readonly=True,
    )

    @api.depends(
        "l10n_ve_person_type",
        "l10n_ve_islr_concept_id",
        "l10n_ve_islr_concept_id.rate_pj_dom",
        "l10n_ve_islr_concept_id.rate_pn_res",
    )
    def _compute_l10n_ve_islr_rate(self):
        for partner in self:
            concept = partner.l10n_ve_islr_concept_id
            if concept:
                partner.l10n_ve_islr_rate = concept._get_rate(
                    partner.l10n_ve_person_type or "pj_dom"
                )
            else:
                partner.l10n_ve_islr_rate = 0.0
