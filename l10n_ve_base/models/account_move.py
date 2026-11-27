# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    nro_ctrl = fields.Char(
        string="Control Number",
        copy=False,
        tracking=True,
        help="Pre-printed invoice control number required by SENIAT",
    )
    sin_cred = fields.Boolean(
        string="Exclude from Fiscal Book",
        copy=False,
        help="Set to true if invoice is exempt or excluded from Venezuelan fiscal book",
    )
    date_document = fields.Date(
        string="Document Date",
        copy=False,
        help="Administrative date printed on the physical vendor bill for fiscal books",
    )
    invoice_printer = fields.Char(
        string="Fiscal Printer Invoice Number",
        copy=False,
        help="Invoice number emitted by the fiscal printer",
    )
    fiscal_printer = fields.Char(
        string="Fiscal Printer Serial",
        copy=False,
        help="Serial number of the fiscal printer",
    )
    z_report = fields.Char(
        string="Report Z",
        copy=False,
        help="Z Report number emitted by fiscal printer",
    )
    supplier_invoice_number = fields.Char(
        copy=False,
        help="Original invoice number from supplier",
    )

    @api.constrains("nro_ctrl", "partner_id", "move_type", "company_id")
    def _check_unique_nro_ctrl(self):
        for move in self:
            if not (move.is_invoice() and move.nro_ctrl):
                continue
            nro = move.nro_ctrl.strip()
            domain = [
                ("id", "!=", move.id),
                ("company_id", "=", move.company_id.id),
                ("nro_ctrl", "=", nro),
                ("state", "!=", "cancel"),
            ]
            # One control number series covers invoices, credit and debit
            # notes of the issuer: the company for sales, each supplier
            # for purchases.
            if move.is_sale_document(include_receipts=True):
                domain.append(
                    ("move_type", "in", self.get_sale_types(include_receipts=True))
                )
            else:
                domain += [
                    (
                        "move_type",
                        "in",
                        self.get_purchase_types(include_receipts=True),
                    ),
                    # Core books payables and payments on the commercial
                    # partner; the invoice contact is billing data only, so
                    # contacts of one supplier are the same issuer.
                    (
                        "commercial_partner_id",
                        "=",
                        move.commercial_partner_id.id,
                    ),
                ]
            if self.search_count(domain):
                raise ValidationError(
                    self.env._(
                        "The Control Number %s has already been "
                        "registered for this company.",
                        nro,
                    )
                )

    @api.onchange("invoice_date")
    def _onchange_invoice_date_ve(self):
        if self.invoice_date and not self.date_document:
            self.date_document = self.invoice_date

    def _l10n_ve_is_fiscal_invoice(self):
        self.ensure_one()
        return self.is_invoice(include_receipts=True)

    def _l10n_ve_taxable_untaxed(self):
        """Untaxed amount excluding IGTF expense lines on vendor bills."""
        self.ensure_one()
        extra = sum(
            self.invoice_line_ids.filtered(
                lambda line: getattr(line, "l10n_ve_igtf_line", False)
            ).mapped("price_subtotal")
        )
        return self.amount_untaxed - extra

    def _l10n_ve_validate_invoice(self):
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        company_ve = self.company_id.account_fiscal_country_id.code == "VE" or (
            self.company_id.country_id and self.company_id.country_id.code == "VE"
        )
        partner_ve = partner.country_id and partner.country_id.code == "VE"
        if company_ve or partner_ve:
            if not partner.vat:
                raise UserError(
                    self.env._(
                        "Partner %s needs a RIF before posting "
                        "a Venezuelan fiscal invoice.",
                        partner.display_name,
                    )
                )
            if not partner._l10n_ve_is_valid_fiscal_id(partner.vat):
                raise UserError(
                    self.env._(
                        "The identification of %s is not valid "
                        "for a Venezuelan fiscal invoice.",
                        partner.display_name,
                    )
                )
        if abs(self.amount_total) < 0.01:
            raise UserError(
                self.env._(
                    "Invoice %s cannot be posted with a total of zero.",
                    self.display_name,
                )
            )
        if (
            self.invoice_date
            and self.invoice_date_due
            and self.invoice_date_due < self.invoice_date
        ):
            raise UserError(
                self.env._(
                    "The due date of %s cannot be earlier than the invoice date.",
                    self.display_name,
                )
            )
        if self.move_type in ("out_refund", "in_refund") and not self.reversed_entry_id:
            raise UserError(
                self.env._(
                    "Credit note %s must be linked to the original "
                    "invoice (reversed entry).",
                    self.display_name,
                )
            )
        for line in self.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        ):
            if line.quantity < 0 or line.price_unit < 0:
                raise UserError(
                    self.env._(
                        "Invoice lines cannot have a negative quantity "
                        "or unit price (%s).",
                        line.display_name,
                    )
                )
            if len(line.tax_ids) > 1:
                raise UserError(
                    self.env._(
                        "Line '%s' cannot have more than one tax. "
                        "Split it into separate lines.",
                        line.name or line.display_name,
                    )
                )

    def _post(self, soft=True):
        for move in self:
            if not move._l10n_ve_is_fiscal_invoice():
                continue
            move._l10n_ve_validate_invoice()
            if not move.date_document:
                move.date_document = move.invoice_date or fields.Date.context_today(
                    self
                )
            if (
                move.move_type in ("in_invoice", "in_refund")
                and not (move.nro_ctrl or "").strip()
            ):
                raise UserError(
                    self.env._(
                        "Vendor bill %s requires a Control Number "
                        "(nro. de control) before posting.",
                        move.display_name,
                    )
                )
        return super()._post(soft=soft)

    def write(self, vals):
        locked_fields = {"nro_ctrl", "date_document", "supplier_invoice_number"}
        if locked_fields & set(vals) and not self.env.context.get(
            "l10n_ve_allow_nro_ctrl"
        ):
            posted = self.filtered(
                lambda move: move.state == "posted"
                and move._l10n_ve_is_fiscal_invoice()
            )
            if posted:
                raise UserError(
                    self.env._(
                        "Fiscal identification fields cannot be changed "
                        "on posted invoices. Use a credit/debit note or "
                        "the control-number wizard on empty values."
                    )
                )
        return super().write(vals)
