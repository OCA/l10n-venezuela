from odoo import fields, models


class L10nVeResCityDistrict(models.Model):
    _name = "l10n_ve.res.city.district"
    _description = "District, administrative units beneath the level of municipalities"
    _order = "name"

    name = fields.Char(translate=True)
    city_id = fields.Many2one("res.city", "City")
    code = fields.Char(
        help="This code will help with the identification of each district"
    )
