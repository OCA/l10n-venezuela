from datetime import datetime
import json
import logging


from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    l10n_ve_invoice_date = fields.Datetime("Invoice Datetime", readonly=True)

    def action_post(self):
        for move_id in self:
            if move_id.country_code != self.env.ref("base.ve").code:
                continue

            lines = []
            for line in self.line_ids:
                if len(line.tax_ids) > 1:
                    tax_mapped = ", ".join(line.tax_ids.mapped("name"))
                    lines.append(f" - {line.name}: {tax_mapped}")

            if lines:
                raise UserError(
                    _(
                        "You cannot assign more than one tax to a single invoice line. "
                        "Please create separate lines for each tax. \n"
                        "%s"
                    )
                    % ("\n".join(lines))
                )
        return super().action_post()

    def button_cancel(self):
        self = self.with_context(force_draft=True)
        return super(AccountMove, self).button_cancel()

    def button_draft(self):
        if self.country_code != self.env.ref("base.ve").code:
            return super().button_draft()

        if self.env.context.get("force_draft"):
            return super().button_draft()

        _logger.info("Button draft called on move %s", self.move_type)
        if self.move_type == "entry":
            return super().button_draft()

        raise ValidationError(
            """You cannot reset to draft an invoice in the Venezuelan localization.
Please create a credit note instead.
        """
        )

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for rec in self:
            if rec.state == "posted":
                rec.l10n_ve_invoice_date = fields.Datetime.now()
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:

            if record.move_id.move_type == "entry":
                continue

            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue

            record._put_unique_tax_per_line()
        return res

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.move_id.move_type == "entry":
                continue
            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue

            record._put_unique_tax_per_line()
        return res

    def _put_unique_tax_per_line(self):
        self.ensure_one()
        if self.display_type not in ("product", "discount"):
            return

        if len(self.tax_ids) == 0:
            if self.move_id.move_type in ("out_invoice", "out_refund", "out_receipt"):
                self.tax_ids = [Command.link(self.env.company.account_sale_tax_id.id)]
                self.move_id.message_post(body=_("Added default sales tax to line: %s.") % self.name)

            if self.move_id.move_type in ("in_invoice", "in_refund", "in_receipt"):
                self.tax_ids = [Command.link(self.env.company.account_purchase_tax_id.id)]
