from odoo import fields, models


class ResCountryParish(models.Model):
    _name = "res.country.parish"
    _description = "Parish"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    municipality_id = fields.Many2one(
        "res.country.municipality", string="Municipality", required=True
    )
