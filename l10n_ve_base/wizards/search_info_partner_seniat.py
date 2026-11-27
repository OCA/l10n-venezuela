# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models
from odoo.exceptions import ValidationError


class SearchInfoPartnerSeniat(models.TransientModel):
    _name = "search.info.partner.seniat"
    _description = "Consult Partner Info in SENIAT"

    vat = fields.Char(string="VAT / RIF", required=True)

    def action_search_seniat(self):
        self.ensure_one()
        info = self.env["seniat.url"].get_seniat_partner_info(self.vat)
        if not info:
            raise ValidationError(
                self.env._("No information found for RIF: %s", self.vat)
            )
        venezuela = self.env.ref("base.ve", raise_if_not_found=False)
        partner = self.env["res.partner"].search([("vat", "=", info["vat"])], limit=1)
        values = {
            "name": info.get("name"),
            "vat": info["vat"],
            "wh_iva_agent": info.get("wh_iva_agent", False),
            "wh_iva_rate": info.get("wh_iva_rate", 0.0),
            "vat_subjected": info.get("vat_subjected", False),
            "seniat_updated": True,
        }
        if venezuela:
            values["country_id"] = venezuela.id
        Partner = self.env["res.partner"]
        rif = Partner._l10n_ve_id_type("l10n_ve_base.it_rif")
        if rif:
            values["l10n_latam_identification_type_id"] = rif.id
        preview = Partner.new(
            {
                "vat": info["vat"],
                "l10n_latam_identification_type_id": rif.id if rif else False,
            }
        )
        suggested = preview._l10n_ve_suggested_person_type()
        if suggested:
            values["person_type"] = suggested
        if partner:
            partner.write({k: v for k, v in values.items() if v or k == "wh_iva_agent"})
        else:
            partner = self.env["res.partner"].create(values)
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "base.action_partner_form"
        )
        action["res_id"] = partner.id
        action["views"] = [(self.env.ref("base.view_partner_form").id, "form")]
        return action
