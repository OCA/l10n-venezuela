# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_l10n_ve_iva_wh(self):
        # Unreconciling the withholding entry from the bill would leave the
        # issued voucher without its accounting counterpart.
        moves = self.debit_move_id.move_id | self.credit_move_id.move_id
        moves._l10n_ve_iva_wh_check_protected()
