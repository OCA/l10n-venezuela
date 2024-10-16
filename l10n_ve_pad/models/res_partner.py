from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ve_district_id = fields.Many2one(
        "l10n_ve.res.city.district",
        string="District",
        help="Districts are part of a city.",
    )
    l10n_ve_district_name = fields.Char(
        string="District name", related="l10n_ve_district_id.name"
    )

    @api.onchange("l10n_ve_district_id")
    def _onchange_l10n_ve_district(self):
        if self.l10n_ve_district_id:
            self.city_id = self.l10n_ve_district_id.city_id

    @api.onchange("city_id")
    def _onchange_l10n_ve_city_id(self):
        if (
            self.city_id
            and self.l10n_ve_district_id.city_id
            and self.l10n_ve_district_id.city_id != self.city_id
        ):
            self.l10n_ve_district_id = False

    @api.model
    def _formatting_address_fields(self):
        """Returns the list of address fields usable to format addresses."""
        return super()._formatting_address_fields() + ["l10n_ve_district_name"]
