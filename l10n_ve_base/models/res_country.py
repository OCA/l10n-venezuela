# Copyright 2025-Present SINAPSYS GLOBAL SA, MASTERCORE SAS
# Copyright 2026 Guillermo Montoya
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
#
# Models and catalog taken from l10n_ve_base 19.0
# https://github.com/odoo-mastercore/odoo-venezuela/tree/19.0/l10n_ve_base
# See data/ORIGIN.txt.

from odoo import fields, models


class ResCountry(models.Model):
    _inherit = "res.country"

    nationality = fields.Char(
        help="Gentilicio of the country.",
    )


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    municipality_ids = fields.One2many(
        comodel_name="res.country.state.municipality",
        inverse_name="state_id",
        string="Municipalities",
    )


class ResCountryStateMunicipality(models.Model):
    _name = "res.country.state.municipality"
    _description = "Municipality"
    _order = "name"

    name = fields.Char(string="Municipality", required=True)
    code = fields.Char(required=True)
    state_id = fields.Many2one(
        comodel_name="res.country.state",
        required=True,
        ondelete="restrict",
        index=True,
    )
    parish_ids = fields.One2many(
        comodel_name="res.country.state.municipality.parish",
        inverse_name="municipality_id",
        string="Parishes",
    )


class ResCountryStateMunicipalityParish(models.Model):
    _name = "res.country.state.municipality.parish"
    _description = "Parish"
    _order = "name"

    name = fields.Char(string="Parish", required=True)
    code = fields.Char(required=True)
    municipality_id = fields.Many2one(
        comodel_name="res.country.state.municipality",
        required=True,
        ondelete="restrict",
        index=True,
    )
