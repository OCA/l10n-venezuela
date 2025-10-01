import re

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _default_res_country(self):
        return self.env.company.country_id.id or False

    def _default_vat(self):
        if self.env.company.country_id == self.env.ref("base.ve"):
            return "V"
        return False

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        store=True,
    )
    prefix_vat = fields.Char(string="Prefix vat", compute="_compute_vat_prefix")
    municipality_id = fields.Many2one("res.country.municipality", "Municipality")
    parish_id = fields.Many2one("res.country.parish", "Parish")
    country_id = fields.Many2one("res.country", default=_default_res_country)
    vat = fields.Char(default=_default_vat)

    @api.depends("vat")
    def _compute_vat_prefix(self):
        for record in self:
            if record.vat:
                match = re.match(r"([VEJPG])([0-9]+)", record.vat, re.IGNORECASE)
                if match:
                    record.prefix_vat = match.group(1).upper()
                    continue
            record.prefix_vat = False

    @api.onchange("municipality_id")
    def _onchange_municipality_id(self):
        self.parish_id = False

    @api.onchange("state_id")
    def _onchange_state_id(self):
        self.municipality_id = False
        self.parish_id = False

    def check_vat_ve(self, vat):
        vat_regex = re.compile(
            r"""
            ([vecjpg])                          # group 1 - kind
            (
                (?P<optional_1>-)?                      # optional '-' (1)
                [0-9]{2}
                (?(optional_1)(?P<optional_2>[.])?)     # optional '.' (2) only if (1)
                [0-9]{3}
                (?(optional_2)[.])                      # mandatory '.' if (2)
                [0-9]{3}
                (?(optional_1)-)                        # mandatory '-' if (1)
            )                                   # group 2 - identifier number
            ([0-9]{1})?                         # check digit opcional
        """,
            re.VERBOSE | re.IGNORECASE,
        )

        matches = re.fullmatch(vat_regex, vat)
        if not matches:
            return False

        return True
