from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class L10nVeIgtfUnreconcilePaymentWizard(models.TransientModel):
    _name = "l10n_ve_igtf.unreconcile.payment.wizard"
    _description = "IGTF payment unreconcile decision"

    move_id = fields.Many2one("account.move", string="Invoice", required=True)
    partial_id = fields.Many2one(
        "account.partial.reconcile", string="Partial Reconcile", required=True
    )
    payment_id = fields.Many2one("account.payment", string="Payment", required=True)

    action = fields.Selection(
        selection=[
            ("cancel", "Cancel payment"),
            ("keep_remove_igtf", "Keep payment but remove IGTF"),
        ],
        required=True,
        default="keep_remove_igtf",
    )

    def action_confirm(self):
        """
        Unreconcile the selected payment from the invoice and apply
        the chosen IGTF option.

        Parameters
        ----------
        None

        Returns
        -------
        dict
            A window close action.

        Raises
        ------
        UserError
            If required information is missing, IGTF account is not
            configured, or the resulting amount is invalid.

        Notes
        -----
        The flow is:
        1) Unreconcile the partial reconcile from the invoice (same
           as the standard payments widget).
        2) Either cancel the payment, or keep it by removing the
           IGTF split (draft -> update -> post).
        """
        self.ensure_one()

        move_id = self.move_id.id
        partial_id = self.partial_id.id
        payment_id = self.payment_id.id
        action = self.action

        if not move_id or not partial_id or not payment_id:
            raise UserError(_("Missing data to process the request."))

        move = self.env["account.move"].browse(move_id)
        payment = self.env["account.payment"].browse(payment_id)

        move.js_remove_outstanding_partial(partial_id)

        if action == "cancel":
            payment.action_cancel()
            return {"type": "ir.actions.act_window_close"}

        company = payment.company_id
        igtf_account = company.l10n_ve_igtf_account_id
        if not igtf_account:
            raise UserError(_("No IGTF account is configured for the company."))

        igtf_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == igtf_account
        )
        if not igtf_lines:
            payment.with_context(l10n_ve_igtf_from_register_payment=True).write(
                {"l10n_ve_apply_igtf": False, "l10n_ve_igtf_included": False}
            )
            return {"type": "ir.actions.act_window_close"}

        igtf_amount_currency_abs = sum(abs(line.amount_currency) for line in igtf_lines)

        payment.action_draft()

        new_amount = payment.currency_id.round(
            payment.amount - igtf_amount_currency_abs
        )
        if new_amount < 0:
            raise UserError(
                _("The payment amount would become negative after removing IGTF.")
            )

        self.env.cr.execute(
            """
            UPDATE account_payment
            SET l10n_ve_apply_igtf = FALSE,
                l10n_ve_igtf_included = FALSE,
                amount = %s
            WHERE id = %s
            """,
            (new_amount, payment.id),
        )
        payment.invalidate_recordset(
            ["l10n_ve_apply_igtf", "l10n_ve_igtf_included", "amount"]
        )

        old_line_ids = payment.move_id.line_ids.ids
        line_vals_list = payment._prepare_move_line_default_vals()

        payment.move_id.write(
            {
                "line_ids": [Command.delete(line_id) for line_id in old_line_ids]
                + [Command.create(vals) for vals in line_vals_list],
            }
        )

        payment.move_id.action_post()
        payment.action_post()
        return {"type": "ir.actions.act_window_close"}
