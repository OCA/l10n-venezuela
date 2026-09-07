# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nVeUt(models.Model):
    _name = "l10n.ve.ut"
    _description = "Unidad Tributaria (Venezuela)"
    _order = "date_from desc"

    date_from = fields.Date(string="Vigente desde", required=True)
    value = fields.Float(string="Valor (Bs)", required=True, digits=(16, 2))
    gaceta = fields.Char(string="Gaceta Oficial")

    @api.depends("date_from", "value")
    def _compute_display_name(self):
        for ut in self:
            ut.display_name = f"UT Bs {ut.value:.2f} (desde {ut.date_from or ''})"

    @api.constrains("value")
    def _check_value(self):
        for ut in self:
            if ut.value <= 0:
                raise ValidationError(
                    self.env._(
                        "El valor de la Unidad Tributaria debe ser mayor que cero."
                    )
                )

    @api.model
    def get_ut_value(self, date):
        """Return the tax unit value applicable on the given date."""
        date = fields.Date.to_date(date)
        ut = self.search([("date_from", "<=", date)], order="date_from desc", limit=1)
        if not ut:
            raise UserError(
                self.env._(
                    "No hay un valor de Unidad Tributaria vigente al %s. "
                    "Cárguelo en Contabilidad > Configuración > Unidad Tributaria.",
                    date,
                )
            )
        return ut.value

    @api.model
    def _get_ves_currency(self):
        # The tax unit is expressed in bolivars; consumers convert from VES.
        ves = self.env.ref("base.VES", raise_if_not_found=False)
        if not ves:
            ves = (
                self.env["res.currency"]
                .with_context(active_test=False)
                .search([("name", "=", "VES")], limit=1)
            )
        if not ves:
            raise UserError(
                self.env._("No se encontró la moneda VES (Bolívar) en el sistema.")
            )
        return ves

    @api.model
    def _require_ves_rate(self, company, date):
        """Return VES after ensuring an exchange rate exists on the date."""
        ves = self._get_ves_currency()
        date = fields.Date.to_date(date)
        has_rate = (
            self.env["res.currency.rate"]
            .sudo()
            .search_count(
                [
                    ("currency_id", "=", ves.id),
                    ("company_id", "in", [company.id, False]),
                    ("name", "<=", date),
                ],
                limit=1,
            )
        )
        if not has_rate:
            raise UserError(
                self.env._(
                    "No hay tasa de cambio del Bolívar (VES) cargada al %s: cargue "
                    "la tasa BCV en Contabilidad > Configuración > Monedas antes de "
                    "calcular retenciones de ISLR o exportar el XML del SENIAT.",
                    date,
                )
            )
        return ves
