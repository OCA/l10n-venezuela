import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMoveRetention(models.Model):
    _inherit = "account.move"

    apply_islr_retention = fields.Boolean(string="Apply ISLR Retention?", default=False)
    islr_voucher_number = fields.Char(copy=False)
    iva_voucher_number = fields.Char(copy=False)
    municipal_voucher_number = fields.Char(copy=False)
    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?", default=False
    )
    l10n_ve_missing_iva_withholding_type = fields.Boolean(
        compute="_compute_l10n_ve_missing_iva_withholding_type",
    )

    @api.depends(
        "partner_id",
        "partner_id.withholding_type_id",
        "l10n_ve_third_party_partner_id",
        "l10n_ve_third_party_partner_id.withholding_type_id",
        "move_type",
        "country_code",
        "generate_iva_retention",
        "state",
    )
    def _compute_l10n_ve_missing_iva_withholding_type(self):
        for move in self:
            move.l10n_ve_missing_iva_withholding_type = bool(
                move._l10n_ve_get_iva_withholding_type_warning()
            )

    def _l10n_ve_requires_iva_withholding_type(self):
        self.ensure_one()
        return (
            self.state == "draft"
            and self.generate_iva_retention
            and self.country_code == "VE"
            and self.move_type in ("in_invoice", "in_refund", "in_receipt")
            and bool(self.partner_id)
        )

    def _l10n_ve_get_iva_withholding_type_warning(self):
        self.ensure_one()
        if not self._l10n_ve_requires_iva_withholding_type():
            return None
        partner = self._l10n_ve_withholding_partner()
        if partner._l10n_ve_get_withholding_type():
            return None
        return {
            "title": _("Missing IVA withholding percentage"),
            "message": _(
                'The contact "%(partner)s" has no IVA withholding percentage '
                "configured. Set the field \"Withholding Type\" on the partner "
                "before confirming this operation.",
                partner=partner.display_name,
            ),
        }

    def _l10n_ve_withholding_partner(self):
        self.ensure_one()
        if (
            self.move_type in ("in_invoice", "in_refund")
            and self.l10n_ve_third_party_partner_id
        ):
            return self.l10n_ve_third_party_partner_id
        return self.partner_id

    retention_islr_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="ISLR Retention Lines",
        domain=[
            "|",
            ("payment_concept_id", "!=", False),
            ("retention_id.type_retention", "=", "islr"),
        ],
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="IVA Retention Lines",
        domain=[("retention_id.type_retention", "=", "iva")],
    )

    retention_municipal_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="Municipal Retention Lines",
        domain=[
            "|",
            ("economic_activity_id", "!=", False),
            ("retention_id.type_retention", "=", "municipal"),
        ],
    )

    iva_retention_id = fields.Many2one(
        "account.retention",
        compute="_compute_supplier_retention_links",
        string="IVA retention document",
    )
    islr_retention_id = fields.Many2one(
        "account.retention",
        compute="_compute_supplier_retention_links",
        string="ISLR retention document",
    )

    @api.depends(
        "retention_iva_line_ids.retention_id",
        "retention_iva_line_ids.state",
        "retention_islr_line_ids.retention_id",
        "retention_islr_line_ids.state",
    )
    def _compute_supplier_retention_links(self):
        for move in self:
            iva_lines = move.retention_iva_line_ids.filtered(
                lambda line: line.state != "cancel"
            )
            ret_iva = iva_lines.mapped("retention_id")[:1]
            move.iva_retention_id = ret_iva

            islr_lines = move.retention_islr_line_ids.filtered(
                lambda line: line.state != "cancel"
            )
            ret_islr = islr_lines.mapped("retention_id")[:1]
            move.islr_retention_id = ret_islr

    def action_open_iva_retention(self):
        self.ensure_one()
        if not self.iva_retention_id:
            raise UserError(
                _("No IVA retention document linked to this vendor bill.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.iva_retention_id.display_name,
            "res_model": "account.retention",
            "res_id": self.iva_retention_id.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "l10n_ve_withholding.view_retention_iva_form_l10n_ve_withholding"
                    ).id,
                    "form",
                )
            ],
            "target": "current",
        }

    def action_open_islr_retention(self):
        self.ensure_one()
        if not self.islr_retention_id:
            raise UserError(
                _("No ISLR retention document linked to this vendor bill.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.islr_retention_id.display_name,
            "res_model": "account.retention",
            "res_id": self.islr_retention_id.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "l10n_ve_withholding.view_retention_islr_form_l10n_ve_withholding"
                    ).id,
                    "form",
                )
            ],
            "target": "current",
        }

    def action_print_iva_retention(self):
        self.ensure_one()
        if not self.iva_retention_id:
            raise UserError(
                _("No IVA retention document linked to this vendor bill.")
            )
        return self.iva_retention_id.action_print_retention_voucher()

    def action_print_islr_retention(self):
        self.ensure_one()
        if not self.islr_retention_id:
            raise UserError(
                _("No ISLR retention document linked to this vendor bill.")
            )
        return self.islr_retention_id.action_print_retention_voucher()

    def action_post(self):
        """Create supplier retentions only after the move is actually posted."""
        res = super().action_post()
        self._l10n_ve_create_post_retentions()
        return res

    def _l10n_ve_create_post_retentions(self):
        for move in self.filtered(lambda m: m.state == "posted"):
            if move.move_type not in ("in_invoice", "in_refund"):
                continue

            if move.retention_islr_line_ids and not move.islr_voucher_number:
                move._validate_islr_retention()
                retention = move._create_supplier_retention("islr")
                retention.with_context(skip_is_manually_modified=True).action_post()
                move.islr_voucher_number = retention.number

            if move.retention_municipal_line_ids:
                move._validate_municipal_retention()
                retention = move._create_supplier_retention("municipal")
                retention.with_context(skip_is_manually_modified=True).action_post()

            if move.generate_iva_retention and not move.retention_iva_line_ids.filtered(
                lambda line: line.state != "cancel"
            ):
                move._validate_iva_retention()
                retention = move._create_supplier_retention("iva")
                retention.with_context(skip_is_manually_modified=True).action_post()
                move.iva_voucher_number = retention.number

        move_retention = self.filtered(
            lambda move: move.state == "posted" and move.origin_payment_id.is_retention
        )
        for move in move_retention:
            move._set_retention_name()


    def _set_retention_name(self):
        self.ensure_one()
        payment = self.origin_payment_id
        if not all((payment.retention_line_ids, payment.retention_id.number)):
            return

        move_name = (
            payment.journal_id.code
            + f"-{payment.retention_id.number}"
            + f"-{payment.retention_line_ids[0].move_id.name}"
        )

        if payment.retention_id.type_retention == "islr":
            move_name += f"-{payment.retention_line_ids[0].payment_concept_id.name[:5]}"

        self.name = move_name

    def _validate_islr_retention(self):
        """
        Validate that the company has a journal for ISLR supplier retention, the
        partner a type of person and that the amount of the retention is greater
        than zero, in order for the ISLR retention to be created.
        """
        self.ensure_one()
        if not self.env.company.islr_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for ISLR supplier retention.")
            )
        islr_retention = self.retention_islr_line_ids
        sum_invoice_amount = sum(
            islr_retention.filtered(lambda rl: rl.state != "cancel").mapped(
                "invoice_amount"
            )
        )
        if sum_invoice_amount > self.tax_totals["base_amount"]:
            raise UserError(
                _(
                    "The amount of the retention is greater than the total amount of the invoice."  # noqa: E501
                )
            )
        withholding_partner = self._l10n_ve_withholding_partner()
        if not withholding_partner.type_person_id:
            raise UserError(_("The partner must have a type of person"))
        if sum_invoice_amount <= 0:
            raise UserError(_("The amount of the retention must be greater than zero."))

    def _validate_iva_retention(self):
        """
        Validate that the company has a journal for IVA supplier retention and
        that the invoice has at least one tax, in order for the IVA retention to
        be created.
        """
        self.ensure_one()
        withholding_partner = self._l10n_ve_withholding_partner()
        if not withholding_partner._l10n_ve_get_withholding_type():
            raise UserError(
                _(
                    'The contact "%(partner)s" has no IVA withholding percentage '
                    "configured. Set the field \"Withholding Type\" on the partner "
                    "before confirming this operation.",
                    partner=withholding_partner.display_name,
                )
            )
        if not self.env.company.iva_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for IVA supplier retention.")
            )
        if not any(
            self.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0)
        ):
            raise UserError(_("The invoice has no tax."))

    def _validate_municipal_retention(self):
        """
        Validate that the company has a journal for municipal supplier retention
        in order for the municipal retention to be created.
        """
        self.ensure_one()
        if not self.env.company.municipal_supplier_retention_journal_id:
            raise UserError(
                _("The company must have a journal for municipal supplier retention.")
            )

    @api.model
    def _create_supplier_retention(self, type_retention):
        """
        Calls the method to create the payment for the retention of the type
        specified in the type_retention parameter.

        Params
        ------
        invoice_id: account.move
            The invoice to which the retention will be applied.
        type_retention: tuple[str, str]
            The type of retention and the type of invoice.

        Returns
        -------
        account.retention
            The retention created.
        """
        self.ensure_one()
        withholding_partner = self._l10n_ve_withholding_partner()
        if type_retention == "iva" and not withholding_partner._l10n_ve_get_withholding_type():
            raise UserError(_("The partner has no withholding type."))

        retention = self.env["account.retention"]
        payment_type = "outbound"
        if self.move_type == "in_refund":
            payment_type = "inbound"

        journals = {
            "iva": self.env.company.iva_supplier_retention_journal_id,
            "islr": self.env.company.islr_supplier_retention_journal_id,
            "municipal": self.env.company.municipal_supplier_retention_journal_id,
        }

        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        payment_vals = {
            "payment_type": payment_type,
            "partner_type": "supplier",
            "partner_id": withholding_partner.id,
            "journal_id": journals[type_retention].id,
            "payment_type_retention": type_retention,
            "payment_method_id": self.env.ref(
                "account.account_payment_method_manual_in"
            ).id,
            "is_retention": True,
            "currency_id": self.env.user.company_id.currency_id.id,
            "is_sent": True,
        }
        if type_retention == "islr":
            payment_vals["retention_line_ids"] = self.retention_islr_line_ids.filtered(
                lambda rl: rl.state != "cancel"
            ).ids
        elif type_retention == "municipal":
            payment_vals["retention_line_ids"] = (
                self.retention_municipal_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )

        payment = Payment.create(payment_vals)
        retention_vals = {
            "payment_ids": [Command.link(payment.id)],
            "date_accounting": self.date,
            "date": self.date if self.move_type == "in_invoice" else False,
            "type_retention": type_retention,
            "type": "in_invoice",
            "partner_id": withholding_partner.id,
        }

        if type_retention == "iva":
            retention_lines_data = Retention.compute_retention_lines_data(self, payment)
            retention_vals["retention_line_ids"] = [
                Command.create(line) for line in retention_lines_data
            ]
        elif type_retention == "islr":
            retention_vals["retention_line_ids"] = (
                self.retention_islr_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )
        else:
            retention_vals["retention_line_ids"] = (
                self.retention_municipal_line_ids.filtered(
                    lambda rl: rl.state != "cancel"
                ).ids
            )

        retention = Retention.create(retention_vals)
        payment.compute_retention_amount_from_retention_lines()
        return retention

    def action_register_payment(self):
        """
        Override the action_register_payment method to send the is_out_invoice
        context to the payment wizard.

        This is used to know if the invoice is an outgoing invoice, in order to
        know if the option to create a retention should be displayed in the
        payment wizard.
        """
        res = super().action_register_payment()
        res["context"]["default_is_out_invoice"] = any(
            self.filtered(lambda i: i.move_type in ("out_invoice", "out_refund"))
        )
        return res

    @api.depends("move_type", "line_ids.amount_residual")
    def _compute_payments_widget_reconciled_info(self):
        res = super()._compute_payments_widget_reconciled_info()
        for record in self:
            if not record.invoice_payments_widget:
                continue

            for payment in record.invoice_payments_widget.get("content"):
                if not payment.get("account_payment_id", False):
                    payment["is_retention"] = False
                    continue
                payment_id = self.env["account.payment"].browse(
                    payment["account_payment_id"]
                )
                payment["is_retention"] = payment_id.is_retention

        return res

    @api.model
    def validate_payment(self, payment):
        """This function is used to not add withholding in the calculation of
        the last payment date"""
        if payment.get("is_retention", False):
            return False
        return True
