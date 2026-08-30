# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
from xml.dom.minidom import parseString
from xml.etree import ElementTree as ET

from odoo import _, fields, models
from odoo.exceptions import UserError


class GenerateXmlWhIslr(models.TransientModel):
    _name = "generate.xml.wh.islr"
    _description = "Generate XML File for SENIAT (ISLR)"

    date_start = fields.Date(
        string="Start Date", required=True, default=fields.Date.context_today
    )
    date_end = fields.Date(
        string="End Date", required=True, default=fields.Date.context_today
    )
    xml_filename = fields.Char(string="File Name", default="retencion_islr_seniat.xml")
    xml_file = fields.Binary(string="XML File", readonly=True)
    state = fields.Selection([("draft", "Draft"), ("done", "Done")], default="draft")

    def action_generate_xml(self):
        self.ensure_one()
        vouchers = self.env["account.wh.islr.doc"].search(
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
                    "No confirmed ISLR Withholding vouchers found for the selected date range."
                )
            )

        company = self.env.company
        company_vat = (
            (company.partner_id.vat or "").replace("VE", "").replace("-", "").strip()
        )
        period_str = self.date_start.strftime("%Y%m")

        root = ET.Element(
            "RelacionRetencionesISLR",
            {
                "RifAgente": company_vat,
                "Periodo": period_str,
            },
        )

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

                det = ET.SubElement(root, "DetalleRetencion")
                ET.SubElement(det, "RifRetenido").text = partner_vat
                ET.SubElement(det, "NumeroFactura").text = inv_number
                ET.SubElement(det, "NumeroControl").text = nro_ctrl
                ET.SubElement(det, "FechaOperacion").text = (
                    inv.invoice_date or v.date
                ).strftime("%d/%m/%Y")
                ET.SubElement(det, "CodigoConcepto").text = (
                    line.concept_id.code or "001"
                )
                ET.SubElement(det, "MontoOperacion").text = f"{line.base_amount:.2f}"
                ET.SubElement(det, "PorcentajeRetencion").text = (
                    f"{line.wh_percentage:.2f}"
                )

        xml_raw = ET.tostring(root, encoding="utf-8")
        dom = parseString(xml_raw)
        xml_pretty = dom.toprettyxml(indent="  ", encoding="utf-8")

        self.write(
            {
                "xml_file": base64.b64encode(xml_pretty),
                "xml_filename": f"ISLR_{company_vat}_{period_str}.xml",
                "state": "done",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "generate.xml.wh.islr",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
