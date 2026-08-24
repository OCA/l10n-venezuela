import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        compute="_compute_invoice_ids",
        string="Invoices",
        copy=False,
    )

    l10n_ve_is_ve_country = fields.Boolean(
        compute="_compute_l10n_ve_is_ve_country",
    )
    l10n_ve_dispatch_guide_enabled = fields.Boolean(
        related="company_id.l10n_ve_dispatch_guide_enabled",
        readonly=True,
    )
    l10n_ve_internal_transfer_reason_id = fields.Many2one(
        "l10n_ve.stock.transfer.reason",
        string="Motivo de traslado",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Motivo del traslado de los bienes muebles en albaranes internos o en "
        "entregas sin pedido de venta, según el Artículo 10, numeral 4, de la "
        "Providencia Administrativa del SENIAT.",
    )
    l10n_ve_dispatch_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Lista de precios (guía)",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Obligatoria en la guía cuando el albarán no proviene de un "
        "pedido de venta.",
    )
    l10n_ve_dispatch_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda total (guía)",
        default=lambda self: self.env.company.currency_id,
    )
    l10n_ve_dispatch_amount_total = fields.Monetary(
        string="Total con impuestos (guía)",
        currency_field="l10n_ve_dispatch_currency_id",
        help="Total documental con impuestos cuando no hay pedido de venta "
        "(multimoneda).",
    )
    l10n_ve_dispatch_display_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_l10n_ve_dispatch_display_prices",
    )
    l10n_ve_dispatch_display_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="l10n_ve_dispatch_display_currency_id",
        compute="_compute_l10n_ve_dispatch_display_prices",
    )
    l10n_ve_dispatch_display_discount = fields.Monetary(
        string="Descuento",
        currency_field="l10n_ve_dispatch_display_currency_id",
        compute="_compute_l10n_ve_dispatch_display_prices",
    )
    l10n_ve_dispatch_display_total = fields.Monetary(
        string="Total",
        currency_field="l10n_ve_dispatch_display_currency_id",
        compute="_compute_l10n_ve_dispatch_display_prices",
    )
    l10n_ve_dispatch_guide_original_printed = fields.Boolean(
        copy=False,
    )
    l10n_ve_control_number = fields.Char(
        string="N° de control",
        copy=False,
        tracking=True,
    )
    l10n_ve_control_number_placeholder = fields.Char(
        string="Próximo N° de control (previsto)",
        compute="_compute_l10n_ve_control_number_placeholder",
        readonly=True,
    )
    l10n_ve_show_control_number_ui = fields.Boolean(
        compute="_compute_l10n_ve_show_control_number_ui",
    )
    l10n_ve_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    l10n_ve_fleet_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehículo",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    l10n_ve_sales_user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        related="sale_id.user_id",
        readonly=True,
    )
    l10n_ve_partner_contact_phone_display = fields.Char(
        string="Teléfono (contacto)",
        compute="_compute_l10n_ve_partner_contact_phone_display",
    )
    l10n_ve_dispatch_guide_date = fields.Date(
        string="Fecha guía",
        compute="_compute_l10n_ve_dispatch_guide_listing_data",
        store=True,
    )
    l10n_ve_dispatch_guide_time = fields.Char(
        string="Hora guía",
        compute="_compute_l10n_ve_dispatch_guide_listing_data",
        store=True,
    )
    l10n_ve_dispatch_guide_user_id = fields.Many2one(
        "res.users",
        string="Usuario guía",
        compute="_compute_l10n_ve_dispatch_guide_listing_data",
        store=True,
    )

    @api.depends("date_done", "write_uid", "state")
    def _compute_l10n_ve_dispatch_guide_listing_data(self):
        for picking in self:
            if picking.state == "done" and picking.date_done:
                localized = fields.Datetime.context_timestamp(
                    picking, picking.date_done
                )
                picking.l10n_ve_dispatch_guide_date = localized.date()
                picking.l10n_ve_dispatch_guide_time = localized.strftime("%H:%M")
                picking.l10n_ve_dispatch_guide_user_id = picking.write_uid
            else:
                picking.l10n_ve_dispatch_guide_date = False
                picking.l10n_ve_dispatch_guide_time = False
                picking.l10n_ve_dispatch_guide_user_id = False

    @api.depends("partner_id", "partner_id.phone", "partner_id.mobile")
    def _compute_l10n_ve_partner_contact_phone_display(self):
        for picking in self:
            p = picking.partner_id
            if not p:
                picking.l10n_ve_partner_contact_phone_display = False
            else:
                picking.l10n_ve_partner_contact_phone_display = (
                    p.phone or p.mobile or False
                )

    def _l10n_ve_requires_internal_transfer_reason(self):
        """Motivo SENIAT: internos siempre; salidas sin pedido de venta (ni POS)."""
        self.ensure_one()
        if not self.l10n_ve_dispatch_guide_enabled:
            return False
        if self.return_id:
            return False
        if self.picking_type_id.code == "internal":
            return True
        if self.picking_type_id.code != "outgoing" or self.sale_id:
            return False
        if "pos_order_id" in self._fields and self.pos_order_id:
            return False
        return True

    @api.depends(
        "move_ids",
        "move_ids.invoice_line_ids",
        "move_ids.invoice_line_ids.move_id",
    )
    def _compute_invoice_ids(self):
        for picking in self:
            amls = picking.move_ids.invoice_line_ids
            picking.invoice_ids = amls.move_id

    @api.depends("company_id.account_fiscal_country_id")
    def _compute_l10n_ve_is_ve_country(self):
        for record in self:
            record.l10n_ve_is_ve_country = (
                record.company_id.account_fiscal_country_id
                and record.company_id.account_fiscal_country_id.code == "VE"
            )

    @api.depends(
        "picking_type_id",
        "company_id",
        "company_id.account_fiscal_country_id",
        "move_ids",
        "move_ids.product_id",
        "move_ids.l10n_ve_dispatch_subtotal",
        "move_ids.l10n_ve_dispatch_price_total",
        "move_ids.l10n_ve_dispatch_currency_id",
        "company_id.l10n_ve_dispatch_guide_enabled",
        "sale_id",
        "sale_id.amount_total",
        "sale_id.amount_untaxed",
        "sale_id.currency_id",
        "sale_id.tax_totals",
        "l10n_ve_dispatch_amount_total",
        "l10n_ve_dispatch_currency_id",
        "scheduled_date",
    )
    def _compute_l10n_ve_dispatch_display_prices(self):
        for picking in self:
            picking.l10n_ve_dispatch_display_currency_id = (
                picking.company_id.currency_id
            )
            picking.l10n_ve_dispatch_display_subtotal = 0.0
            picking.l10n_ve_dispatch_display_discount = 0.0
            picking.l10n_ve_dispatch_display_total = 0.0
            if picking.picking_type_id.code != "outgoing":
                continue
            if not picking.l10n_ve_dispatch_guide_enabled:
                continue
            if not picking.l10n_ve_is_ve_country:
                continue
            company = picking.company_id
            date = picking.scheduled_date or fields.Date.context_today(picking)
            moves = picking.move_ids.filtered("product_id")
            if picking.sale_id:
                total_cur = picking.sale_id.currency_id
                picking.l10n_ve_dispatch_display_currency_id = total_cur
                picking.l10n_ve_dispatch_display_total = picking.sale_id.amount_total
                subtotal_sum = 0.0
                for move in moves:
                    cur = move.l10n_ve_dispatch_currency_id
                    subtotal_sum += cur._convert(
                        move.l10n_ve_dispatch_subtotal,
                        total_cur,
                        company,
                        date,
                    )
                picking.l10n_ve_dispatch_display_subtotal = subtotal_sum
                picking.l10n_ve_dispatch_display_discount = (
                    picking._l10n_ve_dispatch_guide_discount_amount(
                        picking_subtotal=subtotal_sum
                    )
                )
            else:
                total_cur = picking.l10n_ve_dispatch_currency_id or company.currency_id
                picking.l10n_ve_dispatch_display_currency_id = total_cur
                subtotal_sum = 0.0
                total_lines = 0.0
                for move in moves:
                    cur = move.l10n_ve_dispatch_currency_id
                    subtotal_sum += cur._convert(
                        move.l10n_ve_dispatch_subtotal,
                        total_cur,
                        company,
                        date,
                    )
                    total_lines += cur._convert(
                        move.l10n_ve_dispatch_price_total,
                        total_cur,
                        company,
                        date,
                    )
                manual = picking.l10n_ve_dispatch_amount_total
                picking.l10n_ve_dispatch_display_subtotal = subtotal_sum
                picking.l10n_ve_dispatch_display_total = (
                    manual if manual else total_lines
                )

    @api.constrains(
        "company_id",
        "picking_type_id",
        "l10n_ve_internal_transfer_reason_id",
        "state",
        "sale_id",
    )
    def _check_l10n_ve_internal_transfer_reason(self):
        for picking in self:
            if picking.state == "draft":
                continue
            if picking.company_id.account_fiscal_country_id.code != "VE":
                continue
            if not picking._l10n_ve_requires_internal_transfer_reason():
                continue
            if not picking.l10n_ve_internal_transfer_reason_id:
                raise ValidationError(
                    _(
                        "En albaranes internos o en entregas sin pedido de venta "
                        "venezolanos debe indicar el motivo de traslado."
                    )
                )

    def _l10n_ve_dispatch_needs_manual_pricing(self):
        self.ensure_one()
        if self.sale_id:
            return False
        if any(m.sale_line_id for m in self.move_ids if m.product_id):
            return False
        return bool(self.move_ids.filtered("product_id"))

    def _l10n_ve_dispatch_guide_print_available(self):
        self.ensure_one()
        if not self._l10n_ve_is_ve_outgoing_dispatch_guide_picking():
            return False
        if self.state != "done":
            return False
        if (
            self._l10n_ve_requires_internal_transfer_reason()
            and not self.l10n_ve_internal_transfer_reason_id
        ):
            return False
        if self._l10n_ve_dispatch_needs_manual_pricing() and (
            not self.l10n_ve_dispatch_pricelist_id
            or not self.l10n_ve_dispatch_currency_id
        ):
            return False
        return True

    def l10n_ve_dispatch_guide_report_check(self):
        for picking in self:
            if not picking.l10n_ve_dispatch_guide_enabled:
                continue
            if picking.company_id.account_fiscal_country_id.code != "VE":
                continue
            if (
                picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
                and picking.state != "done"
            ):
                raise UserError(
                    _("Confirme la entrega antes de imprimir la guía de despacho.")
                )
            if picking._l10n_ve_requires_internal_transfer_reason():
                if not picking.l10n_ve_internal_transfer_reason_id:
                    raise UserError(
                        _("Indique el motivo de traslado antes de imprimir la guía.")
                    )
            if not picking._l10n_ve_dispatch_needs_manual_pricing():
                continue
            if not picking.l10n_ve_dispatch_pricelist_id:
                raise UserError(
                    _(
                        "Seleccione la lista de precios para la guía "
                        "(albarán sin pedido de venta vinculado)."
                    )
                )
            if not picking.l10n_ve_dispatch_currency_id:
                raise UserError(
                    _("Indique la moneda del total con impuestos para la guía.")
                )

    def _l10n_ve_dispatch_origin_partner(self):
        self.ensure_one()
        wh = self.picking_type_id.warehouse_id or self.location_id.warehouse_id
        if wh and wh.partner_id:
            return wh.partner_id
        return self.company_id.partner_id

    def _l10n_ve_dispatch_dest_partner(self):
        self.ensure_one()
        if self.picking_type_code == "outgoing" and self.partner_id:
            return self.partner_id.commercial_partner_id
        wh = self.location_dest_id.warehouse_id
        if wh and wh.partner_id:
            return wh.partner_id
        if self.partner_id:
            return self.partner_id.commercial_partner_id
        return self.company_id.partner_id

    def _l10n_ve_dispatch_address_inline(self, partner):
        if not partner:
            return ""
        text = partner.sudo()._display_address(without_company=True)
        return re.sub(r"\n(\s|\n)*", ", ", text).strip().strip(",")

    def _l10n_ve_dispatch_partner_contact_phone(self):
        self.ensure_one()
        p = self.partner_id
        if not p:
            return ""
        return p.phone or p.mobile or ""

    def _l10n_ve_dispatch_fleet_vehicle_model_name(self):
        self.ensure_one()
        vehicle = self.l10n_ve_fleet_vehicle_id
        if not vehicle or not vehicle.model_id:
            return ""
        return vehicle.model_id.display_name or vehicle.model_id.name or ""

    def _l10n_ve_dispatch_delivery_address_partner(self):
        self.ensure_one()
        if self.picking_type_code == "outgoing" and self.partner_id:
            return self.partner_id
        return self._l10n_ve_dispatch_dest_partner()

    def _l10n_ve_dispatch_guide_lines(self):
        self.ensure_one()
        lines = []
        for move in self.move_ids:
            if not move.product_id:
                continue
            qty = move.quantity if move.state == "done" else move.product_uom_qty
            product = move.product_id
            wt = qty * product.weight if product.weight else 0.0
            vol = qty * product.volume if product.volume else 0.0
            weight_line = (
                f"{wt:.2f} {product.weight_uom_name}" if product.weight else "—"
            )
            volume_line = (
                f"{vol:.4f} {product.volume_uom_name}" if product.volume else "—"
            )
            pv = move._l10n_ve_dispatch_line_pricing_values()
            price_unit = pv["price_unit"]
            price_currency = pv["currency"]
            subtotal = pv["subtotal"]
            lines.append(
                {
                    "default_code": product.default_code or "",
                    "name": product.with_context(
                        display_default_code=False
                    ).display_name,
                    "weight_line": weight_line,
                    "volume_line": volume_line,
                    "quantity": qty,
                    "uom_name": move.product_uom.name,
                    "price_unit": price_unit,
                    "currency": price_currency,
                    "subtotal": subtotal,
                }
            )
        return lines

    def _l10n_ve_dispatch_guide_total_display(self):
        self.ensure_one()
        if self.sale_id:
            return self.sale_id.amount_total, self.sale_id.currency_id
        return (
            self.l10n_ve_dispatch_amount_total,
            self.l10n_ve_dispatch_currency_id or self.company_id.currency_id,
        )

    def _l10n_ve_dispatch_guide_sale_discount_amount(self):
        """Return the sale order global discount amount in order currency.

        Uses tax totals (SENIAT discounts or product discount lines).
        """
        self.ensure_one()
        order = self.sale_id
        if not order:
            return 0.0
        tax_totals = order.tax_totals or {}
        if tax_totals.get("l10n_ve_show_global_discount"):
            return tax_totals.get("l10n_ve_global_discount_amount_currency", 0.0) or 0.0
        if "l10n_ve_global_discount_ids" in order._fields:
            discounts = order.l10n_ve_global_discount_ids
            if discounts:
                return sum(discounts.mapped("amount"))
        disc_product = False
        if "sale_discount_product_id" in order.company_id._fields:
            disc_product = order.company_id.sale_discount_product_id
        if disc_product:
            disc_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id == disc_product
            )
            if disc_lines:
                return abs(sum(disc_lines.mapped("price_subtotal")))
        return 0.0

    def _l10n_ve_dispatch_guide_discount_amount(self, picking_subtotal=None):
        """Allocate sale global discount proportionally to this picking subtotal."""
        self.ensure_one()
        order = self.sale_id
        if not order:
            return 0.0
        so_discount = self._l10n_ve_dispatch_guide_sale_discount_amount()
        currency = order.currency_id
        if float_is_zero(so_discount, precision_rounding=currency.rounding):
            return 0.0
        tax_totals = order.tax_totals or {}
        so_gross = tax_totals.get("l10n_ve_subtotal_gross_currency")
        if so_gross is None:
            so_gross = (order.amount_untaxed or 0.0) + so_discount
        if float_is_zero(so_gross, precision_rounding=currency.rounding):
            return 0.0
        if picking_subtotal is None:
            picking_subtotal = self.l10n_ve_dispatch_display_subtotal or 0.0
        ratio = min(picking_subtotal / so_gross, 1.0) if so_gross else 0.0
        return currency.round(so_discount * ratio)

    def _l10n_ve_dispatch_guide_discount_display(self):
        """Return (amount, currency, detail lines) for the dispatch guide report."""
        self.ensure_one()
        currency = self.l10n_ve_dispatch_display_currency_id or (
            self.sale_id.currency_id if self.sale_id else self.company_id.currency_id
        )
        amount = self.l10n_ve_dispatch_display_discount
        if float_is_zero(amount, precision_rounding=currency.rounding):
            return 0.0, currency, []
        lines = []
        order = self.sale_id
        if order:
            tax_totals = order.tax_totals or {}
            so_lines = tax_totals.get("l10n_ve_global_discount_lines") or []
            so_discount = self._l10n_ve_dispatch_guide_sale_discount_amount()
            ratio = (amount / so_discount) if so_discount else 0.0
            for line in so_lines:
                lines.append(
                    {
                        "id": line.get("id"),
                        "name": line.get("name") or _("Descuento"),
                        "amount": currency.round((line.get("amount") or 0.0) * ratio),
                        "discount_type": line.get("discount_type"),
                        "discount_percentage": line.get("discount_percentage"),
                    }
                )
            if not lines:
                lines = [{"id": False, "name": _("Descuento"), "amount": amount}]
        return amount, currency, lines

    def _l10n_ve_dispatch_outgoing_moves_fully_invoiced(self):
        """True if picking quantities are already covered by posted invoices."""
        self.ensure_one()
        Move = self.env["stock.move"]
        if "invoice_line_ids" not in Move._fields:
            return bool(self.invoice_ids)
        saw_product = False
        per_soline_qty = defaultdict(float)
        for move in self.move_ids:
            if (
                move.scrapped
                or not move.product_id
                or move.product_id.type == "service"
            ):
                continue
            qty_uom = move.quantity if move.state == "done" else move.product_uom_qty
            if float_is_zero(qty_uom, precision_rounding=move.product_uom.rounding):
                continue
            saw_product = True
            if not move.sale_line_id:
                return False
            sol = move.sale_line_id
            per_soline_qty[sol] += move.product_uom._compute_quantity(
                qty_uom,
                sol.product_uom,
                round=False,
            )

        if not saw_product:
            return False

        for sol, qty_pick in per_soline_qty.items():
            if self.state == "done":
                threshold = sol.qty_delivered
            else:
                threshold = sol.qty_delivered + qty_pick
            if (
                float_compare(
                    sol.qty_invoiced_posted,
                    threshold,
                    precision_rounding=sol.product_uom.rounding,
                )
                < 0
            ):
                return False
        return True

    def _l10n_ve_dispatch_requires_control_number(self):
        self.ensure_one()
        if not self.l10n_ve_dispatch_guide_enabled:
            return False
        if not self.l10n_ve_is_ve_country:
            return False
        if self.picking_type_id.code != "outgoing":
            return False
        if not self.sale_id:
            return False
        if self._l10n_ve_dispatch_outgoing_moves_fully_invoiced():
            return False
        return True

    def _l10n_ve_dispatch_guide_section(self):
        self.ensure_one()
        wh = self.picking_type_id.warehouse_id
        if not wh:
            return False
        return wh.l10n_ve_dispatch_guide_section_id

    def _l10n_ve_assign_dispatch_control_number(self):
        self.ensure_one()
        wh = self.picking_type_id.warehouse_id
        if wh and wh.company_id != self.company_id:
            raise ValidationError(
                _(
                    "El almacén del tipo de operación debe pertenecer a la misma "
                    "compañía que el albarán “%(picking)s”."
                )
                % {"picking": self.display_name}
            )
        section = self._l10n_ve_dispatch_guide_section()
        if not section:
            return
        book = section.book_id
        if section.company_id != self.company_id or book.company_id != self.company_id:
            raise ValidationError(
                _(
                    "El tramo de guía de despacho debe pertenecer a la misma compañía "
                    "que el albarán “%(picking)s”."
                )
                % {"picking": self.display_name}
            )
        with self.env.cr.savepoint():
            formatted = book.l10n_ve_allocate_correlative(section, self)
            self.write({"l10n_ve_control_number": formatted})

    @api.depends(
        "l10n_ve_control_number",
        "l10n_ve_is_ve_country",
        "picking_type_id",
        "sale_id",
        "state",
        "move_ids",
        "move_ids.state",
        "move_ids.quantity",
        "move_ids.product_uom_qty",
        "move_ids.sale_line_id",
        "move_ids.product_id",
        "invoice_ids",
        "company_id",
        "company_id.l10n_ve_dispatch_guide_enabled",
        "picking_type_id.warehouse_id.l10n_ve_dispatch_guide_section_id",
        "sale_id.order_line.qty_invoiced_posted",
        "sale_id.order_line.qty_delivered",
    )
    def _compute_l10n_ve_control_number_placeholder(self):
        for picking in self:
            picking.l10n_ve_control_number_placeholder = False
            if (picking.l10n_ve_control_number or "").strip():
                continue
            if not picking._l10n_ve_dispatch_requires_control_number():
                continue
            section = picking._l10n_ve_dispatch_guide_section()
            if not section:
                continue
            book = section.book_id
            picking.l10n_ve_control_number_placeholder = (
                book.l10n_ve_peek_next_formatted(section) or False
            )

    @api.depends(
        "l10n_ve_control_number",
        "l10n_ve_control_number_placeholder",
        "l10n_ve_is_ve_country",
        "picking_type_id",
        "state",
        "sale_id",
        "move_ids",
        "move_ids.state",
        "company_id.l10n_ve_dispatch_guide_enabled",
        "picking_type_id.warehouse_id.l10n_ve_dispatch_guide_section_id",
        "sale_id.order_line.qty_invoiced_posted",
        "sale_id.order_line.qty_delivered",
    )
    def _compute_l10n_ve_show_control_number_ui(self):
        for picking in self:
            picking.l10n_ve_show_control_number_ui = (
                picking._l10n_ve_should_show_control_number_ui()
            )

    def _l10n_ve_should_show_control_number_ui(self):
        self.ensure_one()
        if not self.l10n_ve_dispatch_guide_enabled:
            return False
        if not self.l10n_ve_is_ve_country:
            return False
        if self.picking_type_id.code == "internal":
            return False
        if (self.l10n_ve_control_number or "").strip():
            return True
        if self.l10n_ve_control_number_placeholder:
            return True
        return False

    def _l10n_ve_dispatch_guide_shows_company_header(self):
        self.ensure_one()
        if not self.l10n_ve_dispatch_guide_enabled:
            return False
        if self.picking_type_id.code != "outgoing" or not self.l10n_ve_is_ve_country:
            return False
        if (self.l10n_ve_control_number or "").strip():
            return False
        if self._l10n_ve_dispatch_requires_control_number():
            return False
        return True

    def _l10n_ve_dispatch_guide_paperformat(self):
        self.ensure_one()
        if self._l10n_ve_dispatch_guide_shows_company_header():
            return self.env.ref(
                "l10n_ve_stock.paperformat_l10n_ve_dispatch_guide_letter"
            )
        section = self._l10n_ve_dispatch_guide_section()
        if section and section.book_id:
            book = section.book_id.sudo()
            book._l10n_ve_ensure_paperformat()
            if book.paperformat_id:
                return book.paperformat_id
        return self.env.ref("l10n_ve_stock.paperformat_l10n_ve_dispatch_guide")

    def _l10n_ve_is_ve_outgoing_dispatch_guide_picking(self):
        self.ensure_one()
        return (
            self.l10n_ve_dispatch_guide_enabled
            and self.l10n_ve_is_ve_country
            and self.picking_type_id.code == "outgoing"
        )

    def _l10n_ve_get_portal_pdf_report_xmlid(self):
        self.ensure_one()
        if self._l10n_ve_is_ve_outgoing_dispatch_guide_picking():
            return "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        return "stock.action_report_delivery"

    def l10n_ve_portal_pdf_url(self):
        self.ensure_one()
        sale = self.sudo().sale_id
        token = sale.access_token if sale else ""
        return f"/my/picking/pdf/{self.id}?access_token={token}"

    def l10n_ve_portal_control_number_display(self):
        self.ensure_one()
        return (self.sudo().l10n_ve_control_number or "").strip()

    def _l10n_ve_will_assign_dispatch_control_number_on_validate(self):
        self.ensure_one()
        if (self.l10n_ve_control_number or "").strip():
            return False
        if not self._l10n_ve_dispatch_requires_control_number():
            return False
        return bool(self._l10n_ve_dispatch_guide_section())

    def action_l10n_ve_print_dispatch_guide(self):
        if any(not picking.l10n_ve_dispatch_guide_enabled for picking in self):
            return super(
                StockPicking, self.with_context(discard_logo_check=True)
            ).do_print_picking()
        self.l10n_ve_dispatch_guide_report_check()
        report = self.env.ref("l10n_ve_stock.action_report_l10n_ve_dispatch_guide")
        self.write({"printed": True})
        return report.with_context(discard_logo_check=True).report_action(
            self, config=False
        )

    def _action_open_dispatch_guide_validate_confirmation_wizard(self):
        self.ensure_one()
        return {
            "name": _("Confirmar guía de despacho"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ve.stock.picking.validate.confirmation",
            "view_mode": "form",
            "target": "new",
            "context": {
                **self.env.context,
                "default_picking_ids": [fields.Command.set(self.ids)],
            },
        }

    def _pre_action_done_hook(self):
        if not self.env.context.get("l10n_ve_dispatch_guide_validate_confirmed"):
            pickings = self.filtered(
                lambda picking: (
                    picking._l10n_ve_will_assign_dispatch_control_number_on_validate()
                )
            )
            if pickings:
                return (
                    pickings._action_open_dispatch_guide_validate_confirmation_wizard()
                )
        return super()._pre_action_done_hook()

    def _action_done(self):
        res = super()._action_done()
        if self.env.context.get("install_mode"):
            return res
        for picking in self:
            if not picking._l10n_ve_dispatch_requires_control_number():
                continue
            if picking.l10n_ve_control_number:
                continue
            section = picking._l10n_ve_dispatch_guide_section()
            if not section:
                continue
            picking._l10n_ve_assign_dispatch_control_number()
        return res
