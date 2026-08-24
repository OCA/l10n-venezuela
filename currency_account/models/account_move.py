import json

from lxml import etree

from odoo import api, fields, models

import logging

from odoo.tools.float_utils import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def read(self, fields=None, load="_classic_read"):
        res = super().read(fields=fields, load=load)
        return self._currency_account_filter_read_rows(res)

    @api.model
    def search_read(
        self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs
    ):
        res = super().search_read(
            domain,
            fields,
            offset=offset,
            limit=limit,
            order=order,
            **read_kwargs,
        )
        return self._currency_account_filter_read_rows(res)

    total_currencies = fields.Json(
        string="Totales por Moneda",
        compute="_compute_total_currencies",
        store=True,
        help="Almacena el total de la factura y el residuo pendiente en cada moneda habilitada.",  # noqa: E501
    )

    lines_with_rate_difference = fields.Boolean(
        string="Lineas con diferencia de tasa de cambio",
        help="Lineas con diferencia de tasa de cambio",
        compute="_compute_lines_with_rate_difference",
    )

    @api.depends(
        "line_ids.has_rate_difrerence",
    )
    def _compute_lines_with_rate_difference(self):
        for move in self:
            move.lines_with_rate_difference = any(
                line.has_rate_difrerence for line in move.invoice_line_ids
            )

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.tax_ids",
        "line_ids.price_total",
        "currency_id",
        "amount_total",
        "amount_residual",
        "company_id.currency_id",
    )
    def _compute_total_currencies(self):
        for move in self:
            totals = {}
            company_currency = move.company_id.currency_id

            currencies = self.env["res.currency"].search(
                [("active", "=", True), ("id", "!=", move.currency_id.id)]
            )

            for currency in currencies:
                date = move.date or fields.Date.today()
                total_in_currency = move.currency_id._convert(
                    move.amount_total, currency, move.company_id, date
                )

                if currency == company_currency:
                    date = fields.Date.today()

                residual_in_currency = move.currency_id._convert(
                    move.amount_residual, currency, move.company_id, date
                )

                totals[str(currency.id)] = {
                    "currency_id": currency.id,
                    "currency_name": currency.name,
                    "total": total_in_currency,
                    "residual": residual_in_currency,
                }

            # El campo JSON debe almacenar una estructura serializable
            move.total_currencies = json.dumps(totals) if totals else False

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        """Convert an account.move.line having display_type='product' into a base line for the taxes computation.

        :param product_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        is_invoice = self.is_invoice(include_receipts=True)
        sign = self.direction_sign if is_invoice else 1
        if is_invoice:
            if product_line.price_subtotal_currency:
                rate = product_line.currency_rate
            else:
                rate = self.invoice_currency_rate
        else:
            rate = (
                (abs(product_line.amount_currency) / abs(product_line.balance))
                if product_line.balance
                else 0.0
            )

        return self.env["account.tax"]._prepare_base_line_for_taxes_computation(
            product_line,
            price_unit=(
                product_line.price_unit if is_invoice else product_line.amount_currency
            ),
            quantity=product_line.quantity if is_invoice else 1.0,
            discount=product_line.discount if is_invoice else 0.0,
            rate=rate,
            sign=sign,
            special_mode=False if is_invoice else "total_excluded",
            name=product_line.name,
        )

    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'list':
            self._inject_currency_fields_to_view(
                arch,
                ['amount_total_signed', 'amount_total_in_currency_signed'],
            )
            self._inject_currency_fields_to_view(
                arch,
                ['amount_total_signed', 'amount_total_in_currency_signed'],
                'x_subtotal_currency_%',
            )
        if view_type == 'form':
            self._inject_line_currency_fields_to_form(arch)
        return arch, view

    def _inject_line_currency_fields_to_form(self, arch):
        self._inject_line_fields_by_pattern(
            arch, 'price_subtotal', 'x_amount_currency_%'
        )
        self._inject_line_fields_by_pattern(
            arch, 'price_subtotal', 'x_subtotal_currency_%'
        )
        self._inject_line_fields_by_pattern(
            arch, 'price_unit', 'x_price_unit_currency_%'
        )

    def _inject_line_fields_by_pattern(self, arch, after_field, field_pattern):
        line_fields = self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'account.move.line'),
            ('name', 'like', field_pattern),
        ])
        if not line_fields:
            return
        ref_nodes = arch.xpath(
            f"//field[@name='invoice_line_ids']//list//field[@name='{after_field}']"
        )
        if not ref_nodes:
            return
        ref_node = ref_nodes[-1]
        parent = ref_node.getparent()
        idx = list(parent).index(ref_node)
        offset = 0
        for af in line_fields:
            currency_id = af.name.rsplit('_', 1)[-1]
            group_xmlid = self._currency_account_group_xmlid(currency_id)
            if af.currency_field:
                currency_el = etree.Element('field')
                currency_el.set('name', af.currency_field)
                currency_el.set('column_invisible', 'True')
                currency_el.set('groups', group_xmlid)
                parent.insert(idx + 1 + offset, currency_el)
                offset += 1
            field_el = etree.Element('field')
            field_el.set('name', af.name)
            field_el.set('optional', 'show')
            field_el.set('readonly', '1')
            field_el.set('groups', group_xmlid)
            field_el.set(
                'column_invisible',
                f'parent.currency_id == {currency_id}'
            )
            parent.insert(idx + 1 + offset, field_el)
            offset += 1

    def _inject_currency_fields_to_view(
        self, arch, after_fields, field_pattern='x_amount_currency_%'
    ):
        amount_fields = self.env['ir.model.fields'].sudo().search([
            ('model', '=', self._name),
            ('name', 'like', field_pattern),
        ])
        if not amount_fields:
            return
        if isinstance(after_fields, str):
            after_fields = [after_fields]
        ref_node = None
        for field_name in after_fields:
            ref_nodes = arch.xpath(f"//field[@name='{field_name}']")
            if ref_nodes:
                ref_node = ref_nodes[-1]
                break
        if ref_node is None:
            return
        parent = ref_node.getparent()
        idx = list(parent).index(ref_node)
        offset = 0
        for af in amount_fields:
            currency_id = af.name.rsplit('_', 1)[-1]
            group_xmlid = self._currency_account_group_xmlid(currency_id)
            if af.currency_field:
                currency_el = etree.Element('field')
                currency_el.set('name', af.currency_field)
                currency_el.set('column_invisible', 'True')
                currency_el.set('groups', group_xmlid)
                parent.insert(idx + 1 + offset, currency_el)
                offset += 1
            field_el = etree.Element('field')
            field_el.set('name', af.name)
            field_el.set('optional', 'show')
            field_el.set('groups', group_xmlid)
            parent.insert(idx + 1 + offset, field_el)
            offset += 1

    @api.model
    def _compute_currency_field(self, currency_id):
        date = self.date or fields.Date.today()
        to_currency = self.env["res.currency"].browse(currency_id)
        total_in_currency = self.currency_id._convert(
            self.amount_total, to_currency, self.company_id, date
        )
        return total_in_currency

    @api.model
    def _compute_subtotal_currency_field(self, currency_id):
        date = self.date or fields.Date.today()
        to_currency = self.env["res.currency"].browse(currency_id)
        subtotal_in_currency = self.currency_id._convert(
            self.amount_untaxed, to_currency, self.company_id, date
        )
        return subtotal_in_currency
