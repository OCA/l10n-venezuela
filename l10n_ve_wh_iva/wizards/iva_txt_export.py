# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
import calendar
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nVeIvaWhTxtExport(models.TransientModel):
    _name = "l10n.ve.iva.wh.txt.export"
    _description = "Exportar TXT de Retenciones de IVA (Forma 99035)"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=lambda self: self._default_date_from(),
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=lambda self: self._default_date_to(),
    )
    file_data = fields.Binary(string="Archivo TXT", readonly=True)
    file_name = fields.Char()

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1) if today.day <= 15 else today.replace(day=16)

    @api.model
    def _default_date_to(self):
        today = fields.Date.context_today(self)
        if today.day <= 15:
            return today.replace(day=15)
        return today.replace(day=calendar.monthrange(today.year, today.month)[1])

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise ValidationError(
                    self.env._(
                        "La fecha inicial de la quincena no puede ser posterior "
                        "a la final."
                    )
                )

    @api.model
    def _sanitize(self, value, size=20):
        return re.sub(r"[\t\r\n]", " ", value or "").strip()[:size]

    def action_generate(self):
        self.ensure_one()
        company = self.company_id
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        rif_agent = voucher_model._l10n_ve_format_rif(company.vat)
        if not rif_agent:
            raise UserError(
                self.env._(
                    "Configure el RIF de la compañía %s (campo NIF) antes de exportar.",
                    company.display_name,
                )
            )
        ves = voucher_model._l10n_ve_get_ves_currency()
        vouchers = voucher_model.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ],
            order="number",
        )
        if not vouchers:
            raise UserError(
                self.env._(
                    "No hay comprobantes de retención de IVA emitidos entre "
                    "%(date_from)s y %(date_to)s.",
                    date_from=self.date_from,
                    date_to=self.date_to,
                )
            )
        rows = []
        for voucher in vouchers:
            period = voucher.date.strftime("%Y%m")
            rif_partner = voucher_model._l10n_ve_format_rif(voucher.partner_id.vat)
            if not rif_partner:
                raise UserError(
                    self.env._(
                        "El proveedor %s no tiene RIF configurado (campo NIF).",
                        voucher.partner_id.display_name,
                    )
                )
            for line in voucher._l10n_ve_get_report_lines():
                doc_date = line["date"]

                def to_ves(amount, conversion_date=doc_date):
                    return company.currency_id._convert(
                        amount, ves, company, conversion_date
                    )

                def to_ves_wh(amount, conversion_date=voucher.date):
                    return company.currency_id._convert(
                        amount, ves, company, conversion_date
                    )

                columns = [
                    rif_agent,
                    period,
                    doc_date.strftime("%Y-%m-%d"),
                    "C",
                    line["doc_type"],
                    rif_partner,
                    self._sanitize(line["doc_number"]) or "0",
                    self._sanitize(line["control_number"]) or "0",
                    f"{to_ves(line['total']):.2f}",
                    f"{to_ves(line['base']):.2f}",
                    f"{to_ves_wh(line['withheld']):.2f}",
                    self._sanitize(line["affected"]) or "0",
                    voucher.number,
                    f"{to_ves(line['exempt']):.2f}",
                    f"{line['rate']:.2f}",
                    "0",
                ]
                rows.append("\t".join(columns))
        content = "\r\n".join(rows) + "\r\n"
        self.file_data = base64.b64encode(content.encode())
        self.file_name = "IVA_99035_{}_{}_{}.txt".format(
            rif_agent,
            self.date_from.strftime("%Y%m%d"),
            self.date_to.strftime("%Y%m%d"),
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Exportar TXT Retenciones IVA (99035)"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
