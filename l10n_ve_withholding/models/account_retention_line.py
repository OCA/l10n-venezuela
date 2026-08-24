import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"
    _check_company_auto = True

    name = fields.Char(
        string="Description",
        required=True,
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(related="retention_id.state")
    company_currency_id = fields.Many2one(related="retention_id.company_currency_id")
    retention_id = fields.Many2one(
        "account.retention", string="Retention", ondelete="cascade"
    )
    invoice_type = fields.Selection(
        selection=[
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
        ],
    )
    date_accounting = fields.Date(related="retention_id.date_accounting", store=True)
    aliquot = fields.Float(digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    amount_tax_incurred = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits="Tasa")
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    supplier_invoice_reference = fields.Char(
        related="move_id.ref",
        string="Vendor Reference",
    )
    affected_invoice_display_name = fields.Char(
        compute="_compute_affected_invoice_display_name",
        string="Affected Invoice",
    )
    is_client_retention = fields.Boolean(default=True)
    invoice_amount = fields.Float(
        string="Taxable income",
        digits="Tasa",
        store=True,
        readonly=False,
    )
    invoice_total = fields.Float(string="Total invoiced", digits="Tasa", store=True)
    iva_amount = fields.Float(string="IVA", digits=(16, 2))

    retention_amount = fields.Float(
        digits="Tasa",
        compute="_compute_retention_amount",
        store=True,
        readonly=False,
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )
    code = fields.Char(related="payment_concept_id.line_payment_concept_ids.code")
    economic_activity_id = fields.Many2one(
        "economic.activity",
        ondelete="cascade",
        compute="_compute_economic_activity_id",
        readonly=False,
        store=True,
        index=True,
    )

    payment_id = fields.Many2one("account.payment", "Payment", index=True)

    payment_date = fields.Date(related="payment_id.date", store=True)

    payment_journal_id = fields.Many2one(
        "account.journal",
        "Payment journal",
        ondelete="cascade",
        index=True,
        related="payment_id.journal_id",
    )

    related_pay_from = fields.Float(
        string="Pays from",
        compute="_compute_related_fields",
        store=True,
    )

    related_percentage_tax_base = fields.Float(
        string="% tax base",
        compute="_compute_related_fields",
        store=True,
        readonly=False,
    )

    related_percentage_fees = fields.Float(
        string="% tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    related_amount_subtract_fees = fields.Float(
        string="Amount subtract tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    @api.depends(
        "move_id.l10n_ve_control_number",
        "move_id.ref",
        "move_id.l10n_ve_invoice_number",
        "move_id.name",
    )
    def _compute_affected_invoice_display_name(self):
        for line in self:
            move = line.move_id
            identifier = (
                move.l10n_ve_control_number or move.ref or move.l10n_ve_invoice_number
            )
            if identifier and move.name and identifier != move.name:
                line.affected_invoice_display_name = f"{identifier} ({move.name})"
            else:
                line.affected_invoice_display_name = identifier or move.name

    @api.depends("retention_id.type_retention", "move_id")
    def _compute_name(self):
        for record in self:
            if record.name:
                continue
            names = {
                "islr": _("ISLR Retention"),
                "iva": _("IVA Retention"),
                "municipal": _("Municipal Retention"),
            }
            type_retention = "islr"
            if record.retention_id.type_retention:
                type_retention = record.retention_id.type_retention
            elif record.move_id:
                if record in record.move_id.retention_iva_line_ids:
                    type_retention = "iva"
                elif record in record.move_id.retention_municipal_line_ids:
                    type_retention = "municipal"

            record.name = names.get(type_retention, _("Retention"))

    @api.depends("retention_id", "move_id")
    def _compute_economic_activity_id(self):
        for line in self:
            if line.economic_activity_id:
                continue
            if line.retention_id and line.retention_id.type_retention == "municipal":
                line.economic_activity_id = (
                    line.retention_id.partner_id.economic_activity_id
                )
            if (
                line.move_id
                and line.id in line.move_id.retention_municipal_line_ids.ids
            ):
                partner = line.move_id._l10n_ve_withholding_partner()
                line.economic_activity_id = partner.economic_activity_id

    def unlink(self):
        lines = self.exists()
        payments_to_unlink = lines.mapped("payment_id").filtered(
            lambda p: p.state in ("draft", "canceled")
        )
        if payments_to_unlink:
            payments_to_unlink.unlink()
        return super(AccountRetentionLine, lines).unlink()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.supplier_invoice_reference or self.move_id.display_name,
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "views": [(self.env.ref("account.view_move_form").id, "form")],
            "target": "current",
        }

    @api.onchange("payment_concept_id")
    @api.depends("payment_concept_id", "move_id")
    def _compute_related_fields(self):
        """
        This compute is used to get the related fields from the payment concept
        of the partner to generate the ISLR retention line
        """
        lines_from_islr_retention = self.filtered(
            lambda line: line.payment_concept_id
            and (not line.retention_id or line.retention_id.type_retention == "islr")
        )
        for record in lines_from_islr_retention:
            # Payment concept of the line
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if not record.move_id:
                    continue
                # if not record.move_id.partner_id.type_person_id:
                #     raise UserError(_("The partner does not have a type of person"))

                partner = record.move_id._l10n_ve_withholding_partner()
                if partner.type_person_id.id == line.type_person_id.id:
                    # compare the type_person_id of the partner with the
                    # type_person_id of the payment concept and set the related
                    # fields.
                    record.invoice_total = record.move_id.tax_totals["total_amount"]
                    record.related_pay_from = line.pay_from
                    record.related_percentage_tax_base = line.percentage_tax_base
                    record.related_percentage_fees = line.tariff_id.percentage
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract

                    if (
                        not record.retention_id
                        or record.retention_id.type == "in_invoice"
                    ):
                        # We don't want this fields to be computed when the
                        # retention is created from a customer invoice since
                        # they are filled by the user.
                        record.invoice_amount = record.move_id.tax_totals["base_amount"]

    @api.onchange(
        "invoice_amount",
        "iva_amount",
        "aliquot",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "payment_concept_id",
    )
    @api.depends(
        "invoice_amount",
        "iva_amount",
        "aliquot",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "payment_concept_id",
        "economic_activity_id",
        "move_id",
        "retention_id.type",
        "retention_id.type_retention",
    )
    def _compute_retention_amount(self):
        for record in self:
            retention = record.retention_id
            type_retention = retention.type_retention if retention else False
            retention_type = retention.type if retention else False

            if not type_retention:
                if record.payment_concept_id:
                    type_retention = "islr"
                elif record.economic_activity_id:
                    type_retention = "municipal"

            if type_retention == "iva" and retention_type == "out_invoice":
                record.retention_amount = record.retention_amount or 0.0
                continue

            if type_retention == "islr" and (
                retention_type == "in_invoice"
                or (not retention and record.payment_concept_id)
            ):
                calculated = (
                    record.invoice_amount
                    * (record.related_percentage_tax_base / 100)
                    * (record.related_percentage_fees / 100)
                ) - record.related_amount_subtract_fees
                record.retention_amount = max(0.0, calculated)
                continue

            if type_retention == "iva" and retention_type == "in_invoice":
                record.retention_amount = record.iva_amount * (
                    record.related_percentage_tax_base / 100
                )
                continue

            if type_retention == "municipal" and (
                retention_type == "in_invoice"
                or (not retention and record.economic_activity_id)
            ):
                record.retention_amount = record.invoice_amount * record.aliquot / 100
                continue

            record.retention_amount = record.retention_amount or 0.0

    @api.onchange("economic_activity_id", "move_id")
    def onchange_economic_activity_id(self):
        """
        Computes the aliquot of the line when the economic
        activity is changed for the retentions
        of municipal type.
        """
        municipal_retention_lines_with_economic_activity_and_invoice = self.filtered(
            lambda line: (
                not line.retention_id
                or (line.retention_id.type_retention == "municipal")
            )
            and line.economic_activity_id
            and line.move_id
        )

        for record in municipal_retention_lines_with_economic_activity_and_invoice:
            if not record.retention_id or record.retention_id.type == "in_invoice":
                # We don't want this fields to be computed when the retention is
                # created from a customer invoice since they are filled by the user.
                record.invoice_amount = record.move_id.tax_totals["base_amount"]

            record.invoice_total = record.move_id.tax_totals["total_amount"]

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100

    @api.onchange("invoice_amount", "aliquot")
    def onchange_municipal_invoice_amount(self):
        """
        Computes the retention amount when the invoice amount or the aliquot are
        changed for the retentions of municipal type.
        """
        for record in self.filtered(
            lambda line: (not line.retention_id and line.economic_activity_id)
            or line.retention_id.type_retention == "municipal"
        ):
            record.retention_amount = record.invoice_amount * record.aliquot / 100

    @api.constrains(
        "retention_amount",
        "invoice_total",
        "invoice_amount",
    )
    def _constraint_amounts(self):
        for record in self:
            if any(
                (
                    record.retention_amount == 0,
                    record.invoice_total == 0,
                    record.invoice_amount == 0,
                )
            ):
                raise ValidationError(
                    _("You can not create a retention with 0 amount.")
                )

            is_vef_the_base_currency = self.env.company.currency_id == self.env.ref(
                "base.VEF"
            )
            is_client_retention = record.retention_id.type == "out_invoice"
            if (
                is_vef_the_base_currency
                and is_client_retention
                and record.retention_amount > record.move_id.amount_residual
            ):
                raise ValidationError(
                    _(
                        "The total amount of the retention is greater than the residual amount of"  # noqa: E501
                        " the invoice."
                    )
                )

    def get_invoice_paid_amount_not_related_with_retentions(self):
        """
        Returns the amount paid on the invoice that is not related with the
        retentions for the ISLR supplier retention lines.
        """
        # We need to get the lines without duplicate invoices because the
        # invoice can have more than one retention line.
        lines_without_duplicate_invoices = self.env[self._name]
        for line in self.filtered(
            lambda line: line.retention_id
            and line.retention_id.type_retention == "islr"
        ):
            if line.move_id in lines_without_duplicate_invoices.mapped("move_id"):
                continue
            lines_without_duplicate_invoices |= line

        for line in lines_without_duplicate_invoices:
            partials = self.env["account.partial.reconcile"].search(
                [
                    (
                        "credit_move_id",
                        "=",
                        line.move_id.line_ids.filtered(
                            lambda line: line.account_id.account_type
                            == "liability_payable"
                            and line.credit > 0
                        )[0].id,
                    )
                ]
            )
            retention_payments = self.env["account.payment"].search(
                [
                    (
                        "move_id.line_ids",
                        "in",
                        partials.mapped("debit_move_id").ids,
                    ),
                    ("is_retention", "=", True),
                ]
            )
            # The invoice paid amount not related with retentions is the sum of
            # the debit amounts of the partials that are not related with the
            # retention payments.
            invoice_paid_amount_not_related_with_retentions = sum(
                partial.debit_amount_currency
                for partial in partials.filtered(
                    lambda p: p.debit_move_id
                    not in retention_payments.mapped("move_id.line_ids")  # noqa: B023
                )
            )
            return invoice_paid_amount_not_related_with_retentions
