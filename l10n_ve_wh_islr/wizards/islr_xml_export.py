# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

import base64
import re
import xml.etree.ElementTree as ET

from odoo import fields, models
from odoo.exceptions import UserError

RIF_PATTERN = re.compile(r"^[VEJPG]\d{9}$")

MONTH_SELECTION = [
    ("01", "Enero"),
    ("02", "Febrero"),
    ("03", "Marzo"),
    ("04", "Abril"),
    ("05", "Mayo"),
    ("06", "Junio"),
    ("07", "Julio"),
    ("08", "Agosto"),
    ("09", "Septiembre"),
    ("10", "Octubre"),
    ("11", "Noviembre"),
    ("12", "Diciembre"),
]


class L10nVeIslrXmlExport(models.TransientModel):
    _name = "l10n.ve.islr.xml.export"
    _description = "Exportar XML de Retenciones ISLR (SENIAT)"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Char(
        string="Año",
        required=True,
        size=4,
        default=lambda self: fields.Date.context_today(self).strftime("%Y"),
    )
    month = fields.Selection(
        MONTH_SELECTION,
        string="Mes",
        required=True,
        default=lambda self: fields.Date.context_today(self).strftime("%m"),
    )
    file_data = fields.Binary(string="Archivo XML", readonly=True)
    file_name = fields.Char(string="Nombre del Archivo", readonly=True)

    def _format_rif(self, vat, owner_name):
        rif = re.sub(r"[^A-Za-z0-9]", "", vat or "").upper()
        if not RIF_PATTERN.match(rif):
            raise UserError(
                self.env._(
                    "El RIF de %s no es válido para el XML del SENIAT: se espera "
                    "una letra V/E/J/P/G seguida de 9 dígitos (ej. J123456789).",
                    owner_name,
                )
            )
        return rif

    def _get_invoice_number(self, move):
        digits = re.sub(r"\D", "", (move.ref or move.name or "")) if move else ""
        return digits[-10:] if digits else "0"

    def _get_control_number(self, move):
        value = ""
        if move and "l10n_ve_control_number" in move._fields:
            value = move.l10n_ve_control_number or ""
        if "-" in value:
            value = value.rsplit("-", 1)[1]
        digits = re.sub(r"\D", "", value)
        return digits or "NA"

    def _get_voucher_details(self, voucher):
        """Return one move and base share tuple per invoice in a voucher."""
        moves = voucher.move_ids
        if len(moves) <= 1:
            return [(moves[:1], voucher.base)]
        currency = voucher.currency_id
        weights = [
            abs(move.amount_untaxed_signed) or abs(move.amount_total_signed)
            for move in moves
        ]
        total_weight = sum(weights)
        details = []
        remaining = voucher.base
        for index, move in enumerate(moves):
            if index == len(moves) - 1:
                share = remaining
            else:
                factor = (
                    weights[index] / total_weight if total_weight else 1.0 / len(moves)
                )
                share = currency.round(voucher.base * factor)
                remaining -= share
            details.append((move, share))
        return details

    def _check_seniat_codes(self, vouchers):
        """Reject the zero-declaration code on actual vouchers."""
        placeholder = vouchers.filtered(
            lambda voucher: (
                voucher.concept_id._get_seniat_code(voucher.person_type) or "000"
            )
            == "000"
        )
        if placeholder:
            lines = "\n".join(
                f"- {voucher.number}: {voucher.concept_id.name}"
                for voucher in placeholder
            )
            raise UserError(
                self.env._(
                    "Los siguientes comprobantes del período usan conceptos ISLR "
                    "con código SENIAT '000' o vacío ('000' es solo para la "
                    "declaración sin operaciones): confirmar el código del anexo "
                    "6.1 antes de declarar.\n%s",
                    lines,
                )
            )

    def action_generate(self):
        self.ensure_one()
        if not (self.year or "").isdigit() or len(self.year) != 4:
            raise UserError(self.env._("El año debe tener 4 dígitos (ej. 2026)."))
        period = f"{self.year}{self.month}"
        vouchers = self.env["l10n.ve.islr.voucher"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "issued"),
                ("period", "=", period),
            ],
            order="number",
        )
        self._check_seniat_codes(vouchers)
        rif_agente = self._format_rif(self.company_id.vat, self.company_id.display_name)
        ut_model = self.env["l10n.ve.ut"]
        ves = ut_model._get_ves_currency()
        root = ET.Element(
            "RelacionRetencionesISLR", RifAgente=rif_agente, Periodo=period
        )
        if not vouchers:
            last_day = fields.Date.end_of(
                fields.Date.to_date(f"{self.year}-{self.month}-01"), "month"
            )
            detail = ET.SubElement(root, "DetalleRetencion")
            ET.SubElement(detail, "RifRetenido").text = rif_agente
            ET.SubElement(detail, "NumeroFactura").text = "0"
            ET.SubElement(detail, "NumeroControl").text = "NA"
            ET.SubElement(detail, "FechaOperacion").text = last_day.strftime("%d/%m/%Y")
            ET.SubElement(detail, "CodigoConcepto").text = "000"
            ET.SubElement(detail, "MontoOperacion").text = "0.00"
            ET.SubElement(detail, "PorcentajeRetencion").text = "0.00"
        for voucher in vouchers:
            if voucher.currency_id != ves:
                ut_model._require_ves_rate(voucher.company_id, voucher.date)
            rif_retenido = self._format_rif(
                voucher.partner_id.vat, voucher.partner_id.display_name
            )
            code = voucher.concept_id._get_seniat_code(voucher.person_type)
            rate = 0.0 if voucher.currency_id.is_zero(voucher.amount) else voucher.rate
            for move, base_share in self._get_voucher_details(voucher):
                detail = ET.SubElement(root, "DetalleRetencion")
                ET.SubElement(detail, "RifRetenido").text = rif_retenido
                ET.SubElement(detail, "NumeroFactura").text = self._get_invoice_number(
                    move
                )
                ET.SubElement(detail, "NumeroControl").text = self._get_control_number(
                    move
                )
                ET.SubElement(detail, "FechaOperacion").text = voucher.date.strftime(
                    "%d/%m/%Y"
                )
                ET.SubElement(detail, "CodigoConcepto").text = code
                base_ves = voucher.currency_id._convert(
                    base_share, ves, voucher.company_id, voucher.date
                )
                ET.SubElement(detail, "MontoOperacion").text = f"{base_ves:.2f}"
                ET.SubElement(detail, "PorcentajeRetencion").text = f"{rate:.2f}"
        xml_bytes = ET.tostring(root, encoding="ISO-8859-1", xml_declaration=True)
        self.write(
            {
                "file_data": base64.b64encode(xml_bytes),
                "file_name": f"RelacionRetencionesISLR_{rif_agente}_{period}.xml",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
