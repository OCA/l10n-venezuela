# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, models


class DiaryBookReportCustomHandler(models.AbstractModel):
    _name = "account.diary.book.report.handler.oca"
    _inherit = "account.report.custom.handler.oca"
    _description = "Diary Book Report Custom Handler"

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "diary_book_report",
        }

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        options["unfold_all"] = options.get("unfold_all", True)
        return result

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        totals_by_column_group = defaultdict(lambda: {"debit": 0.0, "credit": 0.0})

        moves_data = self._get_moves_data(report, options)

        for move_data in moves_data:
            move = move_data["move"]
            move_lines = move_data["lines"].sorted("id")

            for line in move_lines:
                line_columns = []
                for column in options["columns"]:
                    col_expr_label = column["expression_label"]
                    if col_expr_label == "date":
                        line_columns.append(
                            report._build_column_dict(
                                move.date,
                                column,
                                options=options,
                            )
                        )
                    elif col_expr_label == "move_name":
                        line_columns.append(
                            report._build_column_dict(
                                move.name,
                                column,
                                options=options,
                            )
                        )
                    elif col_expr_label == "debit":
                        line_columns.append(
                            report._build_column_dict(
                                line.debit,
                                column,
                                options=options,
                            )
                        )
                    elif col_expr_label == "credit":
                        line_columns.append(
                            report._build_column_dict(
                                line.credit,
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
                        "account.move.line", line.id, markup="diary_line"
                    ),
                    "name": f"{line.account_id.code} - {line.account_id.name}",
                    "columns": line_columns,
                    "level": 1,
                    "unfoldable": False,
                    "caret_options": "account.move.line",
                }
                lines.append(line_dict)

                for col_group_key in options["column_groups"]:
                    totals_by_column_group[col_group_key]["debit"] += line.debit
                    totals_by_column_group[col_group_key]["credit"] += line.credit

        total_line_columns = []
        for column in options["columns"]:
            col_expr_label = column["expression_label"]
            column_group_key = column["column_group_key"]
            if col_expr_label == "debit":
                total_line_columns.append(
                    report._build_column_dict(
                        totals_by_column_group[column_group_key]["debit"],
                        column,
                        options=options,
                    )
                )
            elif col_expr_label == "credit":
                total_line_columns.append(
                    report._build_column_dict(
                        totals_by_column_group[column_group_key]["credit"],
                        column,
                        options=options,
                    )
                )
            else:
                total_line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )

        total_line = {
            "id": report._get_generic_line_id(None, None, markup="total"),
            "name": _("Total"),
            "columns": total_line_columns,
            "level": 0,
            "unfoldable": False,
            "class": "total",
        }
        lines.append(total_line)

        return [(0, line) for line in lines]

    def _get_moves_data(self, report, options):
        domain = report._get_options_domain(options, "strict_range")

        move_lines = self.env["account.move.line"].search(
            domain, order="date, move_id, id"
        )

        moves_dict = {}
        for line in move_lines:
            move = line.move_id
            if move.state != "posted":
                continue
            if move.id not in moves_dict:
                moves_dict[move.id] = {
                    "move": move,
                    "lines": self.env["account.move.line"],
                }
            moves_dict[move.id]["lines"] |= line

        moves_list = list(moves_dict.values())
        moves_list.sort(key=lambda x: (x["move"].date, x["move"].name))

        return moves_list
