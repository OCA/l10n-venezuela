# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, fields, models


class L10nVeLiquidityBookReportMixin(models.AbstractModel):
    _name = "l10n.ve.liquidity.book.report.mixin"
    _inherit = "account.report.custom.handler.oca"
    _description = "Mixin for Venezuelan bank and cash auxiliary books"

    def _get_journal_types(self):
        raise NotImplementedError

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "liquidity_book_report",
        }

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        report._init_options_journals(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", self._get_journal_types())],
        )
        options["unfold_all"] = options.get("unfold_all", True)
        return result

    def export_to_pdf(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        return type(report).export_to_pdf(
            report.with_context(force_landscape_printing=True), options
        )

    def _get_liquidity_account(self, journal):
        return journal.default_account_id

    def _get_selected_journals(self, report, options):
        selected = report._get_options_journals(options)
        journal_ids = [journal["id"] for journal in selected]
        journals = self.env["account.journal"].browse(journal_ids)
        return journals.filtered(
            lambda journal: journal.type in self._get_journal_types()
        ).sorted(lambda journal: (journal.company_id.name, journal.name))

    def _to_report_date(self, value):
        if not value:
            return False
        if isinstance(value, str):
            return fields.Date.from_string(value)
        return value

    def _get_report_date_bounds(self, options):
        date_info = options["date"]
        date_from = self._to_report_date(date_info.get("date_from"))
        date_to = self._to_report_date(date_info["date_to"])
        if not date_from:
            date_from = date_to
        return date_from, date_to

    def _get_opening_balances(self, report, options, account_ids):
        if not account_ids:
            return {}
        date_from, _date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)
        balances = defaultdict(float)
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "in", account_ids),
                ("company_id", "in", company_ids),
                ("parent_state", "=", "posted"),
                ("date", "<", date_from),
            ]
        )
        for line in lines:
            balances[line.account_id.id] += line.balance
        return balances

    def _get_account_move_lines(self, report, options, account_id):
        date_from, date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)
        return self.env["account.move.line"].search(
            [
                ("account_id", "=", account_id),
                ("company_id", "in", company_ids),
                ("parent_state", "=", "posted"),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
            ],
            order="date asc, move_id asc, id asc",
        )

    def _build_row_columns(self, report, options, values_map):
        line_columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            if label not in values_map:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )
                continue
            line_columns.append(
                report._build_column_dict(values_map[label], column, options=options)
            )
        return line_columns

    def _build_amount_total_columns(
        self, report, options, amounts_by_column_group, amount_labels
    ):
        columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            col_group_key = column["column_group_key"]
            if label in amount_labels:
                columns.append(
                    report._build_column_dict(
                        amounts_by_column_group[col_group_key].get(label, 0.0),
                        column,
                        options=options,
                    )
                )
            else:
                columns.append(report._build_column_dict(None, column, options=options))
        return columns

    def _get_move_detail_label(self, aml):
        journal_code = aml.journal_id.code or ""
        journal_info = f"[{journal_code}]" if journal_code else ""
        line_name = aml.name or ""
        return f"{journal_info} {line_name}".strip()

    def _get_move_comp_number(self, aml):
        return aml.ref or aml.move_id.name or ""

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        journals = self._get_selected_journals(report, options)
        totals_by_group = defaultdict(
            lambda: {
                "previous_balance": 0.0,
                "debit": 0.0,
                "credit": 0.0,
                "balance": 0.0,
            }
        )

        account_ids = [
            account.id
            for journal in journals
            if (account := self._get_liquidity_account(journal))
        ]
        opening_balances = self._get_opening_balances(report, options, account_ids)

        for journal in journals:
            account = self._get_liquidity_account(journal)
            if not account:
                continue

            previous_balance = opening_balances.get(account.id, 0.0)
            running_balance = previous_balance
            journal_totals = defaultdict(
                lambda: {
                    "previous_balance": previous_balance,  # noqa: B023
                    "debit": 0.0,
                    "credit": 0.0,
                    "balance": previous_balance,  # noqa: B023
                }
            )
            account_title = _("%(journal)s — %(account)s") % {
                "journal": journal.display_name,
                "account": account.display_name,
            }

            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="liquidity_book_journal_header",
                        ),
                        "name": account_title,
                        "columns": self._build_row_columns(report, options, {}),
                        "level": 0,
                        "unfoldable": False,
                    },
                )
            )

            move_lines = self._get_account_move_lines(report, options, account.id)
            for aml in move_lines:
                debit = aml.debit
                credit = aml.credit
                running_balance += debit - credit
                for col_group_key in options["column_groups"]:
                    journal_totals[col_group_key]["debit"] += debit
                    journal_totals[col_group_key]["credit"] += credit
                    journal_totals[col_group_key]["balance"] = running_balance

                lines.append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.move.line",
                                aml.id,
                                markup="liquidity_book_line",
                            ),
                            "name": account.code,
                            "columns": self._build_row_columns(
                                report,
                                options,
                                {
                                    "date": aml.date,
                                    "comp_number": self._get_move_comp_number(aml),
                                    "document": aml.move_id.name or "",
                                    "detail": self._get_move_detail_label(aml),
                                    "debit": debit,
                                    "credit": credit,
                                    "balance": running_balance,
                                },
                            ),
                            "level": 1,
                            "unfoldable": False,
                            "caret_options": "account.move.line",
                        },
                    )
                )

            for col_group_key in options["column_groups"]:
                totals_by_group[col_group_key]["previous_balance"] += previous_balance
                totals_by_group[col_group_key]["debit"] += journal_totals[
                    col_group_key
                ]["debit"]
                totals_by_group[col_group_key]["credit"] += journal_totals[
                    col_group_key
                ]["credit"]
                totals_by_group[col_group_key]["balance"] += journal_totals[
                    col_group_key
                ]["balance"]

            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="liquidity_book_journal_total",
                        ),
                        "name": _("Total (%(journal)s)", journal=journal.display_name),
                        "columns": self._build_amount_total_columns(
                            report,
                            options,
                            journal_totals,
                            (
                                "previous_balance",
                                "debit",
                                "credit",
                                "balance",
                            ),
                        ),
                        "level": 1,
                        "unfoldable": False,
                        "class": "total",
                    },
                )
            )

        if journals:
            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            None, None, markup="liquidity_book_total"
                        ),
                        "name": _("Total"),
                        "columns": self._build_amount_total_columns(
                            report,
                            options,
                            totals_by_group,
                            (
                                "previous_balance",
                                "debit",
                                "credit",
                                "balance",
                            ),
                        ),
                        "level": 0,
                        "unfoldable": False,
                        "class": "total",
                    },
                )
            )

        return lines
