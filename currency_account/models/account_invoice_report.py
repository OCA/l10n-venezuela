from lxml import etree

from odoo import models, fields, api
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

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

    @api.model
    def _select(self):
        select = super()._select()
        amount_fields = self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'account.move.line'),
            ('name', 'like', 'x_amount_currency_%'),
        ])
        subtotal_fields = self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'account.move.line'),
            ('name', 'like', 'x_subtotal_currency_%'),
        ])
        if not amount_fields and not subtotal_fields:
            return select
        extra = []
        currency_ids_added = set()
        for af in amount_fields:
            currency_id = int(af.name.replace('x_amount_currency_', ''))
            extra.append(SQL(
                "line.%s * (CASE WHEN move.move_type IN"
                " ('in_invoice','out_refund','in_receipt')"
                " THEN -1 ELSE 1 END) AS %s",
                SQL.identifier(af.name),
                SQL.identifier(af.name),
            ))
            if currency_id not in currency_ids_added:
                extra.append(SQL(
                    "%s AS %s",
                    currency_id,
                    SQL.identifier(f'x_currency_id_{currency_id}'),
                ))
                currency_ids_added.add(currency_id)
        for sf in subtotal_fields:
            currency_id = int(sf.name.replace('x_subtotal_currency_', ''))
            extra.append(SQL(
                "line.%s * (CASE WHEN move.move_type IN"
                " ('in_invoice','out_refund','in_receipt')"
                " THEN -1 ELSE 1 END) AS %s",
                SQL.identifier(sf.name),
                SQL.identifier(sf.name),
            ))
            if currency_id not in currency_ids_added:
                extra.append(SQL(
                    "%s AS %s",
                    currency_id,
                    SQL.identifier(f'x_currency_id_{currency_id}'),
                ))
                currency_ids_added.add(currency_id)
        return SQL("%s, %s", select, SQL(", ").join(extra))

    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ('list', 'pivot'):
            self._inject_currency_fields_to_view(arch, 'price_total')
            self._inject_currency_fields_to_view(
                arch, 'price_total', 'x_subtotal_currency_%'
            )
        return arch, view

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
        is_pivot = arch.tag == 'pivot'
        offset = 0
        for af in amount_fields:
            currency_id = af.name.rsplit('_', 1)[-1]
            group_xmlid = self._currency_account_group_xmlid(currency_id)
            if af.currency_field and not is_pivot:
                currency_el = etree.Element('field')
                currency_el.set('name', af.currency_field)
                currency_el.set('column_invisible', 'True')
                currency_el.set('groups', group_xmlid)
                parent.insert(idx + 1 + offset, currency_el)
                offset += 1
            field_el = etree.Element('field')
            field_el.set('name', af.name)
            field_el.set('groups', group_xmlid)
            if is_pivot:
                field_el.set('type', 'measure')
            else:
                field_el.set('optional', 'show')
                field_el.set('sum', 'Total')
            parent.insert(idx + 1 + offset, field_el)
            offset += 1
