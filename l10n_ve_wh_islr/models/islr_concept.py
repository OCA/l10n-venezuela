# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import api, fields, models

PERSON_TYPES = [
    ("pj_dom", "Persona Jurídica Domiciliada"),
    ("pn_res", "Persona Natural Residente"),
]


class L10nVeIslrConcept(models.Model):
    _name = "l10n.ve.islr.concept"
    _description = "Concepto de Retención de ISLR (Decreto 1.808)"
    _order = "seniat_code_pj, name"

    name = fields.Char(string="Concepto", required=True)
    seniat_code_pj = fields.Char(
        string="Código SENIAT (PJ Domiciliada)",
        size=3,
        default="000",
        help="Código de 3 dígitos del anexo 6.1 del Manual Técnico XML v3.1 del "
        "SENIAT para persona jurídica domiciliada. '000' está reservado a la "
        "Declaración Sin Operaciones (la emite el export cuando el período no "
        "tiene comprobantes): un comprobante real con '000' bloquea el XML.",
    )
    seniat_code_pn = fields.Char(
        string="Código SENIAT (PN Residente)",
        size=3,
        default="000",
        help="Código de 3 dígitos del anexo 6.1 del Manual Técnico XML v3.1 del "
        "SENIAT para persona natural residente. '000' está reservado a la "
        "Declaración Sin Operaciones (la emite el export cuando el período no "
        "tiene comprobantes): un comprobante real con '000' bloquea el XML.",
    )
    rate_pj_dom = fields.Float(string="Tarifa PJ Domiciliada (%)", digits=(5, 2))
    rate_pn_res = fields.Float(string="Tarifa PN Residente (%)", digits=(5, 2))
    apply_subtrahend = fields.Boolean(
        string="Aplica Sustraendo (PN)",
        help="Sustraendo del Decreto 1.808 para persona natural residente: "
        "UT vigente × tarifa × 83,3334. Aplica a los conceptos con tarifa 3% de PN.",
    )
    active = fields.Boolean(default=True)

    @api.depends("name", "seniat_code_pj")
    def _compute_display_name(self):
        for concept in self:
            concept.display_name = f"[{concept.seniat_code_pj or '000'}] {concept.name}"

    def _get_rate(self, person_type):
        self.ensure_one()
        return self.rate_pn_res if person_type == "pn_res" else self.rate_pj_dom

    def _get_seniat_code(self, person_type):
        self.ensure_one()
        code = self.seniat_code_pn if person_type == "pn_res" else self.seniat_code_pj
        return code or "000"
