# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class WizardInvoiceNroCtrl(models.TransientModel):
    _name = "wizard.invoice.nro.ctrl"
    _description = "Assign Control Number"

    nro_ctrl = fields.Char(string="Control Number", required=True)

    def action_assign_nro_ctrl(self):
        self.ensure_one()
        active_id = self.env.context.get("active_id")
        if active_id:
            move = self.env["account.move"].browse(active_id)
            move.write({"nro_ctrl": self.nro_ctrl})
        return True
