# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .islr_concept import NON_RESIDENT_PERSON_TYPES, PERSON_TYPES

RIF_PATTERN = re.compile(r"^[VEJPG]\d{9}$")
# SENIAT check digit: the letter weighs its value times 4, then the eight
# digits are weighted 3, 2, 7, 6, 5, 4, 3, 2 (modulo 11).
RIF_LETTER_VALUES = {"V": 1, "E": 2, "J": 3, "P": 4, "G": 5}
RIF_DIGIT_WEIGHTS = (3, 2, 7, 6, 5, 4, 3, 2)


def normalize_rif(vat):
    """Return the RIF without hyphens or spaces, uppercased."""
    return re.sub(r"[\s-]", "", vat or "").upper()


def is_valid_rif(rif):
    """Return whether a normalized RIF has a valid format and check digit."""
    if not RIF_PATTERN.match(rif or ""):
        return False
    total = RIF_LETTER_VALUES[rif[0]] * 4 + sum(
        int(digit) * weight
        for digit, weight in zip(rif[1:9], RIF_DIGIT_WEIGHTS, strict=True)
    )
    check = 11 - total % 11
    if check > 9:
        check = 0
    return int(rif[9]) == check


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
        help="Tarifa del concepto por defecto para el tipo de persona, o la "
        "del convenio cuando aplica. Es 0 para un concepto gravado con la "
        "Tarifa N° 2, que depende de la base acumulada del año.",
    )
    l10n_ve_islr_treaty = fields.Boolean(
        string="Convenio para Evitar la Doble Tributación",
        help="Solo para personas no residentes o no domiciliadas: la tarifa "
        "del convenio reemplaza la calculada por el concepto y se aplica "
        "sobre el monto bruto.",
    )
    l10n_ve_islr_treaty_rate = fields.Float(
        string="Tarifa del Convenio (%)",
        digits=(5, 2),
        help="Tarifa reducida del convenio, de 0 a 100. Con 0 se emite el "
        "comprobante sin asiento de retención.",
    )
    l10n_ve_islr_treaty_certificate = fields.Char(
        string="Certificado de Residencia Fiscal",
        help="Referencia del certificado de residencia fiscal que acredita "
        "la aplicación del convenio.",
    )

    @api.constrains("l10n_ve_islr_treaty_rate")
    def _check_l10n_ve_islr_treaty_rate(self):
        for partner in self:
            if not 0.0 <= partner.l10n_ve_islr_treaty_rate <= 100.0:
                raise ValidationError(
                    self.env._("La tarifa del convenio debe estar entre 0 y 100.")
                )

    def _l10n_ve_islr_treaty_applies(self, person_type):
        """Return whether the treaty rate replaces the computed one."""
        self.ensure_one()
        return self.l10n_ve_islr_treaty and person_type in NON_RESIDENT_PERSON_TYPES

    def _l10n_ve_islr_get_valid_rif(self):
        """Return the normalized RIF, or False when missing or invalid."""
        self.ensure_one()
        rif = normalize_rif(self.vat)
        return rif if is_valid_rif(rif) else False

    @api.depends(
        "l10n_ve_person_type",
        "l10n_ve_islr_concept_id",
        "l10n_ve_islr_concept_id.rate_pj_dom",
        "l10n_ve_islr_concept_id.rate_pn_res",
        "l10n_ve_islr_concept_id.rate_pn_nores",
        "l10n_ve_islr_concept_id.rate_pj_nodom",
        "l10n_ve_islr_concept_id.pj_nodom_rate_type",
        "l10n_ve_islr_treaty",
        "l10n_ve_islr_treaty_rate",
    )
    def _compute_l10n_ve_islr_rate(self):
        for partner in self:
            concept = partner.l10n_ve_islr_concept_id
            person_type = partner.l10n_ve_person_type or "pj_dom"
            if partner._l10n_ve_islr_treaty_applies(person_type):
                partner.l10n_ve_islr_rate = partner.l10n_ve_islr_treaty_rate
            elif concept and concept._is_tarifa2(person_type):
                partner.l10n_ve_islr_rate = 0.0
            elif concept:
                partner.l10n_ve_islr_rate = concept._get_rate(
                    partner.l10n_ve_person_type or "pj_dom"
                )
            else:
                partner.l10n_ve_islr_rate = 0.0
