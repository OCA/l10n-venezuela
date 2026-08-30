# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class L10nVeEdocLog(models.Model):
    """What was sent to the digital printing house and what it answered.

    This is the evidence a tax auditor would ask for, and what SENIAT PA
    SNAT/2024/000121 requires of the billing system. It is always written,
    especially when the call fails.
    """

    _name = "l10n.ve.edoc.log"
    _description = "Digital printing house log"
    _order = "id desc"

    move_id = fields.Many2one(
        "account.move", string="Document", required=True, ondelete="cascade", index=True
    )
    endpoint = fields.Char(string="Operation", required=True)
    request = fields.Text(string="Sent")
    response = fields.Text()
    ok = fields.Boolean(string="Successful")
    company_id = fields.Many2one(related="move_id.company_id", store=True, index=True)
