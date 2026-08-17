# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, float_is_zero, float_round


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l10n_ve_inverse_rate = fields.Float(
        string="Tasa de cambio inversa",
        compute="_compute_l10n_ve_inverse_rate",
        digits=(16, 6),
    )
    l10n_ve_seniat_note = fields.Html(
        string="Nota SENIAT",
        compute="_compute_l10n_ve_seniat_note",
        sanitize=False,
    )
    l10n_ve_hide_order_preview = fields.Boolean(
        compute="_compute_l10n_ve_hide_order_preview",
    )

    @api.depends("country_code", "journal_id", "journal_id.l10n_ve_emission_medium")
    def _compute_l10n_ve_hide_order_preview(self):
        for order in self:
            order.l10n_ve_hide_order_preview = (
                order.country_code == "VE"
                and order.journal_id.l10n_ve_emission_medium == "fiscal_machine"
            )

    def action_preview_sale_order(self):
        for order in self:
            if order.l10n_ve_hide_order_preview:
                raise UserError(
                    _(
                        "En maquina fiscal no esta permitida la vista previa "
                        "del pedido."
                    )
                )
        return super().action_preview_sale_order()

    @api.depends("currency_id", "date_order", "company_id")
    def _compute_l10n_ve_inverse_rate(self):
        for order in self:
            if not order.currency_id or not order.company_id:
                order.l10n_ve_inverse_rate = 0.0
                continue
            date_ref = (order.date_order or fields.Datetime.now()).date()
            if order.currency_id == order.company_id.currency_id:
                order.l10n_ve_inverse_rate = 1.0
                continue
            currency_rate = self.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", order.currency_id.id),
                    ("name", "<=", date_ref),
                    ("company_id", "=", order.company_id.id),
                ],
                order="name desc",
                limit=1,
            )
            if currency_rate and currency_rate.rate and currency_rate.rate != 0.0:
                order.l10n_ve_inverse_rate = 1.0 / currency_rate.rate
            else:
                order.l10n_ve_inverse_rate = 0.0

    @api.depends(
        "company_id",
        "company_id.taxpayer_type",
        "l10n_ve_inverse_rate",
        "country_code",
        "currency_id",
    )
    def _compute_l10n_ve_seniat_note(self):
        for order in self:
            if order.country_code != "VE":
                order.l10n_ve_seniat_note = False
                continue
            texts = []
            if order.company_id._l10n_ve_invoice_tag_include_igtf_notice():
                texts.append(
                    "<span>Este pago estará sujeto al cobro adicional del 3% del "
                    "Impuesto a las Grandes Transacciones Financieras (IGTF), de "
                    "conformidad con la Providencia Administrativa SNAT/2022/000013 "
                    "publicada en la G.O N 42.339 del 17-03-2022, en caso de ser "
                    "cancelado en divisas. No aplica en pago en Bs.</span> "
                )
            if order.company_id.currency_id != order.currency_id:
                rate_formatted = order.company_id.currency_id.format(
                    order.l10n_ve_inverse_rate
                )
                texts.append(
                    "<span>Este documento se expresa en Bolívares con su "
                    "equivalente en Divisas, al tipo de cambio corriente del "
                    "mercado a la fecha de su emisión, según lo establecido en "
                    "el articulo 13 numeral 14 de la providencia administrativa "
                    "SNAT/2011/0071 "
                    f"({rate_formatted}) en concordancia con el articulo 128 "
                    "de la Ley del Banco Central de Venezuela (BCV); articulo 15 "
                    "de la Ley que establece el impuesto al valor agregado (IVA) "
                    "y 38 del Reglamento General de la Ley que establece el "
                    "Impuesto de Valor agregado (RLIVA)</span>"
                )
            order.l10n_ve_seniat_note = "".join(texts) if texts else False

    @api.depends("company_id")
    def _compute_journal_id(self):
        non_ve = self.filtered(lambda o: o.country_code != "VE")
        super(SaleOrder, non_ve)._compute_journal_id()
        for order in self - non_ve:
            if not order.journal_id:
                order.journal_id = order._l10n_ve_default_sale_journal()

    def _l10n_ve_default_sale_journal(self):
        self.ensure_one()
        return self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
            ],
            order="sequence asc, id asc",
            limit=1,
        )

    def _l10n_ve_get_product_discount_lines(self):
        self.ensure_one()
        disc = self.company_id.sale_discount_product_id
        if not disc:
            return self.env["sale.order.line"]
        return self.order_line.filtered(
            lambda line: not line.display_type and line.product_id == disc
        )

    def action_l10n_ve_remove_global_discount(self, discount_id):
        self.ensure_one()
        line = self.env["sale.order.line"].browse(discount_id)
        if line.exists() and line in self._l10n_ve_get_product_discount_lines():
            line.unlink()
            return True
        raise UserError(_("El descuento no pertenece a este pedido."))

    def action_l10n_ve_remove_all_global_discounts(self):
        self.ensure_one()
        product_lines = self._l10n_ve_get_product_discount_lines()
        if len(product_lines) <= 1:
            return True
        product_lines.unlink()
        return True

    def _l10n_ve_on_before_create_invoices(self):
        pass

    def _l10n_ve_should_use_discount_line_allocation(self, discount_alloc):
        return bool(discount_alloc)

    def _l10n_ve_after_invoice_chunk(self, moves, discount_alloc):
        pass

    def _l10n_ve_product_order_lines(self, lines=None):
        lines = lines or self.order_line
        disc = self.company_id.sale_discount_product_id
        return lines.filtered(
            lambda line: (
                not line.display_type
                and not line.is_downpayment
                and (not disc or line.product_id != disc)
            )
        )

    def _l10n_ve_product_subtotal(self, lines, qty_field="product_uom_qty"):
        self.ensure_one()
        subtotal = 0.0
        for line in lines:
            if line.display_type or line.is_downpayment:
                continue
            qty = getattr(line, qty_field, 0.0)
            rounding = line.product_uom.rounding if line.product_uom else 1e-9
            if float_is_zero(qty, precision_rounding=rounding):
                continue
            price_reduce = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            subtotal += price_reduce * qty
        return subtotal

    def _l10n_ve_subtotal_by_taxes_from_base_lines(self, base_lines):
        AccountTax = self.env["account.tax"]
        product_lines = self._l10n_ve_product_base_lines_for_discount(base_lines)
        lines_needing_details = [
            base_line for base_line in product_lines if not base_line.get("tax_details")
        ]
        if lines_needing_details:
            AccountTax._add_tax_details_in_base_lines(lines_needing_details, self.company_id)
        totals = defaultdict(float)
        for base_line in product_lines:
            taxes = base_line["tax_ids"].filtered(
                lambda tax: tax.amount_type != "fixed"
            )
            quantity = base_line.get("quantity") or 0.0
            if float_is_zero(quantity, precision_rounding=1e-9):
                continue
            tax_details = base_line.get("tax_details") or {}
            if "total_excluded_currency" in tax_details:
                line_subtotal = tax_details["total_excluded_currency"]
            elif "raw_total_excluded_currency" in tax_details:
                line_subtotal = tax_details["raw_total_excluded_currency"]
            else:
                price_unit = base_line.get("price_unit") or 0.0
                discount = base_line.get("discount") or 0.0
                price_reduce = price_unit * (1 - discount / 100.0)
                line_subtotal = price_reduce * quantity
            totals[taxes] += line_subtotal
        return totals

    def _l10n_ve_product_base_lines_for_discount(self, base_lines):
        return [
            base_line
            for base_line in base_lines
            if not base_line.get("special_type")
        ]

    def _l10n_ve_non_product_base_lines(self, base_lines):
        return [
            base_line
            for base_line in base_lines
            if base_line.get("special_type") in ("early_payment", "cash_rounding")
        ]

    def _l10n_ve_get_max_invoice_lines_from_book(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal:
            return 0
        if journal.l10n_ve_emission_medium == "fiscal_machine":
            return 0
        book = journal.l10n_ve_invoice_section_id.book_id
        if journal.l10n_ve_emission_medium == "free" and book:
            return max(book.l10n_ve_max_invoice_lines or 10, 1)
        if journal.l10n_ve_emission_medium not in ("free", "fiscal_machine"):
            return journal._l10n_ve_journal_invoice_line_limit()
        return 0

    def _l10n_ve_global_discount_lines(self, invoiceable_lines):
        self.ensure_one()
        disc = self.company_id.sale_discount_product_id
        if not disc:
            return self.env["sale.order.line"]
        return invoiceable_lines.filtered(
            lambda line: not line.display_type
            and not line.is_downpayment
            and line.product_id == disc
        )

    def _l10n_ve_split_amount_by_weights(self, amount, weights):
        self.ensure_one()
        if not weights:
            return []
        if len(weights) == 1:
            return [amount]
        total_weight = sum(weights)
        if float_is_zero(total_weight, precision_rounding=1e-9):
            return [0.0] * len(weights)
        prec = self.currency_id.decimal_places
        out = []
        acc = 0.0
        for weight in weights[:-1]:
            part = float_round(amount * weight / total_weight, precision_digits=prec)
            out.append(part)
            acc += part
        out.append(float_round(amount - acc, precision_digits=prec))
        return out

    def _l10n_ve_chunk_subtotal_for_discount(self, chunk_lines, discount_line):
        self.ensure_one()
        disc = self.company_id.sale_discount_product_id
        disc_taxes = discount_line.tax_id.flatten_taxes_hierarchy().filtered(
            lambda tax: tax.amount_type != "fixed"
        )
        subtotal = 0.0
        for line in chunk_lines:
            if line.display_type or line.is_downpayment:
                continue
            if disc and line.product_id == disc:
                continue
            line_taxes = line.tax_id.flatten_taxes_hierarchy().filtered(
                lambda tax: tax.amount_type != "fixed"
            )
            if line_taxes != disc_taxes:
                continue
            qty = line.qty_to_invoice
            if float_is_zero(qty, precision_rounding=line.product_uom.rounding):
                continue
            price_reduce = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            subtotal += price_reduce * qty
        return subtotal

    def _l10n_ve_product_line_count_invoiceable(self, invoiceable_lines):
        disc = self.company_id.sale_discount_product_id

        def _is_counted_product_line(line):
            if line.display_type or line.is_downpayment:
                return False
            if disc and line.product_id == disc:
                return False
            return True

        return len(invoiceable_lines.filtered(_is_counted_product_line))

    def _l10n_ve_split_invoiceable_lines(self, invoiceable_lines, max_lines):
        self.ensure_one()
        lines = invoiceable_lines.sorted(key=lambda line: (line.sequence, line.id))
        chunks = []
        buf_ids = []
        prod_in_buf = 0
        pending_header_ids = []
        down_ids = []
        for line in lines:
            if line.is_downpayment:
                down_ids.append(line.id)
                continue
            if line.display_type in ("line_section", "line_note"):
                pending_header_ids.append(line.id)
                continue
            if prod_in_buf >= max_lines and buf_ids:
                chunks.append(buf_ids)
                buf_ids = []
                prod_in_buf = 0
            if pending_header_ids:
                buf_ids.extend(pending_header_ids)
                pending_header_ids = []
            buf_ids.append(line.id)
            prod_in_buf += 1
        if pending_header_ids:
            buf_ids.extend(pending_header_ids)
        if buf_ids:
            chunks.append(buf_ids)
        if down_ids:
            if chunks:
                chunks[-1].extend(down_ids)
            else:
                chunks.append(down_ids)
        return [invoiceable_lines.browse(ids) for ids in chunks]

    def _l10n_ve_chunk_product_subtotal(self, chunk_lines):
        return self._l10n_ve_product_subtotal(
            chunk_lines,
            qty_field="qty_to_invoice",
        )

    def _l10n_ve_invoiceable_line_chunks(self, final):
        self.ensure_one()
        invoiceable_lines = super()._get_invoiceable_lines(final)
        return self._l10n_ve_invoiceable_line_chunks_legacy(invoiceable_lines, final)

    def _l10n_ve_invoiceable_line_chunks_legacy(self, invoiceable_lines, final):
        self.ensure_one()
        max_lines = self._l10n_ve_get_max_invoice_lines_from_book()
        if (
            max_lines <= 0
            or self._l10n_ve_product_line_count_invoiceable(invoiceable_lines) <= max_lines
        ):
            return [(invoiceable_lines, {})]
        disc_lines = self._l10n_ve_global_discount_lines(invoiceable_lines)
        lines_wo_disc = invoiceable_lines - disc_lines
        core_chunks = self._l10n_ve_split_invoiceable_lines(lines_wo_disc, max_lines)
        out = []
        chunk_weights_by_discount = {}
        for dline in disc_lines:
            qty = dline.qty_to_invoice
            if float_is_zero(qty, precision_rounding=dline.product_uom.rounding):
                continue
            weights = [
                self._l10n_ve_chunk_subtotal_for_discount(chunk, dline)
                for chunk in core_chunks
            ]
            if float_is_zero(sum(weights), precision_rounding=1e-9):
                continue
            total_disc = abs(dline.price_unit * qty)
            chunk_weights_by_discount[dline.id] = self._l10n_ve_split_amount_by_weights(
                total_disc, weights
            )
        for i, chunk in enumerate(core_chunks):
            alloc = {}
            extra_ids = []
            for dline in disc_lines:
                parts = chunk_weights_by_discount.get(dline.id)
                if not parts:
                    continue
                part = parts[i]
                if float_is_zero(
                    part, precision_rounding=10 ** (-self.currency_id.decimal_places)
                ):
                    continue
                alloc[dline.id] = part
                extra_ids.append(dline.id)
            out.append(
                (
                    chunk | self.env["sale.order.line"].browse(extra_ids),
                    alloc,
                )
            )
        return out

    def _get_invoiceable_lines(self, final=False):
        lines = super()._get_invoiceable_lines(final)
        ids_ctx = self.env.context.get("l10n_ve_invoiceable_line_ids")
        if ids_ctx is not None:
            id_set = set(ids_ctx)
            lines = lines.filtered(lambda line: line.id in id_set)
        return lines

    def action_l10n_ve_create_invoice(self):
        orders = self.filtered(lambda order: order.country_code == "VE")
        if not orders:
            raise UserError(
                _("Este flujo solo aplica a pedidos de ventas venezolanos.")
            )
        invoices = orders._create_invoices(final=True, grouped=False)
        return orders.action_view_invoice(invoices=invoices)

    def action_l10n_ve_fix_discount_invoicing_rounding(self):
        orders = self.filtered(
            lambda order: order.state in ("sale", "done") and order.country_code == "VE"
        )
        if not orders:
            candidates = self.search(
                [
                    ("state", "in", ("sale", "done")),
                    ("invoice_status", "=", "to invoice"),
                ]
            )
            orders = candidates.filtered(lambda order: order.country_code == "VE")
        if not orders:
            raise UserError(
                _("No hay pedidos venezolanos confirmados pendientes de corrección.")
            )
        fixed_lines = orders.order_line._l10n_ve_fix_discount_invoicing_rounding()
        fixed_orders = fixed_lines.order_id
        if not fixed_orders:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Sin cambios"),
                    "message": _(
                        "Ningún pedido requirió corrección de redondeo en líneas de descuento."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Corrección aplicada"),
                "message": _(
                    "Se corrigieron %(lines)s línea(s) de descuento en %(orders)s pedido(s): %(names)s",
                    lines=len(fixed_lines),
                    orders=len(fixed_orders),
                    names=", ".join(fixed_orders.mapped("name")),
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def _create_invoices(self, grouped=False, final=False, date=None):
        if not self.env["account.move"].has_access("create"):
            try:
                self.check_access("write")
            except AccessError:
                return self.env["account.move"]
        ve = self.filtered(lambda o: o.country_code == "VE")
        non_ve = self - ve
        moves = (
            non_ve._create_invoices(grouped=grouped, final=final, date=date)
            if non_ve
            else self.env["account.move"]
        )
        for order in ve:
            order._l10n_ve_on_before_create_invoices()
            chunk_specs = order._l10n_ve_invoiceable_line_chunks(final)
            if len(chunk_specs) <= 1:
                chunk, discount_alloc = chunk_specs[0]
                ctx = {}
                if chunk != order._get_invoiceable_lines(final):
                    ctx["l10n_ve_invoiceable_line_ids"] = tuple(chunk.ids)
                if order._l10n_ve_should_use_discount_line_allocation(discount_alloc):
                    ctx["l10n_ve_discount_amount_allocation"] = discount_alloc
                chunk_moves = super(
                    SaleOrder, order.with_context(**ctx)
                )._create_invoices(grouped=False, final=final, date=date)
                order._l10n_ve_after_invoice_chunk(chunk_moves, discount_alloc)
                moves |= chunk_moves
            else:
                for chunk, discount_alloc in chunk_specs:
                    ctx = {"l10n_ve_invoiceable_line_ids": tuple(chunk.ids)}
                    if order._l10n_ve_should_use_discount_line_allocation(discount_alloc):
                        ctx["l10n_ve_discount_amount_allocation"] = discount_alloc
                    chunk_moves = super(
                        SaleOrder,
                        order.with_context(**ctx),
                    )._create_invoices(grouped=False, final=final, date=date)
                    order._l10n_ve_after_invoice_chunk(chunk_moves, discount_alloc)
                    moves |= chunk_moves
        return moves

    def _l10n_ve_check_free_emission_correlatives(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal:
            return
        if journal.l10n_ve_emission_medium != "free":
            return
        if not journal.l10n_ve_invoice_section_id:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: el diario de ventas «%(journal)s» "
                    "está en «forma libre» (correlativo de talonario) y debe tener "
                    "configurado el tramo SENIAT de facturas de cliente."
                )
                % {"journal": journal.display_name}
            )
        if "warehouse_id" not in self._fields:
            return
        if "stock.warehouse" not in self.env:
            return
        Warehouse = self.env["stock.warehouse"]
        if "l10n_ve_dispatch_guide_section_id" not in Warehouse._fields:
            return
        warehouse = self.warehouse_id
        if not warehouse:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: indique el almacén para validar "
                    "el correlativo de guía de despacho (SENIAT)."
                )
            )
        if not warehouse.l10n_ve_dispatch_guide_section_id:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: con diario en «forma libre» debe "
                    "configurar en el almacén «%(warehouse)s» el tramo del talonario "
                    "para guías de despacho (SENIAT)."
                )
                % {"warehouse": warehouse.display_name}
            )

    def action_confirm(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for order in self:
            if float_is_zero(order.amount_total, precision_digits=order.currency_id.decimal_places):
                raise UserError(
                    "No se puede confirmar el pedido con un total de 0. "
                    "Agregue productos con precio o corrija los importes."
                )
            invalid_lines = order.order_line.filtered(
                lambda line: not line.display_type and float_is_zero(line.price_unit, precision_digits=precision)
            )
            if invalid_lines:
                products = [
                    line.product_id.display_name if line.product_id else line.name
                    for line in invalid_lines
                ]
                raise UserError(
                    "No se puede confirmar el pedido con líneas en precio 0. "
                    "Corrija los precios de los siguientes productos: %s"
                    % ", ".join(products)
                )
            invalid_qty_lines = order.order_line.filtered(
                lambda line: (
                    not line.display_type
                    and not line.is_downpayment
                    and float_compare(
                        line.product_uom_qty,
                        0.0,
                        precision_rounding=line.product_uom.rounding,
                    )
                    <= 0
                )
            )
            if invalid_qty_lines:
                products = [
                    line.product_id.display_name if line.product_id else line.name
                    for line in invalid_qty_lines
                ]
                raise UserError(
                    _(
                        "No se puede confirmar el pedido con líneas en cantidad 0 o negativa. "
                        "Corrija las cantidades de los siguientes productos: %s"
                    )
                    % ", ".join(products)
                )
            if order.country_code == "VE":
                if not order.journal_id:
                    raise UserError(
                        _("Debe indicar el diario de ventas antes de confirmar el pedido.")
                    )
                order._l10n_ve_check_free_emission_correlatives()
                default_tax = order.company_id.account_sale_tax_id
                for line in order.order_line.filtered(lambda line: not line.display_type):
                    if len(line.tax_id) == 0:
                        if default_tax:
                            line.tax_id = [Command.link(default_tax.id)]
                            order.message_post(
                                body=_("Se agregó el impuesto por defecto a la línea: %s.")
                                % (line.name or _("Sin nombre"))
                            )
                        else:
                            raise UserError(
                                _(
                                    "La línea '%s' no tiene impuesto asignado. "
                                    "Asigne un impuesto o configure el impuesto de venta por defecto en la compañía."
                                )
                                % (line.name or _("Sin nombre"))
                            )
                lines_with_multi_tax = []
                for line in order.order_line.filtered(lambda line: not line.display_type):
                    if len(line.tax_id) > 1:
                        tax_mapped = ", ".join(line.tax_id.mapped("name"))
                        lines_with_multi_tax.append(" - %s: %s" % (line.name or _("Sin nombre"), tax_mapped))
                if lines_with_multi_tax:
                    raise UserError(
                        _(
                            "No se puede asignar más de un impuesto a una sola línea de pedido. "
                            "Cree líneas separadas para cada impuesto.\n%s"
                        )
                        % "\n".join(lines_with_multi_tax)
                    )
        return super().action_confirm()
