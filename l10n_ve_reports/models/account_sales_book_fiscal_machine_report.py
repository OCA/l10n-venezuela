# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class SalesBookFiscalMachineReportCustomHandler(models.AbstractModel):
    _name = "account.sales.book.fiscal.machine.report.handler.oca"
    _inherit = ["account.report.custom.handler.oca", "l10n.ve.book.report.mixin"]
    _description = "Sales Book Fiscal Machine Report Custom Handler"

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "sales_book_fiscal_machine_report",
        }

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

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        options["unfold_all"] = options.get("unfold_all", True)
        self._l10n_ve_prepare_book_columns(
            options,
            self.env.company,
            "sale",
            include_third_party=False,
        )
        return result

    def _caret_options_initializer(self):
        return {
            "sales_book_fiscal_machine_group": [
                {"name": _("View Grouped Moves"), "action": "action_open_group_moves"},
            ],
        }

    @api.model
    def action_open_group_moves(self, options, params):
        import logging

        _logger = logging.getLogger(__name__)
        _logger.info("=== action_open_group_moves CALLED ===")
        _logger.info("Options: %s", options)
        _logger.info("Params: %s", params)

        if not params:
            _logger.warning("Params is None or empty, returning close action")
            return {"type": "ir.actions.act_window_close"}
        line_id = params.get("line_id", "") or params.get("id", "")
        _logger.info("Line ID from params: %s", line_id)
        if not line_id:
            _logger.warning("Line ID is empty, returning close action")
            return {"type": "ir.actions.act_window_close"}

        report = self.env["account.report"].browse(options.get("report_id"))
        _logger.info(
            "Report ID: %s, exists: %s", options.get("report_id"), report.exists()
        )
        if not report.exists():
            _logger.warning("Report does not exist, returning close action")
            return {"type": "ir.actions.act_window_close"}

        model, record_id = report._get_model_info_from_id(line_id)
        _logger.info("Parsed line_id - Model: %s, Record ID: %s", model, record_id)

        if not record_id:
            _logger.warning("Record ID is empty after parsing, returning close action")
            return {"type": "ir.actions.act_window_close"}

        # Get the first move to determine the group characteristics
        first_move = self.env["account.move"].browse(record_id)
        _logger.info("First move ID: %s, exists: %s", record_id, first_move.exists())
        if not first_move.exists():
            _logger.warning("First move does not exist, returning close action")
            return {"type": "ir.actions.act_window_close"}

        # Reconstruct the group by finding all moves with the same grouping
        # characteristics
        # Group is determined by: date (create_date or invoice_date in format
        # "%d-%m-%Y"), serial_number, and report_z
        serial_number = first_move.l10n_ve_serial_number or ""
        report_z = first_move.l10n_ve_report_z or ""
        _logger.info(
            "Group characteristics - Serial: %s, Report Z: %s", serial_number, report_z
        )
        _logger.info(
            "First move create_date: %s, invoice_date: %s",
            first_move.create_date,
            first_move.invoice_date,
        )

        # Get the date key in the same format as used in _dynamic_lines_generator
        if first_move.create_date:
            _date_key = first_move.create_date.strftime("%d-%m-%Y")
            # For create_date (datetime field), filter by date range for the same day
            date_start = first_move.create_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            date_end = first_move.create_date.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            date_domain = [
                ("create_date", ">=", date_start),
                ("create_date", "<=", date_end),
            ]
            _logger.info("Using create_date filter: %s to %s", date_start, date_end)
        elif first_move.invoice_date:
            _date_key = first_move.invoice_date.strftime("%d-%m-%Y")
            # For invoice_date (date field), filter by exact date
            date_domain = [("invoice_date", "=", first_move.invoice_date)]
            _logger.info("Using invoice_date filter: %s", first_move.invoice_date)
        else:
            _logger.warning("No date available in first move, returning close action")
            return {"type": "ir.actions.act_window_close"}

        # Build domain to find all moves in the same group
        domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "in", ["posted", "cancel"]),
            ("l10n_ve_serial_number", "=", serial_number),
            ("l10n_ve_report_z", "=", report_z),
        ] + date_domain

        # Add company filter
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

        _logger.info("Search domain: %s", domain)
        # Find all moves in the group
        moves = self.env["account.move"].search(
            domain, order="invoice_date asc, id asc"
        )
        move_ids = moves.ids
        _logger.info("Found %s moves in group: %s", len(move_ids), move_ids)

        if not move_ids:
            _logger.warning("No moves found in group, returning close action")
            return {"type": "ir.actions.act_window_close"}

        action = {
            "type": "ir.actions.act_window",
            "name": _("Grouped Moves"),
            "res_model": "account.move",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", move_ids)],
            "context": {
                "create": False,
                "edit": False,
            },
        }
        _logger.info("Returning action: %s", action)
        return action

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

        domain.append(("l10n_ve_invoice_number", "!=", False))
        domain.append(("l10n_ve_serial_number", "!=", False))
        domain.append(("l10n_ve_report_z", "!=", False))

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

    def _get_tax_values_from_stored(self, move):
        if not hasattr(move, "sale_tax_data") or not move.sale_tax_data:
            return self._calculate_tax_values(move)

        company = move.company_id
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

    def _format_date(self, date_value):
        if not date_value:
            return ""
        if isinstance(date_value, str):
            return date_value
        return format_date(self.env, date_value, date_format="dd/MM/yyyy")

    def _dynamic_lines_generator(  # noqa: C901
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []

        moves_data = self._get_moves_data(report, options)

        agrouped_by_date = {}
        for move_data in moves_data:
            move = move_data["move"]
            key = (
                str(move.create_date.strftime("%d-%m-%Y"))
                if move.create_date
                else str(move.invoice_date.strftime("%d-%m-%Y"))
                if move.invoice_date
                else ""
            )
            if not agrouped_by_date.get(key):
                agrouped_by_date[key] = [move]
            else:
                agrouped_by_date[key].append(move)

        for _date_key, date_moves in agrouped_by_date.items():
            agrouped_by_report_z = {}
            for move in sorted(
                date_moves,
                key=lambda m: int(m.l10n_ve_invoice_number)
                if m.l10n_ve_invoice_number and m.l10n_ve_invoice_number.isdigit()
                else 0,
            ):
                key = (
                    str(move.l10n_ve_serial_number or "")
                    + "_"
                    + str(move.l10n_ve_report_z or "")
                )
                if not agrouped_by_report_z.get(key):
                    agrouped_by_report_z[key] = [move]
                else:
                    agrouped_by_report_z[key].append(move)

            for _report_key, report_moves in agrouped_by_report_z.items():
                range_start = 0
                range_last = 0
                cumulative = {
                    "tax_base_exempt_aliquot": 0.0,
                    "amount_taxed": 0.0,
                    "tax_base_reduced_aliquot": 0.0,
                    "amount_reduced_aliquot": 0.0,
                    "tax_base_general_aliquot": 0.0,
                    "amount_general_aliquot": 0.0,
                }
                group_moves_list = []

                for index, move in enumerate(report_moves):
                    next_move = move
                    is_last_move = False
                    if (index + 1) < len(report_moves):
                        next_move = report_moves[index + 1]
                    else:
                        is_last_move = True

                    tax_values = (
                        self._get_tax_values_from_stored(move)
                        if hasattr(move, "sale_tax_data") and move.sale_tax_data
                        else self._calculate_tax_values(move)
                    )
                    amounts = {
                        "tax_base_exempt_aliquot": tax_values.get("total_exempt", 0.0),
                        "amount_taxed": tax_values.get("total_taxed", 0.0),
                        "tax_base_reduced_aliquot": tax_values.get("base_reduced", 0.0),
                        "amount_reduced_aliquot": tax_values.get("amount_reduced", 0.0),
                        "tax_base_general_aliquot": tax_values.get("base_general", 0.0),
                        "amount_general_aliquot": tax_values.get("amount_general", 0.0),
                    }

                    cumulative = {
                        "tax_base_exempt_aliquot": cumulative["tax_base_exempt_aliquot"]
                        + amounts.get("tax_base_exempt_aliquot", 0.0),
                        "amount_taxed": cumulative["amount_taxed"]
                        + amounts.get("amount_taxed", 0.0),
                        "tax_base_reduced_aliquot": cumulative[
                            "tax_base_reduced_aliquot"
                        ]
                        + amounts.get("tax_base_reduced_aliquot", 0.0),
                        "amount_reduced_aliquot": cumulative["amount_reduced_aliquot"]
                        + amounts.get("amount_reduced_aliquot", 0.0),
                        "tax_base_general_aliquot": cumulative[
                            "tax_base_general_aliquot"
                        ]
                        + amounts.get("tax_base_general_aliquot", 0.0),
                        "amount_general_aliquot": cumulative["amount_general_aliquot"]
                        + amounts.get("amount_general_aliquot", 0.0),
                    }

                    if range_start == 0:
                        range_start = move.l10n_ve_invoice_number or "0"
                        group_moves_list = []

                    if move.move_type in ["out_invoice", "out_refund"]:
                        has_retention = (
                            hasattr(move, "retention_iva_line_ids")
                            and move.retention_iva_line_ids
                        )
                        if (
                            hasattr(move.partner_id, "taxpayer_type")
                            and move.partner_id.taxpayer_type == "ordinary"
                            and move.move_type == "out_invoice"
                            and not has_retention
                        ):
                            if move not in group_moves_list:
                                group_moves_list.append(move)
                        if (
                            move.move_type == "out_invoice"
                            and hasattr(move.journal_id, "is_debit")
                            and move.journal_id.is_debit
                        ):
                            line_dict = self._build_line_dict(
                                report, move, tax_values, options, index + 1
                            )
                            lines.append(line_dict)
                            cumulative = {
                                "tax_base_exempt_aliquot": 0.0,
                                "amount_taxed": 0.0,
                                "tax_base_reduced_aliquot": 0.0,
                                "amount_reduced_aliquot": 0.0,
                                "tax_base_general_aliquot": 0.0,
                                "amount_general_aliquot": 0.0,
                            }
                            range_start = 0
                            continue
                        if (
                            (
                                hasattr(move.partner_id, "prefix_vat")
                                and move.partner_id.prefix_vat == "J"
                            )
                            or (
                                hasattr(move.partner_id, "taxpayer_type")
                                and move.partner_id.taxpayer_type != "ordinary"
                            )
                            or move.move_type != "out_invoice"
                        ):
                            if cumulative["amount_taxed"] != amounts["amount_taxed"]:
                                data = {
                                    "move_type": move.move_type,
                                    "range_start": range_start,
                                    "range_end": range_last
                                    if range_last != 0
                                    else move.l10n_ve_invoice_number,
                                    "date": move.invoice_date,
                                    "report_z": move.l10n_ve_report_z,
                                    "serial_number": move.l10n_ve_serial_number,
                                }
                                group_line = self._build_group_line_dict(
                                    report,
                                    data,
                                    cumulative,
                                    options,
                                    group_moves_list.copy(),
                                )
                                lines.append(group_line)
                                range_last = 0
                                group_moves_list = []
                            line_dict = self._build_line_dict(
                                report, move, tax_values, options, index + 1
                            )
                            lines.append(line_dict)
                            cumulative = {
                                "tax_base_exempt_aliquot": 0.0,
                                "amount_taxed": 0.0,
                                "tax_base_reduced_aliquot": 0.0,
                                "amount_reduced_aliquot": 0.0,
                                "tax_base_general_aliquot": 0.0,
                                "amount_general_aliquot": 0.0,
                            }
                            range_start = 0
                            continue

                        has_retention = (
                            hasattr(move, "retention_iva_line_ids")
                            and move.retention_iva_line_ids
                        )
                        if (
                            (
                                (
                                    (
                                        self._format_date(move.invoice_date)
                                        != self._format_date(next_move.invoice_date)
                                    )
                                    or (
                                        hasattr(next_move.partner_id, "prefix_vat")
                                        and next_move.partner_id.prefix_vat == "J"
                                    )
                                    or (
                                        hasattr(next_move.partner_id, "taxpayer_type")
                                        and next_move.partner_id.taxpayer_type
                                        != "ordinary"
                                    )
                                    or next_move.move_type != "out_invoice"
                                )
                                or is_last_move
                            )
                            and (
                                hasattr(move.partner_id, "taxpayer_type")
                                and move.partner_id.taxpayer_type == "ordinary"
                            )
                            and not has_retention
                        ):
                            data = {
                                "move_type": move.move_type,
                                "range_start": range_start,
                                "range_end": move.l10n_ve_invoice_number,
                                "date": move.invoice_date,
                                "report_z": move.l10n_ve_report_z,
                                "serial_number": move.l10n_ve_serial_number,
                            }
                            group_line = self._build_group_line_dict(
                                report,
                                data,
                                cumulative,
                                options,
                                group_moves_list.copy(),
                            )
                            lines.append(group_line)
                            cumulative = {
                                "tax_base_exempt_aliquot": 0.0,
                                "amount_taxed": 0.0,
                                "tax_base_reduced_aliquot": 0.0,
                                "amount_reduced_aliquot": 0.0,
                                "tax_base_general_aliquot": 0.0,
                                "amount_general_aliquot": 0.0,
                            }
                            range_start = 0
                            group_moves_list = []
                            continue

                        has_retention = (
                            hasattr(move, "retention_iva_line_ids")
                            and move.retention_iva_line_ids
                        )
                        if has_retention:
                            line_dict = self._build_line_dict(
                                report, move, tax_values, options, index + 1
                            )
                            lines.append(line_dict)
                            cumulative = {
                                "tax_base_exempt_aliquot": 0.0,
                                "amount_taxed": 0.0,
                                "tax_base_reduced_aliquot": 0.0,
                                "amount_reduced_aliquot": 0.0,
                                "tax_base_general_aliquot": 0.0,
                                "amount_general_aliquot": 0.0,
                            }
                            range_start = 0
                            continue
                        if (
                            not is_last_move
                            and hasattr(move.partner_id, "taxpayer_type")
                            and move.partner_id.taxpayer_type == "ordinary"
                        ):
                            range_last = move.l10n_ve_invoice_number or "0"
                            continue
                        range_last = move.l10n_ve_invoice_number or "0"

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

    def _build_line_dict(self, report, move, tax_values, options, index):  # noqa: C901
        retention_values = self._get_retention_iva_values(move, options)
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
                    format_date(self.env, move.invoice_date, date_format="dd/MM/yyyy")
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
            elif col_expr_label == "serial_number":
                line_columns.append(
                    report._build_column_dict(
                        move.l10n_ve_serial_number or "-",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "report_z":
                line_columns.append(
                    report._build_column_dict(
                        move.l10n_ve_report_z or "-",
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
                        move.l10n_ve_invoice_number or "-",
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
                number_affected = (
                    move.reversed_entry_id.l10n_ve_invoice_number
                    if (
                        hasattr(move, "reversed_entry_id")
                        and move.reversed_entry_id
                        and hasattr(move.reversed_entry_id, "l10n_ve_invoice_number")
                    )
                    else ""
                )
                line_columns.append(
                    report._build_column_dict(
                        number_affected or "",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "total_sales_iva":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("total_taxed", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "total_sales_not_iva":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("total_exempt", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_general_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("base_general", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "general_aliquot":
                percent_val = tax_values.get("percent_general", 0.0)
                line_columns.append(
                    report._build_column_dict(
                        percent_val,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_general_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("amount_general", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_reduced_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("base_reduced", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "reduced_aliquot":
                percent_val = tax_values.get("percent_reduced", 0.0)
                line_columns.append(
                    report._build_column_dict(
                        percent_val,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_reduced_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("amount_reduced", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_extend_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("base_extend", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "extend_aliquot":
                percent_val = tax_values.get("percent_extend", 0.0)
                line_columns.append(
                    report._build_column_dict(
                        percent_val,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_extend_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        tax_values.get("amount_extend", 0.0),
                        column,
                        options=options,
                    )
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
            else:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )

        line_dict = {
            "id": report._get_generic_line_id(
                "account.move", move.id, markup="sales_book_fiscal_machine_line"
            ),
            "name": move.name or "",
            "columns": line_columns,
            "level": 1,
            "unfoldable": False,
            "caret_options": "account.move",
        }
        return line_dict

    def _build_group_line_dict(  # noqa: C901
        self, report, data, cumulative, options, group_moves=None
    ):
        line_columns = []
        for column in options["columns"]:
            col_expr_label = column["expression_label"]
            if col_expr_label == "index":
                line_columns.append(
                    report._build_column_dict(
                        "",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "document_date":
                line_columns.append(
                    report._build_column_dict(
                        self._format_date(data.get("date")),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "vat":
                line_columns.append(
                    report._build_column_dict(
                        "RESUMEN",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "partner_name":
                line_columns.append(
                    report._build_column_dict(
                        "Resumen Diario de Ventas",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "document_number":
                range_start = data.get("range_start", "0")
                range_end = data.get("range_end", "0")
                line_columns.append(
                    report._build_column_dict(
                        f"Desde {range_start} Hasta {range_end}",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "serial_number":
                line_columns.append(
                    report._build_column_dict(
                        data.get("serial_number", "-"),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "report_z":
                line_columns.append(
                    report._build_column_dict(
                        data.get("report_z", "-"),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "move_type":
                move_type_map = {
                    "out_invoice": "FAC",
                    "in_invoice": "FAC",
                    "out_refund": "NC",
                    "in_refund": "NC",
                    "out_debit": "ND",
                    "in_debit": "ND",
                }
                move_type = move_type_map.get(data.get("move_type"), "")
                line_columns.append(
                    report._build_column_dict(
                        move_type,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "transaction_type":
                line_columns.append(
                    report._build_column_dict(
                        "01-REG",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "number_invoice_affected":
                line_columns.append(
                    report._build_column_dict(
                        "",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "reduced_aliquot":
                company = self.env.company
                percent_reduced = self._l10n_ve_get_tax_rate_for_type(
                    company, "reduced", "sale"
                )
                line_columns.append(
                    report._build_column_dict(
                        percent_reduced,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "general_aliquot":
                company = self.env.company
                percent_general = self._l10n_ve_get_tax_rate_for_type(
                    company, "general", "sale"
                )
                line_columns.append(
                    report._build_column_dict(
                        percent_general,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "total_sales_iva":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("amount_taxed", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "total_sales_not_iva":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("tax_base_exempt_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_reduced_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("amount_reduced_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_general_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("amount_general_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_reduced_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("tax_base_reduced_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_general_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("tax_base_general_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "tax_base_extend_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("tax_base_extend_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "extend_aliquot":
                company = self.env.company
                percent_extend = self._l10n_ve_get_tax_rate_for_type(
                    company, "extend", "sale"
                )
                line_columns.append(
                    report._build_column_dict(
                        percent_extend,
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "amount_extend_aliquot":
                line_columns.append(
                    report._build_column_dict(
                        cumulative.get("amount_extend_aliquot", 0.0),
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "date_retention":
                line_columns.append(
                    report._build_column_dict(
                        "",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "number_retention":
                line_columns.append(
                    report._build_column_dict(
                        "",
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "iva_retained":
                line_columns.append(
                    report._build_column_dict(
                        0.0,
                        column,
                        options=options,
                    )
                )
            else:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )

        # Store only the first move ID to avoid ValueError in _parse_line_id
        first_move_id = group_moves[0].id if group_moves else None

        line_dict = {
            "id": report._get_generic_line_id(
                "account.move",
                first_move_id,
                markup="sales_book_fiscal_machine_group_line",
            ),
            "name": "Resumen Diario de Ventas",
            "columns": line_columns,
            "level": 1,
            "unfoldable": False,
            "caret_options": "sales_book_fiscal_machine_group",
            "model": "account.move",
        }
        return line_dict

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
            {
                "name": _("Total Sales and Tax Debits for the Period"),
                "key": "total",
                "is_total": True,
            },
        ]

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
                elif col_expr_label == "tax_base_general_aliquot":
                    line_columns.append(
                        report._build_column_dict(
                            section_data["base_invoices"],
                            column,
                            options=options,
                        )
                    )
                elif col_expr_label == "amount_general_aliquot":
                    line_columns.append(
                        report._build_column_dict(
                            section_data["amount_invoices"],
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
