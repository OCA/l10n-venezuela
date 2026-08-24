import json
import logging
import re
from collections import defaultdict
from datetime import datetime

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

from ..utils.utils_retention import (
    load_retention_lines,
    search_invoices_with_taxes,
)

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Retention"
    _check_company_auto = True

    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        # states={"draft": [("readonly", False)]},
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        # states={"draft": [("readonly", False)]},
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
        tracking=True,
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Type retention",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        # states={"draft": [("readonly", False)]},
        help="Social reason",
        tracking=True,
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Voucher Date",
        # states={"draft": [("readonly", False)]},
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Accounting Date",
        # states={"draft": [("readonly", False)]},
        default=fields.Date.context_today,
        help=(
            "Date of arrival of the document and date to be used to make the accounting record."  # noqa: E501
            " Keep blank to use current date."
        ),
    )
    allowed_lines_move_ids = fields.Many2many(
        "account.move",
        compute="_compute_allowed_lines_move_ids",
        help=(
            "Technical field to store the allowed move types for the ISLR retention lines. This is"  # noqa: E501
            " used to filter the moves that can be selected in the ISLR retention lines."  # noqa: E501
        ),
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        # states={"draft": [("readonly", False)]},
        help="Retentions",
    )
    affected_invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_affected_invoice_ids",
        string="Affected Invoices",
    )
    affected_invoice_display_names = fields.Char(
        compute="_compute_affected_invoice_display_names",
        string="Affected Invoices",
    )

    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
    )

    total_invoice_amount = fields.Float(
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    amount_tax = fields.Float(string="Tax Total", compute="_compute_totals", store=True)
    total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )

    original_lines_per_invoice_counter = fields.Char(
        help=(
            "Technical field to store the quantity of retention"
            "lines per invoice before the user"
            " changes them. This is used to know if the user has"
            "deleted the retention lines when"
            " the invoice is changed, in order to delete all"
            "the other lines of the same invoice"
            " that the one that just has been deleted."
        )
    )
    l10n_ve_missing_iva_withholding_type = fields.Boolean(
        compute="_compute_l10n_ve_missing_iva_withholding_type",
    )

    @api.depends(
        "partner_id",
        "partner_id.withholding_type_id",
        "type_retention",
        "type",
        "state",
    )
    def _compute_l10n_ve_missing_iva_withholding_type(self):
        for retention in self:
            retention.l10n_ve_missing_iva_withholding_type = bool(
                retention._l10n_ve_get_iva_withholding_type_warning()
            )

    def _l10n_ve_requires_iva_withholding_type(self):
        self.ensure_one()
        return (
            self.state == "draft"
            and self.type_retention == "iva"
            and self.type == "in_invoice"
            and bool(self.partner_id)
        )

    def _l10n_ve_get_iva_withholding_type_warning(self):
        self.ensure_one()
        if not self._l10n_ve_requires_iva_withholding_type():
            return None
        if self.partner_id._l10n_ve_get_withholding_type():
            return None
        return {
            "title": _("Missing IVA withholding percentage"),
            "message": _(
                'The contact "%(partner)s" has no IVA withholding percentage '
                'configured. Set the field "Withholding Type" on the partner '
                "before confirming this operation.",
                partner=self.partner_id.display_name,
            ),
        }

    @api.depends("type", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund")
                if retention.type == "in_invoice"
                else ("out_invoice", "out_refund")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("move_type", "in", allowed_types),
            ]
            if retention.type == "in_invoice":
                domain += [
                    "|",
                    ("partner_id", "=", retention.partner_id.id),
                    ("l10n_ve_third_party_partner_id", "=", retention.partner_id.id),
                ]
            else:
                domain.append(("partner_id", "=", retention.partner_id.id))

            retention.allowed_lines_move_ids = self.env["account.move"].search(domain)

    @api.depends("retention_line_ids.move_id")
    def _compute_affected_invoice_ids(self):
        for retention in self:
            retention.affected_invoice_ids = retention.retention_line_ids.mapped(
                "move_id"
            )

    @api.depends(
        "retention_line_ids.move_id.l10n_ve_control_number",
        "retention_line_ids.move_id.ref",
        "retention_line_ids.move_id.l10n_ve_invoice_number",
        "retention_line_ids.move_id.name",
    )
    def _compute_affected_invoice_display_names(self):
        for retention in self:
            names = retention.retention_line_ids.mapped("affected_invoice_display_name")
            retention.affected_invoice_display_names = ", ".join(
                dict.fromkeys(name for name in names if name)
            )

    @api.depends(
        "retention_line_ids.invoice_amount",
        "retention_line_ids.iva_amount",
        "retention_line_ids.retention_amount",
    )
    def _compute_totals(self):
        for retention in self:
            retention.total_invoice_amount = 0
            retention.amount_tax = 0
            retention.total_retention_amount = 0

            for line in retention.retention_line_ids:
                if line.move_id.move_type in ("in_refund", "out_refund"):
                    retention.total_invoice_amount -= float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.amount_tax -= float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount -= float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                else:
                    retention.total_invoice_amount += float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.amount_tax += float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount += float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes
        for IVA retentions that are not posted.
        """
        self._validate_retention_journals()
        for retention in self.filtered(
            lambda r: (r.state, r.type_retention) == ("draft", "iva") and r.partner_id
        ):
            if retention.type == "in_invoice":
                return retention._load_retention_lines_for_iva_supplier_retention()
            return retention._load_retention_lines_for_iva_customer_retention()

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        self.date_accounting = fields.Date.today()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_refund", "in_invoice")),
            ("amount_residual", ">", 0),
            "|",
            ("partner_id", "=", self.partner_id.id),
            ("l10n_ve_third_party_partner_id", "=", self.partner_id.id),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda line: line.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the supplier.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _load_retention_lines_for_iva_customer_retention(self):
        self.ensure_one()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_refund", "out_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda line: line.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the customer.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _validate_retention_journals(self):
        """
        Validate that the company has the journals configured for the retention type.
        """
        for retention in self:
            # IVA
            if (retention.type_retention, retention.type) == (
                "iva",
                "in_invoice",
            ) and not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier IVA retention journal configured."  # noqa: E501
                    )
                )
            if (retention.type_retention, retention.type) == (
                "iva",
                "out_invoice",
            ) and not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer IVA retention journal configured."  # noqa: E501
                    )
                )
            # ISLR
            if (retention.type_retention, retention.type) == (
                "islr",
                "in_invoice",
            ) and not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier ISLR retention journal configured."  # noqa: E501
                    )
                )
            if (retention.type_retention, retention.type) == (
                "islr",
                "out_invoice",
            ) and not self.env.company.islr_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer ISLR retention journal configured."  # noqa: E501
                    )
                )
            # Municipal
            if (retention.type_retention, retention.type) == (
                "municipal",
                "in_invoice",
            ) and not self.env.company.municipal_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier municipal retention journal configured."  # noqa: E501
                    )
                )
            if (retention.type_retention, retention.type) == (
                "municipal",
                "out_invoice",
            ) and not self.env.company.municipal_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer municipal retention journal configured."  # noqa: E501
                    )
                )

    def clear_retention(self):
        """
        Clear retention lines and payments.
        """
        self.ensure_one()
        self.update(
            {
                "retention_line_ids": (
                    Command.clear()
                    if any(
                        isinstance(id, models.NewId)
                        for id in self.retention_line_ids.ids
                    )
                    else False
                ),
            }
        )

    @api.onchange("retention_line_ids")
    def onchange_retention_line_ids(self):
        """
        On the IVA supplier retention when a line is deleted, delete all the
        others lines that have the same invoice.
        """
        for retention in self.filtered(
            lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id
        ):
            original_lines_per_invoice_counter = json.loads(
                retention.original_lines_per_invoice_counter
            )
            lines_per_invoice_counter = defaultdict(int)
            for line in retention.retention_line_ids:
                lines_per_invoice_counter[str(line.move_id.id)] += 1

            for line in retention.retention_line_ids:
                if (
                    line.move_id.id
                    and lines_per_invoice_counter[str(line.move_id.id)]
                    != original_lines_per_invoice_counter[str(line.move_id.id)]
                ):
                    retention.retention_line_ids -= line

            return {
                "value": {
                    "original_lines_per_invoice_counter": json.dumps(
                        lines_per_invoice_counter
                    )
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._create_payments_from_retention_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("retention_line_ids", False):
            self._create_payments_from_retention_lines()
        return res

    def unlink(self):
        for record in self:
            if record.state == "emitted":
                raise ValidationError(
                    _(
                        "You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"  # noqa: E501
                    )
                )
        return super().unlink()

    def _create_payments_from_retention_lines(self):
        """
        Create the payments from the retention lines for an IVA retention.

        When there are retention lines without payments, this method will create
        a payment for each set of retention lines that have the same invoice.
        """
        for retention in self:
            if any(retention.payment_ids) or retention.type_retention != "iva":
                continue
            payment_vals = {
                "retention_id": retention.id,
                "partner_id": retention.partner_id.id,
                "payment_type_retention": "iva",
                "is_retention": True,
                "currency_id": self.env.user.company_id.currency_id.id,
                "is_sent": True,
            }

            def account_retention_line_empty_recordset():
                return self.env["account.retention.line"]

            if retention.type == "in_invoice":
                self._create_payments_for_iva_supplier(
                    payment_vals, account_retention_line_empty_recordset
                )
            if retention.type == "out_invoice":
                self._create_payments_for_iva_customer(
                    payment_vals, account_retention_line_empty_recordset
                )

    def _create_payments_for_iva_supplier(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        payment_vals["partner_type"] = "supplier"
        payment_vals["journal_id"] = (
            self.env.company.iva_supplier_retention_journal_id.id
        )
        in_refund_lines = self.retention_line_ids.filtered(
            lambda line: line.move_id.move_type == "in_refund"
        )
        in_invoice_lines = self.retention_line_ids.filtered(
            lambda line: line.move_id.move_type == "in_invoice"
        )

        in_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        in_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in in_refund_lines:
            in_refunds_dict[line.move_id] += line
        for line in in_invoice_lines:
            in_invoices_dict[line.move_id] += line

        for lines in in_refunds_dict.values():
            partner = lines[0].move_id._l10n_ve_withholding_partner()
            vals = {
                **payment_vals,
                "partner_id": partner.id,
                "payment_type": "inbound",
                "payment_method_line_id": (
                    payment_vals["journal_id"]
                    and self.env["account.journal"]
                    .browse(payment_vals["journal_id"])
                    .inbound_payment_method_line_ids.filtered(
                        lambda method: method.code == "manual"
                    )[:1]
                    .id
                ),
            }
            payment = Payment.create(vals)
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in in_invoices_dict.values():
            partner = lines[0].move_id._l10n_ve_withholding_partner()
            vals = {
                **payment_vals,
                "partner_id": partner.id,
                "payment_type": "outbound",
                "payment_method_line_id": (
                    payment_vals["journal_id"]
                    and self.env["account.journal"]
                    .browse(payment_vals["journal_id"])
                    .outbound_payment_method_line_ids.filtered(
                        lambda method: method.code == "manual"
                    )[:1]
                    .id
                ),
            }
            payment = Payment.create(vals)
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def _create_payments_for_iva_customer(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        payment_vals["partner_type"] = "customer"
        payment_vals["journal_id"] = (
            self.env.company.iva_customer_retention_journal_id.id
        )
        out_refund_lines = self.retention_line_ids.filtered(
            lambda line: line.move_id.move_type == "out_refund"
        )
        out_invoice_lines = self.retention_line_ids.filtered(
            lambda line: line.move_id.move_type == "out_invoice"
        )

        out_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        out_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in out_refund_lines:
            out_refunds_dict[line.move_id] += line
        for line in out_invoice_lines:
            out_invoices_dict[line.move_id] += line

        for lines in out_refunds_dict.values():
            payment_vals["payment_type"] = "outbound"
            payment_vals["payment_method_line_id"] = (
                payment_vals["journal_id"]
                and self.env["account.journal"]
                .browse(payment_vals["journal_id"])
                .outbound_payment_method_line_ids.filtered(
                    lambda method: method.code == "manual"
                )[:1]
                .id
            )
            payment = Payment.create(payment_vals)
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in out_invoices_dict.values():
            payment_vals["payment_type"] = "inbound"
            payment_vals["payment_method_line_id"] = (
                payment_vals["journal_id"]
                and self.env["account.journal"]
                .browse(payment_vals["journal_id"])
                .inbound_payment_method_line_ids.filtered(
                    lambda method: method.code == "manual"
                )[:1]
                .id
            )
            payment = Payment.create(payment_vals)
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def action_draft(self):
        self.write({"state": "draft"})

    def _validate_iva_checklist_before_post(self):
        for retention in self.filtered(lambda r: r.type_retention == "iva"):
            errors = []

            journal = (
                retention.company_id.iva_supplier_retention_journal_id
                if retention.type == "in_invoice"
                else retention.company_id.iva_customer_retention_journal_id
            )
            if not journal:
                errors.append(
                    _(
                        "1) Diario IVA: no hay diario de retencion IVA "
                        "configurado para este tipo."
                    )
                )
            else:
                if journal.type not in ("bank", "cash"):
                    errors.append(
                        _(
                            "1) Diario IVA: el diario '%(journal)s' "
                            "debe ser de tipo Banco o Caja.",
                            journal=journal.display_name,
                        )
                    )
                if not journal.default_account_id and not journal.suspense_account_id:
                    errors.append(
                        _(
                            "1) Diario IVA: el diario '%(journal)s' no tiene "
                            "cuentas configuradas (cuenta por defecto o "
                            "cuenta transitoria).",
                            journal=journal.display_name,
                        )
                    )

            if not retention.partner_id._l10n_ve_get_withholding_type():
                errors.append(
                    _(
                        "4) Partner: el proveedor '%(partner)s' no tiene "
                        "tipo de retencion configurado.",
                        partner=retention.partner_id.display_name,
                    )
                )

            invoices = retention.retention_line_ids.mapped("move_id")
            if not invoices:
                errors.append(
                    _(
                        "2) Facturas: la retencion no tiene lineas "
                        "con facturas asociadas."
                    )
                )
            else:
                not_posted = invoices.filtered(lambda inv: inv.state != "posted")
                if not_posted:
                    errors.append(
                        _(
                            "2) Facturas: deben estar publicadas. "
                            "Facturas no publicadas: %(invoices)s",
                            invoices=", ".join(m.display_name for m in not_posted),
                        )
                    )

                without_residual = invoices.filtered(
                    lambda inv: inv.amount_residual <= 0
                )
                if without_residual:
                    errors.append(
                        _(
                            "2) Facturas: deben tener saldo pendiente > 0. "
                            "Facturas sin saldo pendiente: %(invoices)s",
                            invoices=", ".join(
                                m.display_name for m in without_residual
                            ),
                        )
                    )

                without_taxes = invoices.filtered(
                    lambda inv: not any(
                        line.tax_ids and line.tax_ids[0].amount > 0
                        for line in inv.line_ids
                    )
                )
                if without_taxes:
                    errors.append(
                        _(
                            "2) Facturas: deben tener impuestos > 0. "
                            "Facturas sin impuestos validos: %(invoices)s",
                            invoices=", ".join(m.display_name for m in without_taxes),
                        )
                    )

                current_retention = retention
                with_active_retention = invoices.filtered(
                    lambda inv, current=current_retention: any(
                        inv.retention_iva_line_ids.filtered(
                            lambda line, current=current: (
                                line.retention_id != current
                                and line.state in ("draft", "emitted")
                            )
                        )
                    )
                )
                if with_active_retention:
                    errors.append(
                        _(
                            "3) Facturas: ya tienen una retencion IVA activa "
                            "(draft/emitted). Facturas afectadas: %(invoices)s",
                            invoices=", ".join(
                                m.display_name for m in with_active_retention
                            ),
                        )
                    )

            if errors:
                raise UserError(
                    _(
                        "No se puede confirmar la retencion IVA porque "
                        "fallaron estas validaciones:\n\n%(errors)s",
                        errors="\n".join(errors),
                    )
                )

    def action_post(self):
        today = datetime.now()
        for retention in self:
            retention._validate_iva_checklist_before_post()
            if (
                retention.type in ["out_invoice", "out_refund", "out_debit"]
                and not retention.number
            ):
                raise UserError(_("Insert a number for the retention"))
            if not retention.date_accounting:
                retention.date_accounting = today
            if not retention.date:
                retention.date = today

            move_ids = retention.mapped("retention_line_ids.move_id")
            self.set_voucher_number_in_invoice(move_ids, retention)

            if not retention.payment_ids:
                payments = retention.create_payment_from_retention_form()
                retention.payment_ids = payments.ids

            if retention.type in ["in_invoice", "in_refund", "in_debit"]:
                retention._set_sequence()
                self.set_voucher_number_in_invoice(move_ids, retention)

        if retention.type_retention == "iva":
            if not re.fullmatch(r"\d{14}", retention.number):
                raise ValidationError(
                    _("IVA retention: Number must be exactly 14 numeric digits.")
                )

        self.payment_ids.write({"date": self.date_accounting})
        self._reconcile_all_payments()
        self.write({"state": "emitted"})

    def set_voucher_number_in_invoice(self, move, retention):
        if retention.type_retention == "iva":
            move.write({"iva_voucher_number": retention.number})
        elif retention.type_retention == "islr":
            move.write({"islr_voucher_number": retention.number})
        elif retention.type_retention == "municipal":
            move.write({"municipal_voucher_number": retention.number})

    def action_print_municipal_retention_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/get_xlsx_municipal_retention?&retention_id={self.id}",
            "target": "self",
        }

    def action_print_retention_voucher(self):
        self.ensure_one()
        if self.state != "emitted":
            raise UserError(_("Only emitted retentions can be printed."))
        if self.type_retention == "municipal":
            return self.action_print_municipal_retention_xlsx()
        return self.env.ref(
            "l10n_ve_withholding.retention_voucher_action"
        ).report_action(self, config=False)

    def _set_sequence(self):
        for retention in self.filtered(lambda r: not r.number):
            sequence_number = ""
            if retention.type_retention == "iva":
                sequence_number = retention.get_sequence_iva_retention().next_by_id()
            elif retention.type_retention == "islr":
                sequence_number = retention.get_sequence_islr_retention().next_by_id()
            else:
                sequence_number = (
                    retention.get_sequence_municipal_retention().next_by_id()
                )
            correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"  # noqa: E501
            retention.name = correlative
            retention.number = correlative

    @api.model
    def get_sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.iva.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones IVA",
                    "code": "retention.iva.control.number",
                    "padding": 8,
                }
            )
        return sequence

    @api.model
    def get_sequence_islr_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.islr.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones ISLR",
                    "code": "retention.islr.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def get_sequence_municipal_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.municipal.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones Municipal",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def clear_islr_retention_number(self):
        for line in self.retention_line_ids:
            if line.move_id.islr_voucher_number:
                line.move_id.islr_voucher_number = False

    def action_cancel(self):
        self.payment_ids.mapped("move_id.line_ids").remove_move_reconcile()
        self.payment_ids.with_context(skip_is_manually_modified=True).action_cancel()
        self.write({"state": "cancel"})
        self.clear_islr_retention_number()

    def create_payment_from_retention_form(self):
        """
        Create the corresponding payments for the retention based on the fields
        of the retention.

        This is meant to create the payment for the ISLR and municipal
        retentions and it is triggered on the action_post method of the
        retention if it still doesn't have payments at that point.

        Returns
        -------
        account.payment recordset
            The payments created for the retention.
        """
        self.ensure_one()
        Payment = self.env["account.payment"]
        journals = {
            (
                "islr",
                "in_invoice",
            ): self.env.company.islr_supplier_retention_journal_id,
            (
                "islr",
                "out_invoice",
            ): self.env.company.islr_customer_retention_journal_id,
            (
                "municipal",
                "in_invoice",
            ): self.env.company.municipal_supplier_retention_journal_id,
            (
                "municipal",
                "out_invoice",
            ): self.env.company.municipal_customer_retention_journal_id,
        }
        journal_id = journals[(self.type_retention, self.type)].id

        if self.type_retention == "islr":
            self._validate_islr_retention_fields()

        payment_type = "outbound" if self.type == "in_invoice" else "inbound"
        partner_type = "supplier" if self.type == "in_invoice" else "customer"
        payment_vals = []

        for line in self.retention_line_ids:
            if line.move_id.move_type == "in_refund":
                payment_type = "inbound" if self.type == "in_invoice" else "outbound"
            if line.move_id.move_type == "out_refund":
                payment_type = "outbound" if self.type == "out_invoice" else "inbound"

            payment_method_ref = (
                "account.account_payment_method_manual_in"
                if payment_type == "inbound"
                else "account.account_payment_method_manual_out"
            )

            payment_vals.append(
                {
                    "state": "draft",
                    "payment_type": payment_type,
                    "partner_type": partner_type,
                    "partner_id": line.move_id._l10n_ve_withholding_partner().id,
                    "journal_id": journal_id,
                    "payment_type_retention": self.type_retention,
                    "payment_method_id": self.env.ref(payment_method_ref).id,
                    "is_retention": True,
                    "retention_line_ids": line,
                    "currency_id": self.env.user.company_id.currency_id.id,
                }
            )

        # payments = Payment.create(payment_vals)
        payments = self.env["account.payment"]
        for vals in payment_vals:
            payments += Payment.create(vals)
        payments.compute_retention_amount_from_retention_lines()

        return payments

    def _validate_islr_retention_fields(self):
        """
        Validates the partner has a type person and all the retention lines have
        a payment concept.
        """
        self.ensure_one()
        without_type = self.retention_line_ids.mapped("move_id").filtered(
            lambda m: not m._l10n_ve_withholding_partner().type_person_id
        )
        if without_type:
            raise UserError(_("Select a type person"))
        if not any(
            self.retention_line_ids.filtered(lambda line: line.payment_concept_id)
        ):
            raise UserError(_("Select a payment concept"))

    def _reconcile_all_payments(self):
        """
        Reconcile all payments of the retention with the invoice of the lines
        corresponding to the payment.
        """
        for payment in self.mapped("payment_ids"):
            payment.with_context(skip_is_manually_modified=True).action_post()
            if not payment.move_id or not payment.move_id.line_ids:
                raise UserError(
                    _(
                        "El pago de retencion '%(payment)s' no genero "
                        "asiento contable al publicar.\n\n"
                        "Revise la configuracion del diario '%(journal)s':\n"
                        "- Cuenta por defecto o cuenta transitoria\n"
                        "- Cuentas de pagos/cobros pendientes\n"
                        "- Metodo de pago manual",
                        payment=payment.display_name,
                        journal=payment.journal_id.display_name,
                    )
                )
            if payment.company_currency_id.is_zero(payment.amount):
                continue
            if payment.partner_type == "supplier":
                self._reconcile_supplier_payment(payment)
            if payment.partner_type == "customer":
                self._reconcile_customer_payment(payment)

    def _get_line_to_reconcile(self, payment, account_type):
        lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == account_type
            and not line.reconciled
            and not payment.company_currency_id.is_zero(abs(line.balance))
        )
        if not lines:
            move_lines_detail = "\n".join(
                [
                    _(
                        "- Linea '%(name)s' | cuenta=%(account)s | "
                        "tipo=%(type)s | balance=%(balance)s | "
                        "reconciled=%(reconciled)s",
                        name=line.name or "/",
                        account=line.account_id.display_name,
                        type=line.account_id.account_type,
                        balance=line.balance,
                        reconciled=line.reconciled,
                    )
                    for line in payment.move_id.line_ids
                ]
            )
            raise ValidationError(
                _(
                    "No existen lineas conciliables en el asiento "
                    "del pago de retencion.\n\n"
                    "Pago: %(payment)s\n"
                    "Asiento: %(move)s\n"
                    "Tipo esperado de cuenta: %(account_type)s\n"
                    "Diario: %(journal)s\n"
                    "Monto pago: %(amount)s\n\n"
                    "Lineas del asiento:\n%(lines)s",
                    payment=payment.display_name,
                    move=payment.move_id.display_name,
                    account_type=account_type,
                    journal=payment.journal_id.display_name,
                    amount=payment.amount,
                    lines=move_lines_detail or _("- Sin lineas."),
                )
            )
        return lines[0]

    def _reconcile_supplier_payment(self, payment):
        line_to_reconcile = self._get_line_to_reconcile(payment, "liability_payable")
        payment.retention_line_ids.move_id.js_assign_outstanding_line(
            line_to_reconcile.id
        )

    def _reconcile_customer_payment(self, payment):
        line_to_reconcile = self._get_line_to_reconcile(payment, "asset_receivable")
        payment.retention_line_ids.move_id.js_assign_outstanding_line(
            line_to_reconcile.id
        )

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Computes the retention lines data for the given invoice.

        Params
        ------
        invoice_id: account.move
            The invoice for which the retention lines are computed.
        type_retention: tuple[str,str]
            The type of retention and the type of invoice.
        payment: account.payment
            The payment for which the retention lines are computed.

        Returns
        -------
        list[dict]
            The retention lines data.
        """
        tax_ids = invoice_id.invoice_line_ids.filtered(
            lambda line: line.tax_ids and line.tax_ids[0].amount > 0
        ).mapped("tax_ids")
        if not any(tax_ids):
            raise UserError(_("The invoice %s has no tax."), invoice_id.number)

        withholding_partner = invoice_id._l10n_ve_withholding_partner()
        withholding_type = withholding_partner._l10n_ve_get_withholding_type()
        if not withholding_type:
            raise UserError(_("The partner has no withholding type."))
        withholding_amount = withholding_type.value
        lines_data = []

        if len(invoice_id.tax_totals.get("subtotals", [])) < 1:
            raise UserError(
                _("The invoice %s has no tax subtotals."), invoice_id.number
            )

        for tax_group in invoice_id.tax_totals["subtotals"][0]["tax_groups"]:
            taxes = tax_ids.filtered(
                lambda line: line.tax_group_id.id == tax_group["id"]  # noqa: B023
            )
            if not taxes:
                continue
            tax = taxes[0]
            retention_amount = tax_group["tax_amount"] * (withholding_amount / 100)
            line_data = {
                "name": _("Iva Retention"),
                "invoice_type": invoice_id.move_type,
                "move_id": invoice_id.id,
                "payment_id": payment.id if payment else None,
                "aliquot": tax.amount,
                "iva_amount": tax_group["tax_amount"],
                "invoice_total": invoice_id.tax_totals["total_amount"],
                "related_percentage_tax_base": withholding_amount,
                "invoice_amount": tax_group["base_amount"],
            }
            if invoice_id.move_type == "out_invoice":
                line_data["retention_amount"] = 0.0
            else:
                line_data["retention_amount"] = retention_amount
            lines_data.append(line_data)
        return lines_data

    def get_signature(self):
        config = self.env["signature.config"].search(
            [("active", "=", True), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if config and config.signature:
            return config.signature.decode()
        else:
            return False

    @api.constrains("number", "type")
    def _check_number(self):
        for record in self:
            if (
                record.type == "out_invoice"
                and record.number
                and record.state != "draft"
            ):
                if not re.fullmatch(r"\d{14}", record.number):
                    raise ValidationError(
                        _("The number must be exactly 14 numeric digits.")
                    )
