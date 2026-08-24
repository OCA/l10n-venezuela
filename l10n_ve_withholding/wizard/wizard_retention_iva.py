from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class TxtWizard(models.TransientModel):
    _name = "wizard.retention.iva"
    _description = "File IVA taxes with the SENIAT"

    date_start = fields.Date(default=date.today().replace(day=1))
    date_end = fields.Date(
        default=date.today().replace(day=1) + relativedelta(months=1, days=-1)
    )

    def generate_txt(self):
        company_id = self.env.company.id
        if not (self.date_start and self.date_end):
            raise UserError(_("You must enter a start and end date"))
        retention_count = self.env["account.retention"].search_count(
            [
                ("date", ">=", self.date_start),
                ("date", "<=", self.date_end),
                ("state", "=", "emitted"),
                ("type_retention", "=", "iva"),
                ("type", "=", "in_invoice"),
                ("company_id", "=", company_id),
            ]
        )
        if retention_count == 0:
            raise UserError(_("No retentions found for the selected period"))

        url = f"/web/binary/download_retention_iva_txt?&date_start={self.date_start}&date_end={self.date_end}&company_id={str(company_id)}"  # noqa: E501
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def _retention_iva(self, retentions):
        document_types = {
            "in_invoice": "01",
            "in_debit": "02",
            "in_refund": "03",
        }

        data = []
        for line in retentions.mapped("retention_line_ids"):
            line_data = {}
            line_data["RIF del agente de retención"] = (
                line.retention_id.company_id.partner_id.vat
            )
            line_data["Período impositivo"] = line.retention_id.date.strftime("%Y%m")
            line_data["Fecha de factura"] = line.move_id.invoice_date.strftime(
                "%Y-%m-%d"
            )
            line_data["Tipo de operación"] = "C"

            if line.move_id.debit_origin_id:
                line_data["Tipo de documento"] = document_types["in_debit"]
                orig = line.move_id.debit_origin_id
                line_data["Número del documento afectado"] = (
                    orig.ref or orig.name or "0"
                )
            else:
                line_data["Tipo de documento"] = document_types[line.move_id.move_type]
                rev = line.move_id.reversed_entry_id
                line_data["Número del documento afectado"] = (
                    (rev.ref or rev.name or "0") if rev else "0"
                )

            line_data["RIF de proveedor"] = (
                line.move_id.partner_id.prefix_vat or ""
            ) + (line.move_id.partner_id.vat or "")
            line_data["Número de documento"] = line.move_id.ref or line.move_id.name
            line_data["Número de control"] = line.move_id.ref
            line_data["Número de comprobante de retención"] = (
                int(line.retention_id.number) if line.retention_id.number else 0
            )
            line_data["Alícuota"] = line.aliquot
            exempt_amount = sum(
                line.move_id.invoice_line_ids.filtered(
                    lambda line: line.tax_ids.amount == 0
                ).mapped("price_subtotal")
            )
            line_data["Monto total del documento"] = (
                line.invoice_amount + line.iva_amount + exempt_amount
            )
            line_data["Base imponible"] = line.invoice_amount
            line_data["Monto del Iva Retenido"] = line.retention_amount
            line_data["Monto exento del IVA"] = exempt_amount
            line_data["Número de Expediente"] = "0"
            data.append(line_data)
        return data
