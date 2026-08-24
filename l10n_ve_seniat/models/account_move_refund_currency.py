from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


# pylint: disable=consider-merging-classes-inherited
class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_requires_refund_company_currency(self):
        self.ensure_one()
        if "l10n_ve_emission_medium" not in self.journal_id._fields:
            return False
        return bool(self.journal_id.l10n_ve_emission_medium)

    def _l10n_ve_company_price_unit_from_origin_line(self, line):
        if "price_subtotal_currency" in line._fields and line.price_subtotal_currency:
            subtotal = abs(line.price_subtotal_currency)
        else:
            subtotal = abs(line.balance)
        quantity = abs(line.quantity) or 1.0
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        if discount_factor <= 0.0:
            return 0.0
        return subtotal / quantity / discount_factor

    def _l10n_ve_force_refund_to_company_currency(self):
        ve_country = self.env.ref("base.ve").code
        for move in self:
            if (
                move.country_code != ve_country
                or move.move_type != "out_refund"
                or move.currency_id == move.company_currency_id
                or not move._l10n_ve_requires_refund_company_currency()
            ):
                continue
            origin = move.reversed_entry_id
            if not origin or origin.currency_id == origin.company_currency_id:
                continue
            if (
                hasattr(move, "_l10n_ve_is_post_discount_credit_note")
                and move._l10n_ve_is_post_discount_credit_note()
            ):
                move._l10n_ve_apply_company_currency_from_line_balances()
                continue
            cc = move.company_currency_id
            orig_lines = origin.invoice_line_ids.sorted(
                lambda line: (line.sequence, line.id)
            )
            cred_lines = move.invoice_line_ids.sorted(
                lambda line: (line.sequence, line.id)
            )
            if len(orig_lines) != len(cred_lines):
                raise ValidationError(
                    _(
                        "La nota de crédito '%(credit)s' no coincide en líneas "
                        "con la factura origen '%(origin)s'. Revise el borrador "
                        "o cree la reversión desde el asistente estándar."
                    )
                    % {
                        "credit": move.display_name,
                        "origin": origin.display_name,
                    }
                )
            line_cmds = []
            for ol, cl in zip(orig_lines, cred_lines, strict=False):
                if ol.display_type != cl.display_type:
                    raise ValidationError(
                        _(
                            "Las líneas de la nota de crédito no coinciden con "
                            "la factura origen (tipo de línea distinto)."
                        )
                    )
                if ol.display_type in ("product", "cogs"):
                    line_cmds.append(
                        Command.update(
                            cl.id,
                            {
                                "price_unit": (
                                    move._l10n_ve_company_price_unit_from_origin_line(
                                        ol
                                    )
                                ),
                            },
                        )
                    )
                elif ol.display_type == "rounding":
                    line_cmds.append(
                        Command.update(
                            cl.id,
                            {
                                "amount_currency": abs(ol.balance),
                            },
                        )
                    )
            vals = {"currency_id": cc.id}
            if line_cmds:
                vals["invoice_line_ids"] = line_cmds
            move.write(vals)
        return super()._l10n_ve_force_refund_to_company_currency()

    def _l10n_ve_apply_company_currency_from_line_balances(self):
        self.ensure_one()
        cc = self.company_currency_id
        line_cmds = []
        for line in self.invoice_line_ids:
            if line.display_type in ("product", "cogs"):
                quantity = abs(line.quantity) or 1.0
                discount_factor = 1.0 - (line.discount or 0.0) / 100.0
                if discount_factor <= 0.0:
                    price_unit = 0.0
                else:
                    price_unit = abs(line.balance) / quantity / discount_factor
                line_cmds.append(Command.update(line.id, {"price_unit": price_unit}))
            elif line.display_type == "rounding":
                line_cmds.append(
                    Command.update(
                        line.id,
                        {"amount_currency": abs(line.balance)},
                    )
                )
        vals = {"currency_id": cc.id}
        if line_cmds:
            vals["invoice_line_ids"] = line_cmds
        self.write(vals)

    def _l10n_ve_to_company_abs_amount(self):
        self.ensure_one()
        amount = super()._l10n_ve_to_company_abs_amount()
        if (
            self.move_type != "out_refund"
            or not self.reversed_entry_id
            or self.currency_id == self.company_currency_id
            or self.country_code != self.env.ref("base.ve").code
        ):
            return amount
        origin = self.reversed_entry_id
        company_cur = self.company_currency_id
        origin_total = abs(origin.amount_total)
        origin_company = origin._l10n_ve_to_company_abs_amount()
        if (
            self.currency_id == origin.currency_id
            and not self.currency_id.is_zero(origin_total)
            and not company_cur.is_zero(origin_company)
        ):
            ratio = abs(self.amount_total) / origin_total
            return company_cur.round(origin_company * ratio)
        origin_date = (
            origin.invoice_date or origin.date or fields.Date.context_today(self)
        )
        return company_cur.round(
            self.currency_id._convert(
                abs(self.amount_total),
                company_cur,
                self.company_id,
                origin_date,
            )
        )

    def action_post(self):
        ve_code = self.env.ref("base.ve").code
        to_company_refund = self.filtered(
            lambda m: m.country_code == ve_code
            and m.move_type == "out_refund"
            and m.state == "draft"
            and m.reversed_entry_id
            and m.currency_id != m.company_currency_id
            and m.reversed_entry_id.currency_id
            != m.reversed_entry_id.company_currency_id
            and m._l10n_ve_requires_refund_company_currency()
        )
        if to_company_refund:
            to_company_refund._l10n_ve_force_refund_to_company_currency()
        for move in self:
            if (
                move.country_code == ve_code
                and move.move_type == "out_refund"
                and move.currency_id != move.company_currency_id
                and move._l10n_ve_requires_refund_company_currency()
            ):
                raise ValidationError(
                    _(
                        "No se puede confirmar la nota de crédito '%(move)s'. "
                        "Las notas de crédito deben registrarse en bolívares "
                        "(moneda de la compañía)."
                    )
                    % {"move": move.name or _("Borrador")}
                )
        return super().action_post()
