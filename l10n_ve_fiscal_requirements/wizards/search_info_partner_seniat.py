# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class SearchInfoPartnerSeniat(models.TransientModel):
    _name = "search.info.partner.seniat"
    _description = "Consult Partner Info in SENIAT"

    vat = fields.Char(string="VAT / RIF", required=True)

    def action_search_seniat(self):
        self.ensure_one()
        seniat_obj = self.env["seniat.url"]
        info = seniat_obj.get_seniat_partner_info(self.vat)
        if not info:
            raise ValidationError(_("No information found for RIF: %s") % self.vat)
        partner = self.env["res.partner"].search([("vat", "=", info["vat"])], limit=1)
        if partner:
            partner.write(
                {
                    "name": info.get("name") or partner.name,
                    "wh_iva_agent": info.get("wh_iva_agent", False),
                    "wh_iva_rate": info.get("wh_iva_rate", 0.0),
                    "seniat_updated": True,
                }
            )
            action = self.env.ref("base.action_partner_form").read()[0]
            action["res_id"] = partner.id
            action["views"] = [(self.env.ref("base.view_partner_form").id, "form")]
            return action
        else:
            new_partner = self.env["res.partner"].create(
                {
                    "name": info["name"],
                    "vat": info["vat"],
                    "wh_iva_agent": info.get("wh_iva_agent", False),
                    "wh_iva_rate": info.get("wh_iva_rate", 0.0),
                    "seniat_updated": True,
                }
            )
            action = self.env.ref("base.action_partner_form").read()[0]
            action["res_id"] = new_partner.id
            action["views"] = [(self.env.ref("base.view_partner_form").id, "form")]
            return action
