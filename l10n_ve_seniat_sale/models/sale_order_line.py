# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.mail import plaintext2html


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        alloc = self.env.context.get("l10n_ve_discount_amount_allocation") or {}
        if self.id in alloc:
            res["quantity"] = 1.0
            res["price_unit"] = -alloc[self.id]
        return res

    def _l10n_ve_is_split_discount_line(self):
        self.ensure_one()
        disc = self.company_id.sale_discount_product_id
        return (
            self.order_id.country_code == "VE"
            and disc
            and self.product_id == disc
            and not self.display_type
        )

    def _l10n_ve_get_discount_invoiced_subtotal(self):
        self.ensure_one()
        total = 0.0
        for invoice_line in self._get_invoice_lines():
            move = invoice_line.move_id
            if move.state == "cancel" and move.payment_state != "invoicing_legacy":
                continue
            amount = abs(invoice_line.price_subtotal)
            if move.move_type == "out_invoice":
                total += amount
            elif move.move_type == "out_refund":
                total -= amount
        return total

    def _l10n_ve_fix_discount_invoicing_rounding(self):
        fixed = self.env["sale.order.line"]
        for line in self:
            if not line._l10n_ve_is_split_discount_line():
                continue
            rounding = line.product_uom.rounding
            if float_is_zero(line.qty_to_invoice, precision_rounding=rounding):
                continue
            if float_is_zero(line.product_uom_qty, precision_rounding=rounding):
                continue
            expected_subtotal = abs(line.price_subtotal)
            if float_is_zero(
                expected_subtotal, precision_rounding=line.currency_id.rounding
            ):
                continue
            invoiced_subtotal = line._l10n_ve_get_discount_invoiced_subtotal()
            if (
                float_compare(
                    invoiced_subtotal,
                    expected_subtotal,
                    precision_rounding=line.currency_id.rounding,
                )
                < 0
            ):
                continue
            aligned_price = line.price_subtotal / line.product_uom_qty
            line.write({"price_unit": aligned_price})
            fixed |= line
        if fixed:
            fixed._compute_qty_invoiced()
            fixed._compute_qty_to_invoice()
            fixed.mapped("order_id")._compute_invoice_status()
        return fixed

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.quantity",
        "invoice_lines.price_subtotal",
        "price_unit",
        "product_uom_qty",
    )
    def _compute_qty_invoiced(self):
        res = super()._compute_qty_invoiced()
        for line in self.filtered(lambda sol: sol._l10n_ve_is_split_discount_line()):
            line_total = abs(line.price_unit * line.product_uom_qty)
            if float_is_zero(line_total, precision_rounding=line.currency_id.rounding):
                continue
            qty_invoiced = 0.0
            for invoice_line in line._get_invoice_lines():
                move = invoice_line.move_id
                if move.state == "cancel" and move.payment_state != "invoicing_legacy":
                    continue
                portion = (
                    abs(invoice_line.price_subtotal) / line_total * line.product_uom_qty
                )
                if move.move_type == "out_invoice":
                    qty_invoiced += portion
                elif move.move_type == "out_refund":
                    qty_invoiced -= portion
            line.qty_invoiced = qty_invoiced
        return res

    def l10n_ve_report_line_description(self):
        self.ensure_one()
        if self.display_type or self.is_downpayment or self.product_type == "combo":
            return plaintext2html(self.name or "", with_paragraph=False)
        if not self.product_id:
            return plaintext2html(self.name or "", with_paragraph=False)
        lang = self.order_id._get_lang()
        line = self.with_context(lang=lang) if lang != self.env.lang else self
        product = line.product_id.with_context(
            lang=lang,
            display_default_code=False,
        )
        parts = []
        if product.description_sale:
            parts.append(product.description_sale)
        variants = line._get_sale_order_line_multiline_description_variants()
        if variants and variants.strip():
            parts.append(variants.strip())
        if line.linked_line_id and not line.combo_item_id:
            link_product = line.linked_line_id.product_id.with_context(
                lang=lang,
                display_default_code=False,
            )
            parts.append(_("Option for: %s", link_product.display_name))
        if line.linked_line_ids and line.product_type != "combo":
            for linked_line in line.linked_line_ids:
                lp = linked_line.product_id.with_context(
                    lang=lang,
                    display_default_code=False,
                )
                parts.append(_("Option: %s", lp.display_name))
        text = "\n".join(p for p in parts if p)
        raw_stripped = "\n".join((line.name or "").splitlines()).strip()
        if raw_stripped:
            std = "\n".join(
                (
                    line._get_sale_order_line_multiline_description_sale() or ""
                ).splitlines()
            ).strip()
            if raw_stripped != std:
                if std and raw_stripped.startswith(std):
                    extra = raw_stripped[len(std) :].strip().lstrip("\n").strip()
                    if extra:
                        text = f"{text}\n{extra}" if text else extra
                else:
                    cleaned_raw = line._l10n_ve_strip_default_code_prefix(raw_stripped)
                    text = f"{text}\n{cleaned_raw}" if text else cleaned_raw
        if not (text or "").strip():
            text = (product.display_name or "").strip()
        return plaintext2html(text, with_paragraph=False)

    def _l10n_ve_strip_default_code_prefix(self, text):
        self.ensure_one()
        if not text:
            return text
        lines = text.splitlines()
        first_line = lines[0].strip()
        if first_line.startswith("[") and "]" in first_line:
            first_line = first_line.split("]", 1)[1].strip()
            lines[0] = first_line
            return "\n".join(line for line in lines if line.strip()).strip()
        return text

    @api.constrains("discount", "order_id")
    def _l10n_ve_check_line_discount(self):
        prec = self.env["decimal.precision"].precision_get("Discount")
        for line in self:
            if line.display_type:
                continue
            if line.order_id.country_code != "VE":
                continue
            disc = line.discount or 0.0
            if float_compare(disc, 100.0, precision_digits=prec) >= 0:
                raise ValidationError(
                    _(
                        "No se permite un descuento del 100%% en la línea. "
                        'La línea "%(line)s" tiene %(discount)s%%.'
                    )
                    % {
                        "line": line.name or _("Sin nombre"),
                        "discount": disc,
                    }
                )

    @api.constrains(
        "price_unit", "product_id", "display_type", "order_id", "is_downpayment"
    )
    def _l10n_ve_check_line_unit_price(self):
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if line.display_type:
                continue
            if line.is_downpayment:
                continue
            if line.order_id.country_code != "VE":
                continue
            price = line.price_unit or 0.0
            if float_compare(price, 0.0, precision_digits=prec) <= 0:
                disc = line.order_id.company_id.sale_discount_product_id
                if line.product_id and line.product_id == disc:
                    continue
                raise ValidationError(
                    _(
                        "No se permiten líneas con precio menor o igual a cero. "
                        'La línea "%(line)s" tiene precio %(price)s. Use el asistente '
                        "Descuento en el pedido (producto de descuento de compañía) o "
                        "corrija el importe."
                    )
                    % {"line": line.name or _("Sin nombre"), "price": price}
                )

    @api.constrains("tax_id", "order_id")
    def _check_tax_single_required_ve(self):
        for line in self:
            if line.display_type:
                continue
            if line.order_id.state != "sale":
                continue
            if line.order_id.country_code != "VE":
                continue
            if len(line.tax_id) == 0:
                raise ValidationError(
                    _(
                        "No se puede quitar el impuesto de la línea '%s' en un pedido "
                        "confirmado. Cada línea debe tener exactamente un impuesto."
                    )
                    % (line.name or _("Sin nombre"))
                )
            if len(line.tax_id) > 1:
                tax_mapped = ", ".join(line.tax_id.mapped("name"))
                raise ValidationError(
                    _(
                        "No se puede asignar más de un impuesto a la línea "
                        "'%(line)s' en un pedido confirmado. Cree una línea "
                        "separada para cada impuesto. Impuestos actuales: "
                        "%(taxes)s"
                    )
                    % {
                        "line": line.name or _("Sin nombre"),
                        "taxes": tax_mapped,
                    }
                )
