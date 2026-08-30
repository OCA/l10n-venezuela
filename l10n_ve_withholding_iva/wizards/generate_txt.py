# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class GenerateTxtWhIva(models.TransientModel):
    _name = "generate.txt.wh.iva"
    _description = "Generate TXT File for SENIAT (IVA)"

    date_start = fields.Date(
        string="Start Date", required=True, default=fields.Date.context_today
    )
    date_end = fields.Date(
        string="End Date", required=True, default=fields.Date.context_today
    )
    txt_filename = fields.Char(string="File Name", default="retencion_iva_seniat.txt")
    txt_file = fields.Binary(string="TXT File", readonly=True)
    state = fields.Selection([("draft", "Draft"), ("done", "Done")], default="draft")

    def action_generate_txt(self):
        self.ensure_one()
        vouchers = self.env["account.wh.iva"].search(
            [
                ("date", ">=", self.date_start),
                ("date", "<=", self.date_end),
                ("state", "in", ["confirmed", "done"]),
                ("type", "in", ["in_invoice", "in_refund"]),
            ]
        )
        if not vouchers:
            raise UserError(
                _(
                    "No confirmed VAT Withholding vouchers found for the "
                    "selected date range."
                )
            )

        company = self.env.company
        company_vat = (
            (company.partner_id.vat or "").replace("VE", "").replace("-", "").strip()
        )

        lines = []
        for v in vouchers:
            partner_vat = (
                (v.partner_id.vat or "").replace("VE", "").replace("-", "").strip()
            )
            for line in v.line_ids:
                inv = line.move_id
                inv_number = (inv.supplier_invoice_number or inv.name or "").replace(
                    "-", ""
                )
                nro_ctrl = (inv.nro_ctrl or "").replace("-", "")
                total_inv = f"{abs(inv.amount_total):.2f}"
                base_amt = f"{line.base_amount:.2f}"
                ret_amt = f"{line.amount_ret:.2f}"
                exempt_amt = "0.00"
                tax_rate = (
                    f"{(line.tax_amount / line.base_amount * 100):.2f}"
                    if line.base_amount
                    else "16.00"
                )
                voucher_num = v.name or ""

                # SENIAT TXT format:
                # CompanyRIF \t Period(YYYYMM) \t DocDate(YYYY-MM-DD) \t Type(C/V)
                # DocType(01/02/03) \t PartnerRIF \t DocNumber \t CtrlNumber
                # TotalAmt \t BaseAmt \t RetAmt \t 0 \t VoucherNum \t ExemptAmt
                # TaxRate \t 0
                doc_type = "01" if inv.move_type == "in_invoice" else "03"
                txt_row = (
                    f"{company_vat}\t{v.date.strftime('%Y%m')}\t"
                    f"{inv.invoice_date.strftime('%Y-%m-%d')}\tC\t{doc_type}\t"
                    f"{partner_vat}\t{inv_number}\t{nro_ctrl}\t{total_inv}\t"
                    f"{base_amt}\t{ret_amt}\t0\t{voucher_num}\t{exempt_amt}\t"
                    f"{tax_rate}\t0"
                )
                lines.append(txt_row)

        txt_content = "\r\n".join(lines)
        self.write(
            {
                "txt_file": base64.b64encode(
                    txt_content.encode("latin-1", errors="replace")
                ),
                "txt_filename": (
                    f"IVA_{company_vat}_{self.date_start.strftime('%Y%m')}.txt"
                ),
                "state": "done",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "generate.txt.wh.iva",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
