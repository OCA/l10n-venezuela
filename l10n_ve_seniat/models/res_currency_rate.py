# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


_L10N_VE_INVOICE_MOVE_TYPES = (
    "out_invoice",
    "out_refund",
    "in_invoice",
    "in_refund",
    "out_receipt",
    "in_receipt",
)


class ResCurrencyRate(models.Model):
    _name = "res.currency.rate"
    _inherit = ["res.currency.rate", "mail.thread"]

    l10n_ve_rate_edit_count = fields.Integer(
        string="Ediciones de tasa",
        default=0,
        copy=False,
        tracking=True,
    )

    l10n_ve_is_today = fields.Boolean(
        compute="_compute_l10n_ve_is_today",
    )

    l10n_ve_rate_count_readonly = fields.Boolean(
        compute="_compute_l10n_ve_rate_count_readonly",
    )

    @api.depends_context("uid")
    def _compute_l10n_ve_rate_count_readonly(self):
        locked = not self.env.user.has_group("base.group_system")
        for rec in self:
            rec.l10n_ve_rate_count_readonly = locked

    @api.depends("name")
    def _compute_l10n_ve_is_today(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.l10n_ve_is_today = (not rec.name) or (rec.name == today)

    def _l10n_ve_rate_keys_in_vals(self, vals):
        v = self._sanitize_vals(dict(vals))
        return bool(
            {"rate", "company_rate", "inverse_company_rate"} & set(v.keys())
        )

    def _l10n_ve_skip_validation(self):
        return bool(self.env.context.get("l10n_ve_skip_currency_rate_validation"))

    def _l10n_ve_allow_historical_rate_write(self):
        return bool(self.env.context.get("l10n_ve_allow_historical_rate_write"))

    def _l10n_ve_company_uses_rate_rules(self):
        self.ensure_one()
        return self.company_id.account_fiscal_country_id.code == "VE"

    def _l10n_ve_get_posted_moves_using_rate(self):
        self.ensure_one()
        if not self.currency_id or not self.name:
            return self.env["account.move"]
        return self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("currency_id", "=", self.currency_id.id),
                ("invoice_date", "=", self.name),
                ("state", "=", "posted"),
                ("move_type", "in", _L10N_VE_INVOICE_MOVE_TYPES),
            ]
        )

    def _l10n_ve_check_posted_moves_before_rate_change(self):
        for rec in self:
            if not rec._l10n_ve_company_uses_rate_rules():
                continue
            posted_moves = rec._l10n_ve_get_posted_moves_using_rate()
            if not posted_moves:
                continue
            raise UserError(
                _(
                    "No se puede modificar la tasa del %(date)s para %(currency)s "
                    "porque existen facturas confirmadas que la utilizan: "
                    "%(invoices)s. Vuelva esas facturas a borrador para poder "
                    "actualizar la tasa.",
                    date=rec.name,
                    currency=rec.currency_id.display_name,
                    invoices=", ".join(posted_moves.mapped("name")),
                )
            )

    @api.ondelete(at_uninstall=False)
    def _l10n_ve_unlink_currency_rate(self):
        for rec in self:
            if rec._l10n_ve_company_uses_rate_rules():
                raise UserError(_("No se pueden eliminar tasas de cambio."))

    @api.model_create_multi
    def create(self, vals_list):
        rates = super(
            ResCurrencyRate,
            self.with_context(l10n_ve_skip_currency_rate_validation=True),
        ).create(vals_list)
        return rates.with_context(l10n_ve_skip_currency_rate_validation=False)

    def write(self, vals):
        if self._l10n_ve_skip_validation():
            return super().write(vals)

        vals = dict(vals)
        if (
            "l10n_ve_rate_edit_count" in vals
            and not self.env.user.has_group("base.group_system")
        ):
            raise UserError(
                _("No puede modificar manualmente el contador de ediciones de la tasa.")
            )

        today = fields.Date.context_today(self)
        for rec in self:
            if rec.name != today and not self._l10n_ve_allow_historical_rate_write():
                raise UserError(
                    _(
                        "Solo se pueden modificar las tasas con fecha de hoy "
                        "(%(today)s). Esta línea es del %(rate_date)s.",
                        today=today,
                        rate_date=rec.name,
                    )
                )

        rate_update = self._l10n_ve_rate_keys_in_vals(vals)
        if rate_update:
            self._l10n_ve_check_posted_moves_before_rate_change()
            for rec in self:
                if rec.l10n_ve_rate_edit_count >= 2:
                    raise UserError(
                        _(
                            "Se alcanzó el máximo de 2 ediciones de la tasa para "
                            "esta línea."
                        )
                    )

        old_rates = {r.id: r.rate for r in self}
        res = super().write(vals)

        if rate_update:
            for rec in self:
                if (
                    float_compare(
                        old_rates[rec.id],
                        rec.rate,
                        precision_digits=12,
                    )
                    != 0
                ):
                    new_count = rec.l10n_ve_rate_edit_count + 1
                    rec.with_context(
                        l10n_ve_skip_currency_rate_validation=True
                    ).write({"l10n_ve_rate_edit_count": new_count})
                    if rec.currency_id:
                        rec.currency_id.message_post(
                            body=Markup(
                                "<p>%s</p>"
                                % _(
                                    "Tasa del %(date)s: %(old)s → %(new)s "
                                    "(edición %(count)s/2).",
                                    date=rec.name,
                                    old=old_rates[rec.id],
                                    new=rec.rate,
                                    count=new_count,
                                )
                            ),
                            subtype_xmlid="mail.mt_note",
                        )
        return res
