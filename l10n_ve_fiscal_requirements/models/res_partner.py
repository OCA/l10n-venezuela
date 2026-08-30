# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    seniat_updated = fields.Boolean(
        string="Seniat Updated",
        help="Indicates if partner was updated using SENIAT",
    )
    wh_iva_rate = fields.Float(
        string="IVA Retention Rate (%)",
        digits="Account",
        help="Vat Withholding rate according to SENIAT",
    )
    wh_iva_agent = fields.Boolean(
        string="Wh. IVA Agent",
        help="Indicate if the partner is a withholding vat agent",
    )
    person_type = fields.Selection(
        selection=[
            ("pnre", "Natural Person Resident (PNRE)"),
            ("pnnr", "Natural Person Non Resident (PNNR)"),
            ("pjdo", "Legal Entity Domiciled (PJDO)"),
            ("pjnd", "Legal Entity Non Domiciled (PJND)"),
        ],
        string="Person Type",
        default="pjdo",
        help="Venezuelan Fiscal Person Type for ISLR / IVA classification",
    )

    @api.constrains("vat", "country_id")
    def _check_unique_ve_vat(self):
        for partner in self:
            if partner.country_id and partner.country_id.code == "VE" and partner.vat:
                domain = [
                    ("id", "!=", partner.id),
                    ("commercial_partner_id", "!=", partner.commercial_partner_id.id),
                    ("vat", "=", partner.vat),
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        _("The VAT / RIF %s is already assigned to another partner.")
                        % partner.vat
                    )

    def action_update_from_seniat(self):
        self.ensure_one()
        if not self.vat:
            raise ValidationError(_("Please provide a VAT / RIF number first."))
        info = self.env["seniat.url"].get_seniat_partner_info(self.vat)
        if info:
            self.write(
                {
                    "name": info.get("name") or self.name,
                    "wh_iva_agent": info.get("wh_iva_agent", False),
                    "wh_iva_rate": info.get("wh_iva_rate", 0.0),
                    "seniat_updated": True,
                }
            )
        else:
            raise ValidationError(
                _("Could not retrieve partner information from SENIAT for VAT: %s")
                % self.vat
            )
