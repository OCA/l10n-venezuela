# Copyright 2025-Present SINAPSYS GLOBAL SA, MASTERCORE SAS
# Copyright 2026 Guillermo Montoya
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
#
# Taken from l10n_ve_base 19.0 (odoo-mastercore/odoo-venezuela).

from odoo import fields, models


class L10nVeResponsibilityType(models.Model):
    _name = "l10n_ve.responsibility.type"
    _description = "SENIAT Responsibility Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "UNIQUE(name)",
        "The responsibility type name must be unique.",
    )
    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "The responsibility type code must be unique.",
    )
