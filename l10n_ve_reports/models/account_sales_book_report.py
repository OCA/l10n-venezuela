# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import _, fields, models
from odoo.tools.misc import format_date


class SalesBookReportCustomHandler(models.AbstractModel):
    _name = "account.sales.book.report.handler.oca"
    _inherit = ["account.report.custom.handler.oca", "l10n.ve.book.report.mixin"]
    _description = "Sales Book Report Custom Handler"

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "sales_book_report",
        }

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        options["unfold_all"] = options.get("unfold_all", True)
        self._l10n_ve_prepare_book_columns(
            options,
            self.env.company,
            "sale",
            include_third_party=True,
        )
        return result

    def _get_retention_iva_values(self, move, options):
        """Get retention IVA values for a move."""
        if (
            not hasattr(move, "retention_iva_line_ids")
            or not move.retention_iva_line_ids
        ):
            return {
                "date_retention": "",
                "number_retention": "",
                "iva_retained": 0.0,
            }

        multiplier = -1 if move.move_type == "out_refund" else 1
        date_from_str = options.get("date", {}).get("date_from")
        date_to_str = options.get("date", {}).get("date_to")

        date_from = fields.Date.to_date(date_from_str) if date_from_str else None
        date_to = fields.Date.to_date(date_to_str) if date_to_str else None

        ret_lines = (
            move.retention_iva_line_ids.filtered(
                lambda x: x.retention_id.state == "emitted"
            )
            if move.state == "posted"
            else move.retention_iva_line_ids
        )

        ret_vals = {
            "date_retention": "",
            "number_retention": "",
            "iva_retained": 0.0,
        }

        if not ret_lines:
            return ret_vals

        for ret_line in ret_lines:
            retention = ret_line.retention_id
            if not retention:
                continue

            # Check if retention date is within the report date range
            if date_from and retention.date_accounting:
                if (
                    retention.date_accounting < date_from
                    or retention.date_accounting > date_to
                ):
                    continue

            if ret_vals["date_retention"]:
                # If we already have a date, append the new one (comma-separated)
                ret_vals["date_retention"] += ", " + format_date(
                    self.env, retention.date, date_format="dd/MM/yyyy"
                )
            else:
                ret_vals["date_retention"] = (
                    format_date(self.env, retention.date, date_format="dd/MM/yyyy")
                    if retention.date
                    else ""
                )

            if not ret_vals["number_retention"]:
                ret_vals["number_retention"] = (
                    move.iva_voucher_number
                    if hasattr(move, "iva_voucher_number")
                    else ""
                )

            if move.state != "cancel":
                # Use retention_amount which is in company currency
                ret_vals["iva_retained"] += ret_line.retention_amount * multiplier

        return ret_vals

    def _get_move_igtf_amount(self, move):
        if move.state != "posted":
            return 0.0
        if not hasattr(move, "l10n_ve_igtf_document_has_igtf"):
            return 0.0
        if not move.l10n_ve_igtf_document_has_igtf():
            return 0.0
        _igtf_currency, igtf_company = move._l10n_ve_igtf_get_origin_igtf_line_totals()
        return igtf_company

    def _dynamic_lines_generator(  # noqa: C901
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []

        moves_data = self._get_moves_data(report, options)
        index = 1

        for move_data in moves_data:
            move = move_data["move"]

            tax_values = (
                self._get_tax_values_from_stored(move)
                if hasattr(move, "sale_tax_data") and move.sale_tax_data
                else self._calculate_tax_values(move)
            )
            retention_values = self._get_retention_iva_values(move, options)
            igtf_amount = self._get_move_igtf_amount(move)

            line_columns = []
            for column in options["columns"]:
                col_expr_label = column["expression_label"]
                if col_expr_label == "index":
                    line_columns.append(
                        report._build_column_dict(
                            index,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "document_date":
                    date_str = (
                        format_date(
                            self.env, move.invoice_date, date_format="dd/MM/yyyy"
                        )
                        if move.invoice_date
                        else ""
                    )
                    line_columns.append(
                        report._build_column_dict(
                            date_str,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "vat":
                    line_columns.append(
                        report._build_column_dict(
                            move.partner_id.vat or "",
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "partner_name":
                    line_columns.append(
                        report._build_column_dict(
                            move.invoice_partner_display_name or "",
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "third_party_name":
                    third_name = ""
                    if (
                        move.l10n_ve_on_behalf_of_third_party
                        and move.l10n_ve_third_party_partner_id
                    ):
                        third_name = move.l10n_ve_third_party_partner_id.name or ""
                    line_columns.append(
                        report._build_column_dict(
                            third_name,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "third_party_vat":
                    third_vat = ""
                    if (
                        move.l10n_ve_on_behalf_of_third_party
                        and move.l10n_ve_third_party_partner_id
                    ):
                        third_vat = move.l10n_ve_third_party_partner_id.vat or ""
                    line_columns.append(
                        report._build_column_dict(
                            third_vat,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "move_type":
                    move_type = self._determinate_type_for_move(move)
                    line_columns.append(
                        report._build_column_dict(
                            move_type,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "document_number":
                    line_columns.append(
                        report._build_column_dict(
                            move.name or "",
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "correlative":
                    correlative = (
                        move.l10n_ve_control_number
                        if hasattr(move, "l10n_ve_control_number")
                        else (move.correlative if hasattr(move, "correlative") else "")
                    )
                    line_columns.append(
                        report._build_column_dict(
                            correlative or "",
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "transaction_type":
                    transaction_type = self._determinate_transaction_type(move)
                    line_columns.append(
                        report._build_column_dict(
                            transaction_type or "",
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "number_invoice_affected":
                    number_affected = self._get_number_invoice_affected(move)
                    line_columns.append(
                        report._build_column_dict(
                            number_affected,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "total_sales_iva":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("total_taxed", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "total_sales_not_iva":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("total_exempt", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "tax_base_general_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("base_general", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "general_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("percent_general", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "amount_general_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("amount_general", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "tax_base_reduced_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("base_reduced", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "reduced_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("percent_reduced", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "amount_reduced_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("amount_reduced", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "tax_base_extend_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("base_extend", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "extend_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("percent_extend", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "amount_extend_aliquot":
                    val = (
                        0.0
                        if move.l10n_ve_on_behalf_of_third_party
                        else tax_values.get("amount_extend", 0.0)
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_total_sales_iva":
                    val = (
                        tax_values.get("total_taxed", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_total_sales_not_iva":
                    val = (
                        tax_values.get("total_exempt", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_tax_base_general_aliquot":
                    val = (
                        tax_values.get("base_general", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_general_aliquot":
                    val = (
                        tax_values.get("percent_general", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_amount_general_aliquot":
                    val = (
                        tax_values.get("amount_general", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_tax_base_reduced_aliquot":
                    val = (
                        tax_values.get("base_reduced", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_reduced_aliquot":
                    val = (
                        tax_values.get("percent_reduced", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_amount_reduced_aliquot":
                    val = (
                        tax_values.get("amount_reduced", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_tax_base_extend_aliquot":
                    val = (
                        tax_values.get("base_extend", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_extend_aliquot":
                    val = (
                        tax_values.get("percent_extend", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "third_party_amount_extend_aliquot":
                    val = (
                        tax_values.get("amount_extend", 0.0)
                        if move.l10n_ve_on_behalf_of_third_party
                        else 0.0
                    )
                    line_columns.append(
                        report._build_column_dict(val, column, options=options)
                    )
                elif col_expr_label == "date_retention":
                    line_columns.append(
                        report._build_column_dict(
                            retention_values.get("date_retention", ""),
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "number_retention":
                    line_columns.append(
                        report._build_column_dict(
                            retention_values.get("number_retention", ""),
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "iva_retained":
                    line_columns.append(
                        report._build_column_dict(
                            retention_values.get("iva_retained", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "igtf":
                    line_columns.append(
                        report._build_column_dict(
                            igtf_amount,
                            column,
                            options=options,
                        )
                    )
                else:
                    line_columns.append(
                        report._build_column_dict(None, column, options=options)
                    )

            line_dict = {
                "id": report._get_generic_line_id(
                    "account.move", move.id, markup="sales_book_line"
                ),
                "name": move.name or "",
                "columns": line_columns,
                "level": 1,
                "unfoldable": False,
                "caret_options": "account.move",
            }
            lines.append(line_dict)
            index += 1

        separator_line = {
            "id": report._get_generic_line_id(None, None, markup="resume_separator"),
            "name": "",
            "columns": [
                report._build_column_dict(None, col, options=options)
                for col in options["columns"]
            ],
            "level": 0,
            "unfoldable": False,
            "class": "resume_separator",
        }
        lines.append(separator_line)

        resume_title_line = {
            "id": report._get_generic_line_id(None, None, markup="resume_title"),
            "name": _("SUMMARY"),
            "columns": [
                report._build_column_dict(None, col, options=options)
                for col in options["columns"]
            ],
            "level": 0,
            "unfoldable": False,
            "class": "resume_title",
        }
        lines.append(resume_title_line)

        resume_lines = self._generate_resume_lines(report, options, moves_data)
        lines.extend(resume_lines)

        return [(0, line) for line in lines]

    def _get_moves_data(self, report, options):
        date_from = options.get("date", {}).get("date_from")
        date_to = options.get("date", {}).get("date_to")

        domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "in", ["posted", "cancel"]),
        ]

        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))

        multi_company = options.get("multi_company", [])
        if multi_company:
            domain.append(
                (
                    "company_id",
                    "in",
                    [c["id"] for c in multi_company if c.get("selected")],
                )
            )
        else:
            domain.append(("company_id", "=", self.env.company.id))

        selected_journal_ids = [
            journal["id"] for journal in report._get_options_journals(options)
        ]
        if selected_journal_ids:
            domain.append(("journal_id", "in", selected_journal_ids))

        if hasattr(self.env["account.move"], "l10n_ve_control_number"):
            domain += [
                ("l10n_ve_control_number", "!=", False),
                ("l10n_ve_control_number", "!=", "/"),
            ]
        elif hasattr(self.env["account.move"], "correlative"):
            domain += [
                ("correlative", "!=", False),
                ("correlative", "!=", "/"),
            ]

        moves = self.env["account.move"].search(
            domain, order="invoice_date asc, id asc"
        )

        return [{"move": move} for move in moves]

    def _determinate_type_for_move(self, move):
        if hasattr(move.journal_id, "is_debit") and move.journal_id.is_debit:
            return "ND"
        move_type_map = {
            "out_invoice": "FAC",
            "in_invoice": "FAC",
            "out_refund": "NC",
            "in_refund": "NC",
            "out_debit": "ND",
            "in_debit": "ND",
        }
        return move_type_map.get(move.move_type, "")

    def _determinate_transaction_type(self, move):
        if move.state == "cancel":
            return "03-ANU"

        if move.move_type in ["out_invoice", "in_invoice"] and move.state == "posted":
            if hasattr(move.journal_id, "is_debit") and move.journal_id.is_debit:
                return "02-REG"
            return "01-REG"

        if move.move_type in ["out_debit", "in_debit"] and move.state == "posted":
            return "02-REG"

        if move.move_type in ["out_refund", "in_refund"] and move.state == "posted":
            return "03-REG"

        return ""

    def _get_number_invoice_affected(self, move):
        if hasattr(move.journal_id, "is_debit") and move.journal_id.is_debit:
            if hasattr(move, "debit_origin_id") and move.debit_origin_id:
                return move.debit_origin_id.name
        if hasattr(move, "reversed_entry_id") and move.reversed_entry_id:
            return move.reversed_entry_id.name
        return "--"

    def _get_tax_values_from_stored(self, move):
        if not hasattr(move, "sale_tax_data") or not move.sale_tax_data:
            return self._calculate_tax_values(move)

        company = move.company_id
        _tax_config = self._l10n_ve_get_tax_config(company)
        sale_tax_data = move.sale_tax_data
        result = self._l10n_ve_init_tax_values_result(company, "sale")
        result["total_taxed"] = sale_tax_data.get("_total_taxed", 0.0)

        for tax_group_id_str, tax_info in sale_tax_data.items():
            if tax_group_id_str.startswith("_"):
                continue
            tax_type = tax_info.get("tax_type")
            if tax_type == "exempt":
                result["total_exempt"] += tax_info.get("base", 0.0)
            elif tax_type == "general":
                result["base_general"] = tax_info.get("base", 0.0)
                result["amount_general"] = tax_info.get("amount", 0.0)
                result["percent_general"] = self._l10n_ve_get_tax_rate_for_type(
                    company, "general", "sale"
                )
            elif tax_type == "reduced":
                result["base_reduced"] = tax_info.get("base", 0.0)
                result["amount_reduced"] = tax_info.get("amount", 0.0)
                result["percent_reduced"] = self._l10n_ve_get_tax_rate_for_type(
                    company, "reduced", "sale"
                )
            elif tax_type == "extend":
                result["base_extend"] = tax_info.get("base", 0.0)
                result["amount_extend"] = tax_info.get("amount", 0.0)
                result["percent_extend"] = self._l10n_ve_get_tax_rate_for_type(
                    company, "extend", "sale"
                )

        return result

    def _calculate_tax_values(self, move):
        company = move.company_id
        result = self._l10n_ve_init_tax_values_result(company, "sale")

        if move.state != "posted":
            return result

        multiplier = -1 if move.move_type == "out_refund" else 1
        tax_totals = move.tax_totals or {}
        tax_config = self._l10n_ve_get_tax_config(company)

        if not tax_totals:
            return result

        subtotals = tax_totals.get("subtotals", [])
        for subtotal in subtotals:
            if not isinstance(subtotal, dict):
                continue
            tax_groups = subtotal.get("tax_groups", [])
            if not isinstance(tax_groups, list):
                continue
            for tax_info in tax_groups:
                if not isinstance(tax_info, dict):
                    continue
                tax_group_id = tax_info.get("id")
                if not tax_group_id:
                    continue

                for ttype, tg_id in tax_config.items():
                    if tg_id == tax_group_id:
                        self._l10n_ve_apply_tax_values_from_config(
                            result,
                            tax_config,
                            tax_info,
                            ttype,
                            company,
                            "sale",
                            multiplier,
                        )
                        break

        return result

    def _generate_resume_lines(self, report, options, moves_data):
        resume_lines = []

        moves = [m["move"] for m in moves_data]
        company = self.env.company

        resume_data = self._calculate_resume_data(moves, company)

        resume_sections = [
            {"name": _("Exempt Internal Sales"), "key": "exempt"},
            {"name": _("General Rate Exports"), "key": "exports_general"},
            {"name": _("Extended Rate Exports"), "key": "exports_extend"},
            {"name": _("General Rate Internal Sales"), "key": "general"},
            {"name": _("Reduced Rate Internal Sales"), "key": "reduced"},
            {
                "name": _("Adjustments to Tax Debits from Previous Periods"),
                "key": "adjustments",
            },
        ]
        if company.l10n_ve_on_behalf_of_third_party_enabled:
            resume_sections.append(
                {
                    "name": _("Ventas por cuenta de terceros"),
                    "key": "third_party",
                    "third_party_section": True,
                }
            )
        resume_sections.append(
            {
                "name": _("Total Sales and Tax Debits for the Period"),
                "key": "total",
                "is_total": True,
            }
        )

        for section in resume_sections:
            section_data = resume_data.get(
                section["key"],
                {
                    "base_invoices": 0.0,
                    "amount_invoices": 0.0,
                    "base_credits": 0.0,
                    "amount_credits": 0.0,
                },
            )

            line_columns = []
            for column in options["columns"]:
                col_expr_label = column["expression_label"]
                if col_expr_label == "partner_name":
                    line_columns.append(
                        report._build_column_dict(
                            None,
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "tax_base_general_aliquot" and not section.get(
                    "third_party_section"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("base_invoices", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "amount_general_aliquot" and not section.get(
                    "third_party_section"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("amount_invoices", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_total_sales_iva"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("total_taxed", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_total_sales_not_iva"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("total_exempt", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_tax_base_general_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("base_general", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_amount_general_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("amount_general", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_tax_base_reduced_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("base_reduced", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_amount_reduced_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("amount_reduced", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_tax_base_extend_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("base_extend", 0.0),
                            column,
                            options=options,
                        )
                    )
                elif (
                    section.get("third_party_section")
                    and col_expr_label == "third_party_amount_extend_aliquot"
                ):
                    line_columns.append(
                        report._build_column_dict(
                            section_data.get("amount_extend", 0.0),
                            column,
                            options=options,
                        )
                    )
                else:
                    line_columns.append(
                        report._build_column_dict(None, column, options=options)
                    )

            line_class = "total" if section.get("is_total") else "resume"
            line_dict = {
                "id": report._get_generic_line_id(
                    None, None, markup=f"resume_{section['key']}"
                ),
                "name": section["name"],
                "columns": line_columns,
                "level": 0 if section.get("is_total") else 1,
                "unfoldable": False,
                "class": line_class,
            }
            resume_lines.append(line_dict)

        return resume_lines

    def _calculate_resume_data(self, moves, company):
        result = {
            "exempt": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "exports_general": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "exports_extend": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "general": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "reduced": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "adjustments": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
            "third_party": {
                "total_taxed": 0.0,
                "total_exempt": 0.0,
                "base_general": 0.0,
                "amount_general": 0.0,
                "base_reduced": 0.0,
                "amount_reduced": 0.0,
                "base_extend": 0.0,
                "amount_extend": 0.0,
            },
            "total": {
                "base_invoices": 0.0,
                "amount_invoices": 0.0,
                "base_credits": 0.0,
                "amount_credits": 0.0,
            },
        }

        invoices = [
            m for m in moves if m.move_type == "out_invoice" and m.state == "posted"
        ]
        credit_notes = [
            m for m in moves if m.move_type == "out_refund" and m.state == "posted"
        ]

        for move in invoices:
            if move.l10n_ve_on_behalf_of_third_party:
                continue
            tax_values = (
                self._get_tax_values_from_stored(move)
                if hasattr(move, "sale_tax_data") and move.sale_tax_data
                else self._calculate_tax_values(move)
            )

            result["exempt"]["base_invoices"] += tax_values.get("total_exempt", 0.0)
            result["general"]["base_invoices"] += tax_values.get("base_general", 0.0)
            result["general"]["amount_invoices"] += tax_values.get(
                "amount_general", 0.0
            )
            result["reduced"]["base_invoices"] += tax_values.get("base_reduced", 0.0)
            result["reduced"]["amount_invoices"] += tax_values.get(
                "amount_reduced", 0.0
            )

        for move in credit_notes:
            if move.l10n_ve_on_behalf_of_third_party:
                continue
            tax_values = (
                self._get_tax_values_from_stored(move)
                if hasattr(move, "sale_tax_data") and move.sale_tax_data
                else self._calculate_tax_values(move)
            )

            result["exempt"]["base_credits"] += abs(tax_values.get("total_exempt", 0.0))
            result["general"]["base_credits"] += abs(
                tax_values.get("base_general", 0.0)
            )
            result["general"]["amount_credits"] += abs(
                tax_values.get("amount_general", 0.0)
            )
            result["reduced"]["base_credits"] += abs(
                tax_values.get("base_reduced", 0.0)
            )
            result["reduced"]["amount_credits"] += abs(
                tax_values.get("amount_reduced", 0.0)
            )

        third_party_invoices = [
            m for m in invoices if m.l10n_ve_on_behalf_of_third_party
        ]
        third_party_credit_notes = [
            m for m in credit_notes if m.l10n_ve_on_behalf_of_third_party
        ]
        for move in third_party_invoices:
            tax_values = (
                self._get_tax_values_from_stored(move)
                if hasattr(move, "sale_tax_data") and move.sale_tax_data
                else self._calculate_tax_values(move)
            )
            result["third_party"]["total_taxed"] += tax_values.get("total_taxed", 0.0)
            result["third_party"]["total_exempt"] += tax_values.get("total_exempt", 0.0)
            result["third_party"]["base_general"] += tax_values.get("base_general", 0.0)
            result["third_party"]["amount_general"] += tax_values.get(
                "amount_general", 0.0
            )
            result["third_party"]["base_reduced"] += tax_values.get("base_reduced", 0.0)
            result["third_party"]["amount_reduced"] += tax_values.get(
                "amount_reduced", 0.0
            )
            result["third_party"]["base_extend"] += tax_values.get("base_extend", 0.0)
            result["third_party"]["amount_extend"] += tax_values.get(
                "amount_extend", 0.0
            )
        for move in third_party_credit_notes:
            tax_values = (
                self._get_tax_values_from_stored(move)
                if hasattr(move, "sale_tax_data") and move.sale_tax_data
                else self._calculate_tax_values(move)
            )
            result["third_party"]["total_taxed"] += tax_values.get("total_taxed", 0.0)
            result["third_party"]["total_exempt"] += tax_values.get("total_exempt", 0.0)
            result["third_party"]["base_general"] += tax_values.get("base_general", 0.0)
            result["third_party"]["amount_general"] += tax_values.get(
                "amount_general", 0.0
            )
            result["third_party"]["base_reduced"] += tax_values.get("base_reduced", 0.0)
            result["third_party"]["amount_reduced"] += tax_values.get(
                "amount_reduced", 0.0
            )
            result["third_party"]["base_extend"] += tax_values.get("base_extend", 0.0)
            result["third_party"]["amount_extend"] += tax_values.get(
                "amount_extend", 0.0
            )

        result["total"]["base_invoices"] = (
            result["exempt"]["base_invoices"]
            + result["exports_general"]["base_invoices"]
            + result["exports_extend"]["base_invoices"]
            + result["general"]["base_invoices"]
            + result["reduced"]["base_invoices"]
            + result["adjustments"]["base_invoices"]
        )
        result["total"]["amount_invoices"] = (
            result["exports_general"]["amount_invoices"]
            + result["exports_extend"]["amount_invoices"]
            + result["general"]["amount_invoices"]
            + result["reduced"]["amount_invoices"]
            + result["adjustments"]["amount_invoices"]
        )
        result["total"]["base_credits"] = (
            result["exempt"]["base_credits"]
            + result["exports_general"]["base_credits"]
            + result["exports_extend"]["base_credits"]
            + result["general"]["base_credits"]
            + result["reduced"]["base_credits"]
            + result["adjustments"]["base_credits"]
        )
        result["total"]["amount_credits"] = (
            result["exports_general"]["amount_credits"]
            + result["exports_extend"]["amount_credits"]
            + result["general"]["amount_credits"]
            + result["reduced"]["amount_credits"]
            + result["adjustments"]["amount_credits"]
        )

        return result
