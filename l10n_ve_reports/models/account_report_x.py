# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.tools.misc import format_date, format_datetime


class AccountVeReportXHandler(models.AbstractModel):
    _name = "account.ve.report_x.handler.oca"
    _inherit = "account.report.custom.handler.oca"
    _description = "Venezuela Reporte X (resumen consolidado)"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        options["unfold_all"] = options.get("unfold_all", True)

        if previous_options.get("is_opening_report"):
            today = fields.Date.context_today(report)
            date_opt = options.get("date")
            if not date_opt or date_opt.get("period_type") != "today":
                options["date"] = report._get_dates_period(
                    today, today, "single", period_type="today"
                )
            options["date"]["filter"] = "this_today"
            options["date"]["period"] = 0

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "ve_report_x",
        }

    def _daily(self):
        return self.env["account.daily.payments.report.handler.oca"]

    def _sales(self):
        return self.env["account.sales.book.report.handler.oca"]

    def _get_report_date_bounds(self, options):
        return self._daily()._get_report_date_bounds(options)

    def _amount_to_report_currency(self, amount_company, company, options, conv_date):
        return self._daily()._amount_to_report_currency(
            amount_company, company, options, conv_date
        )

    def _build_row_columns(self, report, options, values_map):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        line_columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            if label not in values_map:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )
                continue
            value = values_map[label]
            if column.get("figure_type") == "monetary":
                line_columns.append(
                    report._build_column_dict(
                        value,
                        column,
                        options=options,
                        currency=display_currency,
                    )
                )
            else:
                line_columns.append(
                    report._build_column_dict(value, column, options=options)
                )
        return line_columns

    def _tax_values_for_move(self, move):
        sales = self._sales()
        if hasattr(move, "sale_tax_data") and move.sale_tax_data:
            return sales._get_tax_values_from_stored(move)
        return sales._calculate_tax_values(move)

    def _aggregate_tax_maps(self, moves):
        keys = (
            "total_exempt",
            "base_general",
            "amount_general",
            "base_reduced",
            "amount_reduced",
            "base_extend",
            "amount_extend",
            "total_taxed",
        )
        acc = {k: 0.0 for k in keys}
        for move in moves:
            tv = self._tax_values_for_move(move)
            for k in keys:
                acc[k] += tv.get(k, 0.0)
        return acc

    def _invoice_domain_base(self, report, options, move_types):
        date_from, date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)
        domain = [
            ("move_type", "in", move_types),
            ("state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("company_id", "in", company_ids),
        ]
        journal_domain = report._get_options_journals_domain(options)
        if journal_domain:
            domain += journal_domain
        return domain

    def _move_type_in_selection(self, code):
        Move = self.env["account.move"]
        for key, _label in Move._fields["move_type"]._description_selection(Move.env):
            if key == code:
                return True
        return False

    def _search_sales_invoices_and_receipts(self, report, options):
        domain = self._invoice_domain_base(
            report, options, ("out_invoice", "out_receipt")
        )
        if "debit_origin_id" in self.env["account.move"]._fields:
            domain.append(("debit_origin_id", "=", False))
        return self.env["account.move"].search(domain, order="id asc")

    def _search_customer_debit_notes(self, report, options):
        date_from, date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)
        domain = [
            ("state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("company_id", "in", company_ids),
        ]
        journal_domain = report._get_options_journals_domain(options)
        if journal_domain:
            domain += journal_domain
        Move = self.env["account.move"]
        debit_notes = Move
        if self._move_type_in_selection("out_debit"):
            debit_notes = Move.search(
                domain + [("move_type", "=", "out_debit")], order="id asc"
            )
        if "debit_origin_id" in Move._fields:
            linked = Move.search(
                domain
                + [
                    ("move_type", "in", ("out_invoice", "out_receipt")),
                    ("debit_origin_id", "!=", False),
                ],
                order="id asc",
            )
            debit_notes |= linked
        return debit_notes

    def _cancel_move_types_customer(self):
        types = ["out_invoice", "out_refund", "out_receipt"]
        if self._move_type_in_selection("out_debit"):
            types.append("out_debit")
        return types

    def _discount_total_company(self, moves):
        total = 0.0
        for move in moves:
            company_currency = move.company_id.currency_id
            for line in move.invoice_line_ids:
                if line.display_type in ("line_section", "line_note"):
                    continue
                if not line.discount:
                    continue
                disc = line.discount
                if disc >= 100:
                    continue
                gross = line.price_subtotal / (1.0 - disc / 100.0)
                total += company_currency.round(gross - line.price_subtotal)
        return total

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        date_from, date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)
        if not company_ids:
            return []
        main_company = self.env["res.company"].browse(company_ids[0])
        gen_ts = format_datetime(
            self.env,
            fields.Datetime.now(),
            dt_format="dd/MM/yyyy HH:mm",
        )

        def add_row(name, detail, amount, level=1, line_class=None, markup="rx"):
            row_id = report._get_generic_line_id(
                None, None, markup=f"{markup}_{len(lines)}"
            )
            values_map = {
                "row_detail": detail or "",
                "row_amount": amount,
            }
            line = {
                "id": row_id,
                "name": name,
                "columns": self._build_row_columns(report, options, values_map),
                "level": level,
                "unfoldable": False,
            }
            if line_class:
                line["class"] = line_class
            lines.append((0, line))

        period_label = _("%(date_from)s — %(date_to)s") % {
            "date_from": format_date(self.env, date_from),
            "date_to": format_date(self.env, date_to),
        }
        add_row(_("Reporte X (resumen consolidado)"), period_label, None, level=0)
        add_row(_("Generado"), gen_ts, None, level=1)
        partner = main_company.partner_id
        if partner and partner.vat:
            add_row(_("RIF / identificación fiscal"), partner.vat, None, level=1)
        add_row(_("Usuario"), self.env.user.name, None, level=1)

        daily = self._daily()
        date_type = daily._get_daily_payments_date_type(options)
        bank_cash_journals = daily._get_selected_bank_cash_journals(report, options)
        add_row(
            _("Payments by type and payment method"),
            "",
            None,
            level=0,
            markup="rx_arc",
        )

        total_cash = 0.0
        total_ops = 0
        payment_groups = {
            "inbound": {
                "name": _("Incoming payments"),
                "methods": {},
                "amount": 0.0,
                "count": 0,
            },
            "outbound": {
                "name": _("Outgoing payments"),
                "methods": {},
                "amount": 0.0,
                "count": 0,
            },
        }
        for journal in bank_cash_journals.sorted(lambda j: (j.company_id.name, j.name)):
            posted = daily._get_posted_moves_by_date(
                journal, company_ids, date_from, date_to, date_type
            )
            registered = posted.filtered(
                lambda m, j=journal: daily._is_move_bank_liquidity_registered(m, j)
            )
            for move in registered:
                display_date = daily._get_move_display_date(move, date_type)
                amount = daily._get_move_display_report_amount(
                    move,
                    journal,
                    options,
                    display_date,
                )
                if daily._is_report_amount_zero(amount, options):
                    continue
                payment = daily._get_move_payment(move)
                payment_type = (
                    payment.payment_type
                    if payment
                    else "inbound"
                    if amount >= 0.0
                    else "outbound"
                )
                payment_method_line = daily._get_move_payment_method_line(move)
                payment_method_name = (
                    payment_method_line.name
                    if payment_method_line
                    else _("No payment method")
                )
                payment_method_label = _(
                    "%(method)s - %(journal)s",
                    method=payment_method_name,
                    journal=journal.display_name,
                )
                method_key = (
                    payment_method_name.strip().casefold(),
                    journal.id,
                )
                methods = payment_groups[payment_type]["methods"]
                if method_key not in methods:
                    methods[method_key] = {
                        "name": payment_method_label,
                        "amount": 0.0,
                        "count": 0,
                    }
                methods[method_key]["amount"] += amount
                methods[method_key]["count"] += 1
                payment_groups[payment_type]["amount"] += amount
                payment_groups[payment_type]["count"] += 1
                total_cash += amount
                total_ops += 1

        for payment_type in ("inbound", "outbound"):
            payment_group = payment_groups[payment_type]
            if not payment_group["count"]:
                continue
            add_row(
                payment_group["name"],
                _("%(n)s operations", n=payment_group["count"]),
                payment_group["amount"],
                level=1,
                line_class="total",
                markup="rx_payment_type_%s" % payment_type,
            )
            for method in sorted(
                payment_group["methods"].values(),
                key=lambda method: method["name"],
            ):
                add_row(
                    method["name"],
                    _("%(n)s operations", n=method["count"]),
                    method["amount"],
                    level=2,
                    markup="rx_payment_method_%s" % payment_type,
                )

        add_row(
            _("Total registered payments"),
            _("%(n)s operations", n=total_ops),
            total_cash,
            level=1,
            line_class="total",
        )

        refund_domain = self._invoice_domain_base(report, options, ("out_refund",))
        cancel_domain = [
            ("move_type", "in", tuple(self._cancel_move_types_customer())),
            ("state", "=", "cancel"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("company_id", "in", company_ids),
        ]
        journal_domain = report._get_options_journals_domain(options)
        if journal_domain:
            cancel_domain += journal_domain

        invoices = self._search_sales_invoices_and_receipts(report, options)
        debit_notes = self._search_customer_debit_notes(report, options)
        refunds = self.env["account.move"].search(refund_domain, order="id asc")
        cancelled = self.env["account.move"].search(cancel_domain)

        sale_agg = self._aggregate_tax_maps(invoices)
        debit_agg = self._aggregate_tax_maps(debit_notes)
        refund_agg = self._aggregate_tax_maps(refunds)

        add_row(_("Ventas del período"), "", None, level=0, markup="rx_vs")
        add_row(
            _("Exento / exonerado"),
            "",
            sale_agg["total_exempt"],
            level=1,
        )
        company = main_company
        TaxGroup = self.env["account.tax.group"]
        tax_config = TaxGroup._l10n_ve_build_tax_config(company)
        if "general" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "general", "sale"
            )
            add_row(
                _("Base imponible — alícuota general (%(p)s%%)", p=percent),
                "",
                sale_agg["base_general"],
                level=1,
            )
            add_row(
                _("IVA — general"),
                "",
                sale_agg["amount_general"],
                level=1,
            )
        else:
            add_row(_("Base imponible — alícuota general"), "", sale_agg["base_general"], level=1)
            add_row(_("IVA — general"), "", sale_agg["amount_general"], level=1)

        if "reduced" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "reduced", "sale"
            )
            add_row(
                _("Base imponible — alícuota reducida (%(p)s%%)", p=percent),
                "",
                sale_agg["base_reduced"],
                level=1,
            )
            add_row(
                _("IVA — reducida"),
                "",
                sale_agg["amount_reduced"],
                level=1,
            )
        else:
            add_row(_("Base imponible — reducida"), "", sale_agg["base_reduced"], level=1)
            add_row(_("IVA — reducida"), "", sale_agg["amount_reduced"], level=1)

        if "extend" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "extend", "sale"
            )
            add_row(
                _("Base imponible — alícuota adicional (%(p)s%%)", p=percent),
                "",
                sale_agg["base_extend"],
                level=1,
            )
            add_row(
                _("IVA — adicional"),
                "",
                sale_agg["amount_extend"],
                level=1,
            )
        else:
            add_row(_("Base imponible — adicional"), "", sale_agg["base_extend"], level=1)
            add_row(_("IVA — adicional"), "", sale_agg["amount_extend"], level=1)

        ttl_base_ventas = (
            sale_agg["total_exempt"]
            + sale_agg["base_general"]
            + sale_agg["base_reduced"]
            + sale_agg["base_extend"]
        )
        ttl_iva_ventas = (
            sale_agg["amount_general"]
            + sale_agg["amount_reduced"]
            + sale_agg["amount_extend"]
        )
        add_row(_("Total bases (ventas)"), "", ttl_base_ventas, level=1, line_class="total")
        add_row(_("Total IVA (ventas)"), "", ttl_iva_ventas, level=1, line_class="total")

        add_row(_("Notas de débito"), "", None, level=0, markup="rx_nd")
        add_row(
            _("Exento / exonerado (ND)"),
            "",
            debit_agg["total_exempt"],
            level=1,
        )
        if "general" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "general", "sale"
            )
            add_row(
                _("Base imponible — alícuota general (%(p)s%%) (ND)", p=percent),
                "",
                debit_agg["base_general"],
                level=1,
            )
            add_row(
                _("IVA — general (ND)"),
                "",
                debit_agg["amount_general"],
                level=1,
            )
        else:
            add_row(
                _("Base imponible — alícuota general (ND)"),
                "",
                debit_agg["base_general"],
                level=1,
            )
            add_row(_("IVA — general (ND)"), "", debit_agg["amount_general"], level=1)

        if "reduced" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "reduced", "sale"
            )
            add_row(
                _("Base imponible — alícuota reducida (%(p)s%%) (ND)", p=percent),
                "",
                debit_agg["base_reduced"],
                level=1,
            )
            add_row(
                _("IVA — reducida (ND)"),
                "",
                debit_agg["amount_reduced"],
                level=1,
            )
        else:
            add_row(
                _("Base imponible — reducida (ND)"),
                "",
                debit_agg["base_reduced"],
                level=1,
            )
            add_row(_("IVA — reducida (ND)"), "", debit_agg["amount_reduced"], level=1)

        if "extend" in tax_config:
            percent = TaxGroup._l10n_ve_get_tax_rate_for_type(
                company, "extend", "sale"
            )
            add_row(
                _("Base imponible — alícuota adicional (%(p)s%%) (ND)", p=percent),
                "",
                debit_agg["base_extend"],
                level=1,
            )
            add_row(
                _("IVA — adicional (ND)"),
                "",
                debit_agg["amount_extend"],
                level=1,
            )
        else:
            add_row(
                _("Base imponible — adicional (ND)"),
                "",
                debit_agg["base_extend"],
                level=1,
            )
            add_row(_("IVA — adicional (ND)"), "", debit_agg["amount_extend"], level=1)

        ttl_base_nd = (
            debit_agg["total_exempt"]
            + debit_agg["base_general"]
            + debit_agg["base_reduced"]
            + debit_agg["base_extend"]
        )
        ttl_iva_nd = (
            debit_agg["amount_general"]
            + debit_agg["amount_reduced"]
            + debit_agg["amount_extend"]
        )
        add_row(_("Total bases (ND)"), "", ttl_base_nd, level=1, line_class="total")
        add_row(_("Total IVA (ND)"), "", ttl_iva_nd, level=1, line_class="total")

        add_row(_("Notas de crédito / devoluciones"), "", None, level=0, markup="rx_nc")
        add_row(_("Exento (NC)"), "", abs(refund_agg["total_exempt"]), level=1)
        add_row(_("Base imponible — general (NC)"), "", abs(refund_agg["base_general"]), level=1)
        add_row(_("IVA — general (NC)"), "", abs(refund_agg["amount_general"]), level=1)
        add_row(_("Base imponible — reducida (NC)"), "", abs(refund_agg["base_reduced"]), level=1)
        add_row(_("IVA — reducida (NC)"), "", abs(refund_agg["amount_reduced"]), level=1)
        add_row(_("Base imponible — adicional (NC)"), "", abs(refund_agg["base_extend"]), level=1)
        add_row(_("IVA — adicional (NC)"), "", abs(refund_agg["amount_extend"]), level=1)
        ttl_base_nc = (
            abs(refund_agg["total_exempt"])
            + abs(refund_agg["base_general"])
            + abs(refund_agg["base_reduced"])
            + abs(refund_agg["base_extend"])
        )
        ttl_iva_nc = (
            abs(refund_agg["amount_general"])
            + abs(refund_agg["amount_reduced"])
            + abs(refund_agg["amount_extend"])
        )
        add_row(_("Total bases (NC)"), "", ttl_base_nc, level=1, line_class="total")
        add_row(_("Total IVA (NC)"), "", ttl_iva_nc, level=1, line_class="total")

        disc = self._discount_total_company(invoices | debit_notes)
        add_row(_("Descuentos (estimado en líneas de factura)"), "", disc, level=0)

        add_row(_("Anulaciones (documentos cancelados en el período)"), "", None, level=0)
        add_row(
            _("Documentos cancelados"),
            _("%(n)s documentos", n=len(cancelled)),
            sum(cancelled.mapped("amount_total_signed")),
            level=1,
        )

        add_row(_("Documentos emitidos (referencia Odoo)"), "", None, level=0)
        if invoices:
            last_inv = max(invoices, key=lambda m: (m.invoice_date or m.date, m.id))
            add_row(
                _("Última factura / recibo"),
                last_inv.name or "",
                None,
                level=1,
            )
        add_row(
            _("Cantidad facturas y recibos"),
            "",
            len(invoices),
            level=1,
        )
        if debit_notes:
            last_nd = max(
                debit_notes, key=lambda m: (m.invoice_date or m.date, m.id)
            )
            add_row(
                _("Última nota de débito"),
                last_nd.name or "",
                None,
                level=1,
            )
        add_row(
            _("Cantidad notas de débito"),
            "",
            len(debit_notes),
            level=1,
        )
        if refunds:
            last_nc = max(refunds, key=lambda m: (m.invoice_date or m.date, m.id))
            add_row(
                _("Última nota de crédito"),
                last_nc.name or "",
                None,
                level=1,
            )
        add_row(
            _("Cantidad notas de crédito"),
            "",
            len(refunds),
            level=1,
        )

        if hasattr(self.env["account.move"], "l10n_ve_control_number"):
            fiscal_docs = invoices | debit_notes
            with_control = fiscal_docs.filtered(
                lambda m: (m.l10n_ve_control_number or "").strip()
                and m.l10n_ve_control_number != "/"
            )
            without_control = fiscal_docs - with_control
            add_row(
                _("Documentos de venta con n° de control"),
                "",
                len(with_control),
                level=1,
            )
            add_row(
                _("Documentos sin n° de control (no fiscal)"),
                "",
                len(without_control),
                level=1,
            )

        return lines
