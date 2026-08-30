# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import re
import urllib.request
from xml.dom.minidom import parseString

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SeniatUrl(models.Model):
    _name = "seniat.url"
    _description = "SENIAT Config URL"

    name = fields.Char(
        string="URL Seniat for Partner Information",
        required=True,
        default="http://contribuyente.seniat.gob.ve/getContribuyente/getContribuyente?rif=",
        help="URL from Seniat to search partner fiscal information",
    )
    url_seniat = fields.Char(
        string="URL Seniat for Retention Rate",
        required=True,
        default="http://contribuyente.seniat.gob.ve/buscarrif/BuscarRif.do",
        help="URL from Seniat to search retention rate from partner (RIF)",
    )
    url_seniat2 = fields.Char(
        string="URL Seniat for CI/Passport",
        required=True,
        default="http://contribuyente.seniat.gob.ve/buscarrif/BuscarRif.do",
        help="URL from Seniat to search retention rate from CI/Passport",
    )

    @api.model
    def _get_valid_digit(self, vat):
        divisor = 11
        vat_type = {"V": 1, "E": 2, "J": 3, "P": 4, "G": 5}
        mapper = {1: 3, 2: 2, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2}
        valid_digit = None
        vt = vat_type.get(vat[0].upper())
        if vt:
            sum_vat = vt * 4
            for i in range(8):
                sum_vat += int(vat[i + 1]) * mapper[i + 1]
            valid_digit = divisor - sum_vat % divisor
            if valid_digit >= 10:
                valid_digit = 0
        return valid_digit

    @api.model
    def validate_rif(self, vat):
        if not vat:
            return False
        vat = vat.strip().upper()
        if vat.startswith("VE"):
            vat = vat[2:]
        if re.search(r"^[VJEGP][0-9]{9}$", vat):
            valid_digit = self._get_valid_digit(vat)
            if valid_digit is not None and int(vat[9]) == valid_digit:
                return vat
        elif re.search(r"^([VE][0-9]{1,8})$", vat):
            vat = vat[0] + vat[1:].rjust(8, "0")
            valid_digit = self._get_valid_digit(vat)
            vat += str(valid_digit)
            return vat
        return False

    @api.model
    def get_seniat_partner_info(self, rif):
        valid_rif = self.validate_rif(rif)
        if not valid_rif:
            raise UserError(_("Invalid RIF format: %s") % rif)
        config = self.search([], limit=1)
        base_url = (
            config.name
            if config
            else "http://contribuyente.seniat.gob.ve/getContribuyente/getContribuyente?rif="
        )
        full_url = base_url + valid_rif
        try:
            req = urllib.request.Request(
                full_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8", errors="ignore")
            dom = parseString(content)
            root = dom.childNodes[0]
            name = (
                root.childNodes[0].firstChild.data
                if root.childNodes[0].firstChild
                else ""
            )
            wh_agent = (
                root.childNodes[1].firstChild.data.upper() == "SI"
                if root.childNodes[1].firstChild
                else False
            )
            vat_subjected = (
                root.childNodes[2].firstChild.data.upper() == "SI"
                if root.childNodes[2].firstChild
                else False
            )
            rate_str = (
                root.childNodes[3].firstChild.data
                if root.childNodes[3].firstChild
                else "0"
            )
            rate = float(rate_str.replace(",", "."))
            if "(" in name:
                name = name[: name.index("(")].strip()
            return {
                "name": name.strip(),
                "vat": "VE" + valid_rif,
                "wh_iva_agent": wh_agent,
                "wh_iva_rate": rate,
                "vat_subjected": vat_subjected,
            }
        except Exception as e:
            _logger.warning("Error querying SENIAT for RIF %s: %s", rif, e)
            return False
