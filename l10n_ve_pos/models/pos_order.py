from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de facturación",
        domain="[('type', '=', 'sale')]",
        check_company=True,
        help="Diario usado al facturar este pedido POS.",
    )
    l10n_ve_pos_invoice_name = fields.Char(
        related="account_move.name",
        string="Número de factura",
        readonly=True,
    )
    l10n_ve_pos_control_number = fields.Char(
        related="account_move.l10n_ve_control_number",
        string="N° de control SENIAT",
        readonly=True,
    )
    l10n_ve_pos_fiscal_invoice_number = fields.Char(
        string="N° factura máquina fiscal",
        copy=False,
    )
    l10n_ve_pos_fiscal_serial = fields.Char(
        string="Serial máquina fiscal",
        copy=False,
    )
    l10n_ve_pos_fiscal_report_z = fields.Char(
        string="N° reporte Z",
        copy=False,
    )

    def _l10n_ve_pos_refund_origin_journal(self):
        self.ensure_one()
        origin = self.refunded_order_id
        if not origin:
            return self.env["account.journal"]
        return origin.invoice_journal_id or origin.account_move.journal_id

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        refund_journal = self._l10n_ve_pos_refund_origin_journal()
        if refund_journal:
            vals["journal_id"] = refund_journal.id
        elif self.invoice_journal_id:
            vals["journal_id"] = self.invoice_journal_id.id
        return vals

    def _l10n_ve_pos_lock_refund_invoice_journal(self):
        for order in self:
            refund_journal = order._l10n_ve_pos_refund_origin_journal()
            if refund_journal and order.invoice_journal_id != refund_journal:
                order.invoice_journal_id = refund_journal

    def _l10n_ve_pos_linked_sale_orders(self):
        sale_orders = self.env["sale.order"]
        if "sale_order_origin_id" not in self.lines._fields:
            return sale_orders
        sale_orders |= self.lines.mapped("sale_order_origin_id")
        if "sale_order_line_id" in self.lines._fields:
            sale_orders |= self.lines.mapped("sale_order_line_id").order_id
        return sale_orders.exists()

    def _l10n_ve_pos_apply_invoice_journal_to_sale_orders(self):
        for order in self:
            journal = order.invoice_journal_id
            if not journal or "journal_id" not in self.env["sale.order"]._fields:
                continue
            sale_orders = order._l10n_ve_pos_linked_sale_orders().filtered(
                lambda sale: sale.state in ("draft", "sent")
            )
            sale_orders.filtered(
                lambda sale, invoice_journal=journal: sale.journal_id != invoice_journal
            ).write({"journal_id": journal.id})

    def _process_saved_order(self, draft):
        if not draft:
            self._l10n_ve_pos_lock_refund_invoice_journal()
            self._l10n_ve_pos_apply_invoice_journal_to_sale_orders()
        return super()._process_saved_order(draft)

    def _l10n_ve_pos_apply_fiscal_fields_to_move(self):
        for order in self:
            move = order.account_move
            if not move:
                continue
            vals = {}
            if (order.l10n_ve_pos_fiscal_invoice_number or "").strip() and not (
                move.l10n_ve_invoice_number or ""
            ).strip():
                vals["l10n_ve_invoice_number"] = order.l10n_ve_pos_fiscal_invoice_number
            if (order.l10n_ve_pos_fiscal_serial or "").strip() and not (
                move.l10n_ve_serial_number or ""
            ).strip():
                vals["l10n_ve_serial_number"] = order.l10n_ve_pos_fiscal_serial
            if (order.l10n_ve_pos_fiscal_report_z or "").strip() and not (
                move.l10n_ve_report_z or ""
            ).strip():
                vals["l10n_ve_report_z"] = order.l10n_ve_pos_fiscal_report_z
            if vals:
                if not move.l10n_ve_invoice_original_printed:
                    vals["l10n_ve_invoice_original_printed"] = True
                if not move.l10n_ve_invoice_date:
                    vals["l10n_ve_invoice_date"] = fields.Datetime.now()
                move.write(vals)
                if hasattr(move, "_l10n_ve_fiscal_serial_update_machine_counters"):
                    move._l10n_ve_fiscal_serial_update_machine_counters(
                        {
                            "sequence": vals.get("l10n_ve_invoice_number"),
                            "serial_machine": vals.get("l10n_ve_serial_number"),
                            "mf_reportz": vals.get("l10n_ve_report_z"),
                        }
                    )

    def _generate_pos_order_invoice(self):
        ve_orders = self.filtered(
            lambda order: order.company_id.account_fiscal_country_id.code == "VE"
        )
        other_orders = self - ve_orders

        result = False
        if other_orders:
            result = super(PosOrder, other_orders)._generate_pos_order_invoice()
        if ve_orders:
            result = super(
                PosOrder, ve_orders.with_context(generate_pdf=False)
            )._generate_pos_order_invoice()
            ve_orders._l10n_ve_pos_apply_fiscal_fields_to_move()
        return result

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            return fields_list
        for field_name in (
            "invoice_journal_id",
            "l10n_ve_pos_fiscal_invoice_number",
            "l10n_ve_pos_fiscal_serial",
            "l10n_ve_pos_fiscal_report_z",
        ):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def _create_order_picking(self):
        return super(
            PosOrder, self.with_context(l10n_ve_pos_order_id=self.id)
        )._create_order_picking()
