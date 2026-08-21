# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action


class DailyPaymentsReportCustomHandler(models.AbstractModel):
    _name = "account.daily.payments.report.handler.oca"
    _inherit = "account.report.custom.handler.oca"
    _description = "Daily Payments by Journal Report Custom Handler"

    def _get_current_week_monday_friday(self, reference_date):
        monday = reference_date - timedelta(days=reference_date.weekday())
        friday = monday + timedelta(days=4)
        return monday, friday

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        report._init_options_journals(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", ("bank", "cash"))],
        )
        report._init_options_journals_names(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", ("bank", "cash"))],
        )
        options["unfold_all"] = options.get("unfold_all", True)
        options["daily_payments_date_type"] = previous_options.get(
            "daily_payments_date_type", "validation"
        )

        if previous_options.get("is_opening_report"):
            today = fields.Date.context_today(report)
            date_from, date_to = self._get_current_week_monday_friday(today)
            options["date"] = report._get_dates_period(
                date_from, date_to, "range", period_type="custom"
            )
            options["date"]["filter"] = "custom"
            options["date"]["period"] = 0

        self._update_line_date_column_label(options)

    def _get_line_date_column_name(self, date_type):
        if date_type == "payment":
            return _("Fecha del pago")
        return _("Fecha de validación")

    def _update_line_date_column_label(self, options):
        column_name = self._get_line_date_column_name(
            self._get_daily_payments_date_type(options)
        )
        for column in options.get("columns", []):
            if column.get("expression_label") == "line_date":
                column["name"] = column_name

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "daily_payments_report",
            "templates": {
                "AccountReportFilters": (
                    "l10n_ve_reports.DailyPaymentsReportFiltersCustomizable"
                ),
            },
        }

    def export_to_pdf(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        return type(report).export_to_pdf(
            report.with_context(force_landscape_printing=True), options
        )

    def _get_daily_payments_date_type(self, options):
        date_type = options.get("daily_payments_date_type", "validation")
        if date_type not in ("payment", "validation"):
            return "validation"
        return date_type

    def _get_move_display_report_amount(self, move, journal, options, conv_date):
        balance = self._get_move_report_amount(move, journal)
        return self._amount_to_report_currency(
            balance,
            move.company_id,
            options,
            conv_date,
        )

    def _get_move_pending_report_amount(self, move, journal, options, conv_date):
        bal = self._get_move_outstanding_balance_company(move, journal)
        if journal.company_id.currency_id.is_zero(bal):
            bal = self._get_move_report_amount(move, journal)
        return self._amount_to_report_currency(
            bal,
            journal.company_id,
            options,
            conv_date,
        )

    def _get_move_payment(self, move):
        payment = move.origin_payment_id
        if not payment:
            st_line = self.env["account.bank.statement.line"].search(
                [("move_id", "=", move.id)], limit=1
            )
            if st_line and st_line.payment_ids:
                return st_line.payment_ids[:1]
        if not payment:
            payment = self.env["account.payment"].search(
                [("move_id", "=", move.id)], limit=1
            )
        return payment

    def _get_move_payment_date(self, move):
        payment = self._get_move_payment(move)
        if payment:
            return payment.date
        return move.date

    def _get_move_validation_date(self, move):
        if move.l10n_ve_process_date:
            return move.l10n_ve_process_date
        payment = self._get_move_payment(move)
        if payment and payment.l10n_ve_process_date:
            return payment.l10n_ve_process_date
        return move.date

    def _get_move_filter_date(self, move, date_type):
        if date_type == "payment":
            return self._get_move_payment_date(move)
        return self._get_move_validation_date(move)

    def _get_move_display_date(self, move, date_type="validation"):
        return self._get_move_filter_date(move, date_type)

    def _get_aml_filter_date(self, aml, date_type):
        if date_type == "payment":
            return self._get_move_payment_date(aml.move_id)
        return self._get_move_validation_date(aml.move_id)

    def _get_aml_display_date(self, aml, date_type="validation"):
        return self._get_aml_filter_date(aml, date_type)

    def _move_in_date_range(self, move, date_from, date_to, date_type):
        filter_date = self._get_move_filter_date(move, date_type)
        return date_from <= filter_date <= date_to

    def _aml_in_date_range(self, aml, date_from, date_to, date_type):
        filter_date = self._get_aml_filter_date(aml, date_type)
        return date_from <= filter_date <= date_to

    def _amount_to_report_currency(self, amount_company, company, options, conv_date):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        company_currency = company.currency_id
        if not amount_company or display_currency == company_currency:
            return amount_company
        if not conv_date:
            conv_date = options["date"]["date_to"]
        return company_currency._convert(
            amount_company,
            display_currency,
            company,
            conv_date,
        )

    def _get_journal_liquidity_accounts(self, journal):
        accounts = self.env["account.account"]
        if journal.default_account_id:
            accounts |= journal.default_account_id
        accounts |= journal._get_journal_inbound_outstanding_payment_accounts()
        accounts |= journal._get_journal_outbound_outstanding_payment_accounts()
        return accounts

    def _get_move_liquidity_balance(self, move, journal):
        accounts = self._get_journal_liquidity_accounts(journal)
        if not accounts:
            return 0.0
        liquidity_lines = move.line_ids.filtered(
            lambda line, accs=accounts: line.account_id in accs
        )
        return sum(liquidity_lines.mapped("balance"))

    def _get_move_report_amount(self, move, journal):
        company_currency = journal.company_id.currency_id
        balance = self._get_move_liquidity_balance(move, journal)
        if not company_currency.is_zero(balance):
            return balance
        st_line = self.env["account.bank.statement.line"].search(
            [("move_id", "=", move.id)], limit=1
        )
        if st_line and not company_currency.is_zero(st_line.amount):
            st_currency = st_line.foreign_currency_id or journal.currency_id
            if st_currency and st_currency != company_currency:
                return st_currency._convert(
                    st_line.amount,
                    company_currency,
                    journal.company_id,
                    st_line.date,
                )
            return st_line.amount
        payment = self._get_move_payment(move)
        if payment and not company_currency.is_zero(payment.amount):
            signed_amount = abs(payment.amount)
            if payment.payment_type == "outbound":
                signed_amount = -signed_amount
            pay_currency = payment.currency_id
            if pay_currency != company_currency:
                return pay_currency._convert(
                    signed_amount,
                    company_currency,
                    journal.company_id,
                    payment.date,
                )
            return signed_amount
        return balance

    def _is_report_amount_zero(self, amount, options):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        return display_currency.is_zero(amount)

    def _is_move_bank_liquidity_registered(self, move, journal):
        company_currency = journal.company_id.currency_id
        if journal.default_account_id:
            liquidity_lines = move.line_ids.filtered(
                lambda line, acc=journal.default_account_id: line.account_id == acc
            )
            if liquidity_lines and not company_currency.is_zero(
                sum(liquidity_lines.mapped("balance"))
            ):
                return True
        if journal.type == "cash":
            return not company_currency.is_zero(
                self._get_move_report_amount(move, journal)
            )
        return False

    def _get_move_outstanding_balance_company(self, move, journal):
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return 0.0
        lines = move.line_ids.filtered(lambda line: line.account_id in accounts)
        return sum(lines.mapped("balance"))

    def _caret_options_initializer(self):
        base = self.env["account.report"]._caret_options_initializer_default()
        extra = {
            "name": _("Facturas relacionadas"),
            "action": "caret_option_daily_payments_open_invoices",
        }
        return {
            **base,
            "account.move": list(base.get("account.move", [])) + [extra],
            "account.move.line": list(base.get("account.move.line", [])) + [extra],
        }

    def caret_option_daily_payments_open_invoices(self, options, action_param):
        params = action_param or {}
        line_id = params.get("line_id")
        if not line_id:
            raise UserError(_("Línea inválida."))
        move = self._daily_payments_get_move_from_line_id(line_id)
        if not move:
            raise UserError(_("No se encontró un asiento asociado."))
        invoices = self._get_invoice_moves_for_daily_payment_line(move)
        if not invoices:
            raise UserError(_("No hay facturas vinculadas a este movimiento."))
        action = {
            "type": "ir.actions.act_window",
            "name": _("Facturas"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", invoices.ids)],
            "context": {**self.env.context, "create": False},
        }
        return clean_action(action, self.env)

    def _daily_payments_get_move_from_line_id(self, line_id):
        report = self.env["account.report"]
        for _markup, model, res_id in report._parse_line_id(line_id):
            if model == "account.move" and res_id:
                return self.env["account.move"].browse(res_id)
            if model == "account.move.line" and res_id:
                return self.env["account.move.line"].browse(res_id).move_id
        return self.env["account.move"]

    def _get_invoice_moves_from_reconciliation(self, move):
        move = move[:1]
        if not move:
            return self.env["account.move"]
        invoice_types = (
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
            "out_receipt",
            "in_receipt",
        )
        seen = set()
        invoices = self.env["account.move"]
        for line in move.line_ids:
            for other in line._all_reconciled_lines():
                cm = other.move_id
                if (
                    cm.id != move.id
                    and cm.move_type in invoice_types
                    and cm.id not in seen
                ):
                    seen.add(cm.id)
                    invoices |= cm
        return invoices

    def _get_payments_linked_to_statement_line(self, st_line):
        payments = st_line.payment_ids
        if payments:
            return payments
        self.env["account.payment"].flush_model(["move_id", "outstanding_account_id"])
        self.env["account.move.line"].flush_model(
            ["move_id", "account_id", "statement_line_id"]
        )
        self.env["account.partial.reconcile"].flush_model(
            ["debit_move_id", "credit_move_id"]
        )
        self.env.cr.execute(
            """
            SELECT DISTINCT payment.id
            FROM account_payment payment
            JOIN account_move am ON am.id = payment.move_id
            JOIN account_move_line line ON line.move_id = am.id
            JOIN account_partial_reconcile part ON
                part.debit_move_id = line.id OR part.credit_move_id = line.id
            JOIN account_move_line counterpart ON
                part.debit_move_id = counterpart.id OR part.credit_move_id = counterpart.id
            WHERE payment.outstanding_account_id IS NOT NULL
              AND line.account_id = payment.outstanding_account_id
              AND line.id != counterpart.id
              AND counterpart.statement_line_id = %s
            """,
            (st_line.id,),
        )
        return self.env["account.payment"].browse(id for id, in self.env.cr.fetchall())

    def _get_invoice_moves_for_daily_payment_line(self, move):
        move = move[:1]
        if not move:
            return self.env["account.move"]
        st_line = self.env["account.bank.statement.line"].search(
            [("move_id", "=", move.id)], limit=1
        )
        if st_line:
            payments = self._get_payments_linked_to_statement_line(st_line)
            if payments:
                invoices = self.env["account.move"]
                for pay in payments:
                    invoices |= (
                        pay.invoice_ids
                        | pay.reconciled_invoice_ids
                        | pay.reconciled_bill_ids
                    )
                if invoices:
                    return invoices
        from_reco = self._get_invoice_moves_from_reconciliation(move)
        if from_reco:
            return from_reco
        if st_line:
            return self.env["account.move"]
        payment = self.env["account.payment"].search(
            [("move_id", "=", move.id)], limit=1
        )
        if payment:
            return (
                payment.invoice_ids
                | payment.reconciled_invoice_ids
                | payment.reconciled_bill_ids
            )
        return self.env["account.move"]

    def _format_invoice_documents_label(self, move):
        invoices = self._get_invoice_moves_for_daily_payment_line(move)
        if not invoices:
            return ""
        names = []
        for inv in invoices.sorted(lambda r: (r.name or "", r.id)):
            names.append(inv.name or inv.display_name or "")
        return ", ".join(n for n in names if n)

    def _bank_move_has_pending_bridge_residual(self, move, journal):
        if journal.type != "bank":
            return True
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return False
        lines = move.line_ids.filtered(lambda line: line.account_id in accounts)
        company_currency = journal.company_id.currency_id
        for line in lines:
            if not company_currency.is_zero(line.amount_residual):
                return True
            if not company_currency.is_zero(line.amount_residual_currency):
                return True
        return False

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

    def _to_report_date(self, value):
        if not value:
            return False
        if isinstance(value, str):
            return fields.Date.from_string(value)
        return value

    def _get_report_date_bounds(self, options):
        date_info = options["date"]
        date_to = self._to_report_date(date_info["date_to"])
        if date_info.get("mode") == "single":
            if date_info.get("period_type") == "today":
                return date_to, date_to
            date_from = self._to_report_date(date_info.get("date_from"))
            if date_from:
                return date_from, date_to
            return date_to, date_to
        date_from = self._to_report_date(date_info.get("date_from"))
        if not date_from:
            return date_to, date_to
        return date_from, date_to

    def _get_selected_bank_cash_journals(self, report, options):
        selected = report._get_options_journals(options)
        journal_ids = [j["id"] for j in selected]
        journals = self.env["account.journal"].browse(journal_ids)
        journals = journals.filtered(lambda j: j.type in ("bank", "cash"))

        companies = journals.company_id
        retention_journal_ids = set(
            companies.mapped("iva_supplier_retention_journal_id").ids
            + companies.mapped("iva_customer_retention_journal_id").ids
            + companies.mapped("islr_supplier_retention_journal_id").ids
            + companies.mapped("islr_customer_retention_journal_id").ids
            + companies.mapped("municipal_supplier_retention_journal_id").ids
            + companies.mapped("municipal_customer_retention_journal_id").ids
        )
        if not retention_journal_ids:
            return journals
        return journals.filtered(lambda journal: journal.id not in retention_journal_ids)

    def _filter_moves_by_date_type(self, moves, date_from, date_to, date_type):
        return moves.filtered(
            lambda move, df=date_from, dt=date_to, dtp=date_type: self._move_in_date_range(
                move, df, dt, dtp
            )
        )

    def _get_posted_moves_by_date(
        self, journal, company_ids, date_from, date_to, date_type
    ):
        moves = self.env["account.move"].search(
            [
                ("journal_id", "=", journal.id),
                ("company_id", "in", company_ids),
                ("state", "=", "posted"),
            ],
            order="date asc, name asc",
        )
        moves = self._filter_moves_by_date_type(moves, date_from, date_to, date_type)
        return moves.sorted(
            lambda m, dtp=date_type: (
                self._get_move_display_date(m, dtp),
                m.name or "",
                m.id,
            )
        )

    def _get_draft_moves(self, journal, company_ids, date_from, date_to, date_type):
        moves = self.env["account.move"].search(
            [
                ("journal_id", "=", journal.id),
                ("company_id", "in", company_ids),
                ("state", "=", "draft"),
            ],
            order="date asc, name asc",
        )
        return self._filter_moves_by_date_type(moves, date_from, date_to, date_type)

    def _get_outstanding_amls(
        self, journal, company_ids, date_from, date_to, exclude_move_ids, date_type
    ):
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return self.env["account.move.line"]
        domain = [
            ("journal_id", "=", journal.id),
            ("company_id", "in", company_ids),
            ("account_id", "in", accounts.ids),
            ("parent_state", "=", "posted"),
            ("full_reconcile_id", "=", False),
            "|",
            ("amount_residual", "!=", 0.0),
            ("amount_residual_currency", "!=", 0.0),
        ]
        amls = self.env["account.move.line"].search(domain, order="date asc, id asc")
        amls = amls.filtered(
            lambda line, df=date_from, dt=date_to, dtp=date_type: self._aml_in_date_range(
                line, df, dt, dtp
            )
        )
        if not exclude_move_ids:
            return amls
        exclude = set(exclude_move_ids)
        return amls.filtered(lambda line: line.move_id.id not in exclude)

    def _get_move_payment_method_line(self, move):
        payment = self._get_move_payment(move)
        if payment:
            return payment.payment_method_line_id
        return self.env["account.payment.method.line"]

    def _get_aml_payment_method_line(self, aml):
        if aml.payment_id:
            return aml.payment_id.payment_method_line_id
        return self._get_move_payment_method_line(aml.move_id)

    def _get_payment_method_group_key(self, payment_method_line):
        if payment_method_line:
            return ("account.payment.method.line", payment_method_line.id)
        return (False, False)

    def _get_payment_method_group_name(self, payment_method_line):
        if payment_method_line:
            return payment_method_line.name
        return _("Sin método de pago")

    def _get_payment_method_group_line_id(self, report, journal, payment_method_line):
        if payment_method_line:
            return report._get_generic_line_id(
                "account.payment.method.line",
                payment_method_line.id,
                markup="daily_pay_payment_method",
            )
        return report._get_generic_line_id(
            "account.journal",
            journal.id,
            markup="daily_pay_payment_method_none",
        )

    def _build_amount_total_columns(self, report, options, amounts_by_column_group):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            col_group_key = column["column_group_key"]
            if label == "amount":
                columns.append(
                    report._build_column_dict(
                        amounts_by_column_group[col_group_key],
                        column,
                        options=options,
                        currency=display_currency,
                    )
                )
            else:
                columns.append(report._build_column_dict(None, column, options=options))
        return columns

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        date_from, date_to = self._get_report_date_bounds(options)
        date_type = self._get_daily_payments_date_type(options)
        company_ids = report.get_report_company_ids(options)

        journals = self._get_selected_bank_cash_journals(report, options)
        journals = journals.sorted(lambda j: (j.company_id.name, j.name))

        totals_by_group = defaultdict(float)

        for journal in journals:
            journal_group_totals = defaultdict(float)
            method_groups = {}
            journal_currency = journal.currency_id or journal.company_id.currency_id
            journal_title = _("%(journal)s — %(label)s: %(currency)s") % {
                "journal": journal.display_name,
                "label": _("Moneda del diario"),
                "currency": journal_currency.name,
            }

            def _get_method_group(payment_method_line):
                key = self._get_payment_method_group_key(payment_method_line)
                if key not in method_groups:
                    method_groups[key] = {
                        "payment_method_line": payment_method_line,
                        "name": self._get_payment_method_group_name(
                            payment_method_line
                        ),
                        "registered_lines": [],
                        "pending_lines": [],
                        "totals": defaultdict(float),
                    }
                return method_groups[key]

            def _add_amount_to_totals(method_group, amount):
                for col_group_key in options["column_groups"]:
                    totals_by_group[col_group_key] += amount
                    journal_group_totals[col_group_key] += amount
                    method_group["totals"][col_group_key] += amount

            posted_moves = self._get_posted_moves_by_date(
                journal, company_ids, date_from, date_to, date_type
            )
            registered_moves = posted_moves.filtered(
                lambda m, j=journal: self._is_move_bank_liquidity_registered(m, j)
            )
            pending_posted_bank_moves = (
                posted_moves - registered_moves
            ).filtered(
                lambda m, j=journal: self._bank_move_has_pending_bridge_residual(
                    m, j
                )
            )
            moves_by_date = defaultdict(list)
            for move in registered_moves:
                moves_by_date[self._get_move_display_date(move, date_type)].append(
                    move
                )

            for move_date in sorted(moves_by_date.keys()):
                for move in moves_by_date[move_date]:
                    display_date = self._get_move_display_date(move, date_type)
                    amt = self._get_move_display_report_amount(
                        move, journal, options, display_date
                    )
                    if self._is_report_amount_zero(amt, options):
                        continue
                    method_group = _get_method_group(
                        self._get_move_payment_method_line(move)
                    )
                    _add_amount_to_totals(method_group, amt)
                    partner_label = move.partner_id.display_name if move.partner_id else ""
                    method_group["registered_lines"].append(
                        (
                            0,
                            {
                                "id": report._get_generic_line_id(
                                    "account.move",
                                    move.id,
                                    markup="daily_pay_posted",
                                ),
                                "name": move.name or move.display_name,
                                "columns": self._build_row_columns(
                                    report,
                                    options,
                                    {
                                        "line_date": display_date,
                                        "invoice_documents": self._format_invoice_documents_label(
                                            move
                                        ),
                                        "partner": partner_label,
                                        "amount": amt,
                                    },
                                ),
                                "level": 3,
                                "unfoldable": False,
                                "caret_options": "account.move",
                            },
                        )
                    )

            draft_moves = self._get_draft_moves(
                journal, company_ids, date_from, date_to, date_type
            )
            exclude_move_ids_for_outstanding = (
                registered_moves.ids + pending_posted_bank_moves.ids
            )
            outstanding_amls = self._get_outstanding_amls(
                journal,
                company_ids,
                date_from,
                date_to,
                exclude_move_ids_for_outstanding,
                date_type,
            )

            for move in draft_moves:
                display_date = self._get_move_display_date(move, date_type)
                amt = self._get_move_display_report_amount(
                    move, journal, options, display_date
                )
                if self._is_report_amount_zero(amt, options):
                    continue
                method_group = _get_method_group(
                    self._get_move_payment_method_line(move)
                )
                _add_amount_to_totals(method_group, amt)
                partner_label = (
                    move.partner_id.display_name if move.partner_id else ""
                )
                method_group["pending_lines"].append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.move",
                                move.id,
                                markup="daily_pay_draft",
                            ),
                            "name": move.name or _("Borrador"),
                            "columns": self._build_row_columns(
                                report,
                                options,
                                {
                                    "line_date": display_date,
                                    "invoice_documents": self._format_invoice_documents_label(
                                        move
                                    ),
                                    "partner": partner_label,
                                    "amount": amt,
                                },
                            ),
                            "level": 3,
                            "unfoldable": False,
                            "caret_options": "account.move",
                        },
                    )
                )

            for move in pending_posted_bank_moves.sorted(
                lambda m, dtp=date_type: (
                    self._get_move_display_date(m, dtp),
                    m.name or "",
                )
            ):
                display_date = self._get_move_display_date(move, date_type)
                amt = self._get_move_pending_report_amount(
                    move, journal, options, display_date
                )
                if self._is_report_amount_zero(amt, options):
                    continue
                method_group = _get_method_group(
                    self._get_move_payment_method_line(move)
                )
                _add_amount_to_totals(method_group, amt)
                partner_label = move.partner_id.display_name if move.partner_id else ""
                method_group["pending_lines"].append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.move",
                                move.id,
                                markup="daily_pay_bank_pending",
                            ),
                            "name": move.name or move.display_name,
                            "columns": self._build_row_columns(
                                report,
                                options,
                                {
                                    "line_date": display_date,
                                    "invoice_documents": self._format_invoice_documents_label(
                                        move
                                    ),
                                    "partner": partner_label,
                                    "amount": amt,
                                },
                            ),
                            "level": 3,
                            "unfoldable": False,
                            "caret_options": "account.move",
                        },
                    )
                )

            for aml in outstanding_amls:
                display_date = self._get_aml_display_date(aml, date_type)
                amt = self._amount_to_report_currency(
                    aml.amount_residual,
                    journal.company_id,
                    options,
                    display_date,
                )
                if self._is_report_amount_zero(amt, options):
                    continue
                method_group = _get_method_group(self._get_aml_payment_method_line(aml))
                _add_amount_to_totals(method_group, amt)
                move = aml.move_id
                partner_label = aml.partner_id.display_name if aml.partner_id else ""
                short_name = (move.name if move else None) or aml.move_name or _(
                    "Línea pendiente"
                )
                method_group["pending_lines"].append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.move.line",
                                aml.id,
                                markup="daily_pay_outstanding",
                            ),
                            "name": short_name,
                            "columns": self._build_row_columns(
                                report,
                                options,
                                {
                                    "line_date": display_date,
                                    "invoice_documents": self._format_invoice_documents_label(
                                        aml.move_id
                                    ),
                                    "partner": partner_label,
                                    "amount": amt,
                                },
                            ),
                            "level": 3,
                            "unfoldable": False,
                            "caret_options": "account.move.line",
                        },
                    )
                )

            if not method_groups:
                continue

            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="daily_pay_journal_header",
                        ),
                        "name": journal_title,
                        "columns": self._build_row_columns(report, options, {}),
                        "level": 0,
                        "unfoldable": False,
                    },
                )
            )

            sorted_method_groups = sorted(
                method_groups.values(), key=lambda group: group["name"]
            )
            for method_group in sorted_method_groups:
                payment_method_line = method_group["payment_method_line"]
                method_line_id = self._get_payment_method_group_line_id(
                    report, journal, payment_method_line
                )
                lines.append(
                    (
                        0,
                        {
                            "id": method_line_id,
                            "name": method_group["name"],
                            "columns": self._build_amount_total_columns(
                                report,
                                options,
                                method_group["totals"],
                            ),
                            "level": 1,
                            "unfoldable": True,
                            "unfolded": (
                                method_line_id in options["unfolded_lines"]
                                or options["unfold_all"]
                            ),
                        },
                    )
                )
                method_markup = (
                    payment_method_line.id if payment_method_line else "none"
                )
                if method_group["registered_lines"]:
                    registered_section_id = report._get_generic_line_id(
                        "account.journal",
                        journal.id,
                        parent_line_id=method_line_id,
                        markup="daily_pay_section_done_%s" % method_markup,
                    )
                    lines.append(
                        (
                            0,
                            {
                                "id": registered_section_id,
                                "name": _("Pagos y cobros registrados"),
                                "columns": self._build_row_columns(
                                    report, options, {}
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "parent_id": method_line_id,
                            },
                        )
                    )
                    for _sequence, line in method_group["registered_lines"]:
                        line["parent_id"] = registered_section_id
                    lines.extend(method_group["registered_lines"])
                if method_group["pending_lines"]:
                    pending_section_id = report._get_generic_line_id(
                        "account.journal",
                        journal.id,
                        parent_line_id=method_line_id,
                        markup="daily_pay_section_pending_%s" % method_markup,
                    )
                    lines.append(
                        (
                            0,
                            {
                                "id": pending_section_id,
                                "name": _("Pendientes (borrador y cuentas puente)"),
                                "columns": self._build_row_columns(
                                    report, options, {}
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "parent_id": method_line_id,
                            },
                        )
                    )
                    for _sequence, line in method_group["pending_lines"]:
                        line["parent_id"] = pending_section_id
                    lines.extend(method_group["pending_lines"])
            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="daily_pay_journal_subtotal",
                        ),
                        "name": _("Total (%(journal)s)", journal=journal.display_name),
                        "columns": self._build_amount_total_columns(
                            report,
                            options,
                            journal_group_totals,
                        ),
                        "level": 1,
                        "unfoldable": False,
                        "class": "total",
                    },
                )
            )

        lines.append(
            (
                0,
                {
                    "id": report._get_generic_line_id(
                        None, None, markup="daily_pay_total"
                    ),
                    "name": _("Total"),
                    "columns": self._build_amount_total_columns(
                        report,
                        options,
                        totals_by_group,
                    ),
                    "level": 0,
                    "unfoldable": False,
                    "class": "total",
                },
            )
        )

        return lines
