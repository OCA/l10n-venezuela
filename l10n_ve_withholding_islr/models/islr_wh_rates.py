# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class IslrWhRates(models.Model):
    _name = "islr.wh.rates"
    _description = "ISLR Withholding Rates"

    concept_id = fields.Many2one(
        comodel_name="islr.wh.concept",
        string="Concept",
        required=True,
        ondelete="cascade",
    )
    person_type = fields.Selection(
        selection=[
            ("pnre", "Natural Person Resident (PNRE)"),
            ("pnnr", "Natural Person Non Resident (PNNR)"),
            ("pjdo", "Legal Entity Domiciled (PJDO)"),
            ("pjnd", "Legal Entity Non Domiciled (PJND)"),
        ],
        string="Person Type",
        required=True,
    )
    nature = fields.Selection(
        selection=[
            ("service", "Services"),
            ("good", "Goods / Sales"),
            ("lease", "Leasing / Rentals"),
            ("fees", "Professional Fees"),
        ],
        string="Nature",
        default="service",
    )
    base_percentage = fields.Float(string="Base Percentage (%)", default=100.0)
    wh_percentage = fields.Float(string="Retention Percentage (%)", required=True, default=0.0)
    subtract_ut = fields.Float(string="Subtraction in UT", default=0.0)
