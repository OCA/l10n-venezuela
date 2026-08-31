# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nVeEdocLog(models.Model):
    _name = "l10n.ve.edoc.log"
    _description = "Venezuelan Electronic Document Log"
    _order = "id desc"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    endpoint = fields.Char(string="Operation", required=True)
    request = fields.Text()
    response = fields.Text()
    ok = fields.Boolean(string="Successful")
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="move_id.company_id",
        store=True,
        index=True,
    )
