import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

VE_CODE = "VE"


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _default_res_country(self):
        return self.env.company.country_id.id or False

    def _default_vat(self):
        if self.env.company.country_id == self.env.ref("base.ve"):
            return "V"
        return False

    # @api.depends('complete_name', 'email', 'vat', 'state_id', 'country_id', 'commercial_company_name')
    # def _compute_display_name(self):
    #     super(ResPartner, self)._compute_display_name()

    #     for partner in self:
    #         if partner.vat:
    #             partner.display_name = f"{partner.vat or ""} - {partner.display_name or ""}"
    #             continue
    #         partner.display_name = partner.display_name

    taxpayer_type = fields.Selection(
        [
            ("ordinary", "Ordinary"),
            ("formal", "Formal"),
            ("special", "Special"),
        ],
        store=True,
        readonly=False,
        compute="_compute_taxpayer_type",
    )

    # TODO: prefix_vat isn't used anywhere
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

    @api.depends("country_id", "country_id.code")
    def _compute_taxpayer_type(self):
        for record in self:
            if record.country_id and record.country_id.code == VE_CODE:
                if not record.taxpayer_type:
                    record.taxpayer_type = "ordinary"
            else:
                record.taxpayer_type = False

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

    @api.constrains("country_id", "taxpayer_type")
    def _check_taxpayer_type_country(self):
        for rec in self:
            if rec.taxpayer_type and (
                not rec.country_id or rec.country_id.code != VE_CODE
            ):
                raise ValidationError(
                    _(
                        "The taxpayer type can only be set for Venezuelan partners "
                        "(country code 'VE')."
                    )
                )
