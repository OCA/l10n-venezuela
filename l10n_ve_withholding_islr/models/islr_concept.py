# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

PERSON_TYPES = [
    ("pj_dom", "Persona Jurídica Domiciliada"),
    ("pn_res", "Persona Natural Residente"),
    ("pn_nores", "Persona Natural No Residente"),
    ("pj_nodom", "Persona Jurídica No Domiciliada"),
]
# Decree 1,808 art. 9: subjects taxed as non-residents. A double taxation
# treaty on the vendor only applies to them.
NON_RESIDENT_PERSON_TYPES = ("pn_nores", "pj_nodom")
# Concept fields per person type: SENIAT code, rate and presumptive base.
PERSON_TYPE_FIELDS = {
    "pj_dom": ("seniat_code_pj", "rate_pj_dom", "base_pct_pj_dom"),
    "pn_res": ("seniat_code_pn", "rate_pn_res", "base_pct_pn_res"),
    "pn_nores": ("seniat_code_pn_nores", "rate_pn_nores", "base_pct_pn_nores"),
    "pj_nodom": ("seniat_code_pj_nodom", "rate_pj_nodom", "base_pct_pj_nodom"),
}
# Short labels of the person types, for the list of types a concept applies
# to.
PERSON_TYPE_SHORT_LABELS = {
    "pj_dom": "PJ Dom.",
    "pn_res": "PN Res.",
    "pn_nores": "PN No Res.",
    "pj_nodom": "PJ No Dom.",
}
# Income Tax Law, Tarifa N° 2 (legal entities), in tax units: each tuple is
# (upper bound of the bracket, rate %); None means no upper bound.
TARIFA2_BRACKETS = (
    (2000.0, 15.0),
    (3000.0, 22.0),
    (None, 34.0),
)

SENIAT_CODE_HELP = (
    "Código de 3 dígitos del anexo 6.1 del Manual Técnico XML v3.1 del "
    "SENIAT para este tipo de persona. '000' está reservado a la "
    "Declaración Sin Operaciones (la emite el export cuando el período no "
    "tiene comprobantes): un comprobante real con '000' bloquea el XML."
)
BASE_PCT_HELP = (
    "Porcentaje del monto pagado que constituye la base imponible "
    "(enriquecimiento presunto, art. 9 del Decreto 1.808). 100 cuando la "
    "base no es presunta."
)


def tarifa2_tax(amount, ut_value):
    """Return the Tarifa N° 2 tax of an amount, both in bolivars.

    The brackets are expressed in tax units and converted with the given
    tax unit value. The result is not rounded.
    """
    tax = 0.0
    lower = 0.0
    for upper_ut, rate in TARIFA2_BRACKETS:
        if amount <= lower:
            break
        upper = amount if upper_ut is None else min(amount, upper_ut * ut_value)
        tax += (upper - lower) * rate / 100.0
        if upper_ut is None:
            break
        lower = upper_ut * ut_value
    return tax


class L10nVeIslrConcept(models.Model):
    _name = "l10n.ve.islr.concept"
    _description = "Concepto de Retención de ISLR (Decreto 1.808)"
    _order = "seniat_code_pj, name"

    name = fields.Char(string="Concepto", required=True)
    seniat_code_pj = fields.Char(
        string="Código SENIAT (PJ Domiciliada)",
        size=3,
        default="000",
        help=SENIAT_CODE_HELP,
    )
    seniat_code_pn = fields.Char(
        string="Código SENIAT (PN Residente)",
        size=3,
        default="000",
        help=SENIAT_CODE_HELP,
    )
    seniat_code_pn_nores = fields.Char(
        string="Código SENIAT (PN No Residente)",
        size=3,
        default="000",
        help=SENIAT_CODE_HELP,
    )
    seniat_code_pj_nodom = fields.Char(
        string="Código SENIAT (PJ No Domiciliada)",
        size=3,
        default="000",
        help=SENIAT_CODE_HELP,
    )
    rate_pj_dom = fields.Float(string="Tarifa PJ Domiciliada (%)", digits=(5, 2))
    rate_pn_res = fields.Float(string="Tarifa PN Residente (%)", digits=(5, 2))
    rate_pn_nores = fields.Float(
        string="Tarifa PN No Residente (%)",
        digits=(5, 2),
        help="Tarifa fija sobre la base imponible (34 % en general, art. 9 "
        "del Decreto 1.808). Sin sustraendo.",
    )
    rate_pj_nodom = fields.Float(
        string="Tarifa PJ No Domiciliada (%)",
        digits=(5, 2),
        help="Tarifa fija sobre la base imponible. No se usa cuando el "
        "concepto se grava con la Tarifa N° 2.",
    )
    pj_nodom_rate_type = fields.Selection(
        [("fixed", "Tarifa fija"), ("tarifa2", "Tarifa N° 2 (progresiva)")],
        string="Tipo de Tarifa PJ No Domiciliada",
        required=True,
        default="fixed",
        help="Tarifa N° 2: 15 % hasta 2.000 UT, 22 % de 2.000 a 3.000 UT y "
        "34 % sobre el exceso, aplicada sobre la base imponible acumulada "
        "del proveedor en el año calendario.",
    )
    base_pct_pj_dom = fields.Float(
        string="Base Imponible PJ Domiciliada (%)",
        digits=(5, 2),
        default=100.0,
        help=BASE_PCT_HELP,
    )
    base_pct_pn_res = fields.Float(
        string="Base Imponible PN Residente (%)",
        digits=(5, 2),
        default=100.0,
        help=BASE_PCT_HELP,
    )
    base_pct_pn_nores = fields.Float(
        string="Base Imponible PN No Residente (%)",
        digits=(5, 2),
        default=100.0,
        help=BASE_PCT_HELP,
    )
    base_pct_pj_nodom = fields.Float(
        string="Base Imponible PJ No Domiciliada (%)",
        digits=(5, 2),
        default=100.0,
        help=BASE_PCT_HELP,
    )
    apply_subtrahend = fields.Boolean(
        string="Aplica Sustraendo (PN)",
        help="Sustraendo del Decreto 1.808 para persona natural residente: "
        "UT vigente × tarifa × 83,3334 (art. 9 parágrafo segundo). Aplica a "
        "los conceptos PN con tarifa porcentual, incluidos los de 1%; no a "
        "los premios de loterías, juegos y apuestas. Nunca aplica a no "
        "residentes.",
    )
    active = fields.Boolean(default=True)
    applicable_person_types = fields.Char(
        string="Aplica a",
        compute="_compute_applicable_person_types",
        help="Tipos de persona para los que el concepto tiene código SENIAT. "
        "Una factura cuyo proveedor es de otro tipo no puede contabilizarse "
        "con este concepto.",
    )

    @api.depends(
        "seniat_code_pj",
        "seniat_code_pn",
        "seniat_code_pn_nores",
        "seniat_code_pj_nodom",
    )
    def _compute_applicable_person_types(self):
        for concept in self:
            concept.applicable_person_types = ", ".join(
                PERSON_TYPE_SHORT_LABELS[person_type]
                for person_type in PERSON_TYPE_FIELDS
                if concept._l10n_ve_islr_applies_to(person_type)
            )

    @api.depends("name", "seniat_code_pj")
    def _compute_display_name(self):
        for concept in self:
            concept.display_name = f"[{concept.seniat_code_pj or '000'}] {concept.name}"

    @api.constrains(
        "base_pct_pj_dom",
        "base_pct_pn_res",
        "base_pct_pn_nores",
        "base_pct_pj_nodom",
    )
    def _check_base_pct(self):
        for concept in self:
            for _code, _rate, pct_field in PERSON_TYPE_FIELDS.values():
                if not 0.0 <= concept[pct_field] <= 100.0:
                    raise ValidationError(
                        self.env._(
                            "El porcentaje de base imponible del concepto %s "
                            "debe estar entre 0 y 100.",
                            concept.name,
                        )
                    )

    def _get_person_type_value(self, person_type, index):
        self.ensure_one()
        names = PERSON_TYPE_FIELDS.get(person_type, PERSON_TYPE_FIELDS["pj_dom"])
        return self[names[index]]

    def _get_seniat_code(self, person_type):
        return self._get_person_type_value(person_type, 0) or "000"

    def _l10n_ve_islr_applies_to(self, person_type):
        """Return whether the concept can be withheld on this person type.

        The SENIAT table defines each concept only for some person types
        (royalties, for instance, only for non-residents). A concept applies
        to a person type only when it has a SENIAT code for it: '000' is the
        zero-declaration code, never a concept code.
        """
        return self._get_seniat_code(person_type) != "000"

    def _get_rate(self, person_type):
        return self._get_person_type_value(person_type, 1)

    def _get_base_pct(self, person_type):
        return self._get_person_type_value(person_type, 2)

    def _is_tarifa2(self, person_type):
        self.ensure_one()
        return person_type == "pj_nodom" and self.pj_nodom_rate_type == "tarifa2"
