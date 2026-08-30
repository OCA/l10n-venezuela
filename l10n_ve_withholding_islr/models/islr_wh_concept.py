# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class IslrWhConcept(models.Model):
    _name = "islr.wh.concept"
    _description = "ISLR Withholding Concept"

    name = fields.Char(string="Concept Name", required=True)
    code = fields.Char(string="Concept Code", required=True, size=10)
    withholding_rate_ids = fields.One2many(
        comodel_name="islr.wh.rates",
        inverse_name="concept_id",
        string="Rates Breakdown",
    )
