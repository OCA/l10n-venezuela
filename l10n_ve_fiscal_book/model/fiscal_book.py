#!/usr/bin/python
# -*- encoding: utf-8 -*-
###############################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
############# Credits #########################################################
#    Coded by: Humberto Arocha           <hbto@vauxoo.com>
#              Katherine Zaoral          <katherine.zaoral@vauxoo.com>
#    Planified by: Humberto Arocha & Nhomar Hernandez
#    Audited by: Humberto Arocha           <hbto@vauxoo.com>
###############################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
from openerp.osv import osv, orm, fields
from openerp.tools.translate import _
from openerp.addons import decimal_precision as dp


class fiscal_book(orm.Model):

    def _get_type(self, cr, uid, context=None):
        context = context or {}
        return context.get('type', 'purchase')

    def _get_partner_addr(self, cr, uid, ids, field_name, arg, context=None):
        """ It returns Partner address in printable format for the fiscal book
        report.
        @param field_name: field [get_partner_addr]
        """
        context = context or {}
        res = {}.fromkeys(ids, 'NO HAY DIRECCION FISCAL DEFINIDA')
        #~ TODO: ASK: what company, fisal.book.company_id?
        addr = self.pool.get('res.users').browse(
            cr, uid, uid, context=context).company_id.partner_id
        for fb_id in ids:
            if addr:
                res[fb_id] = addr.type == 'invoice' and (addr.street or '') + \
                    ' ' + (addr.street2 or '') + ' ' + (addr.zip or '') + ' ' \
                    + (addr.city or '') + ' ' + \
                    (addr.country_id and addr.country_id.name or '') + \
                    ', TELF.:' + (addr.phone or '') or \
                    'NO HAY DIRECCION FISCAL DEFINIDA'
        return res

    def _get_total_with_iva_sum(self, cr, uid, ids, field_names, arg,
                                context=None):
        """ It returns sum of of all columns total with iva of the fiscal book
        lines.
        @param field_name: ['get_total_with_iva_sum',
                            'get_total_with_iva_i_sum',
                            'get_total_with_iva_n_sum']"""
        context = context or {}
        res = {}.fromkeys(ids, {}.fromkeys(field_names, 0.0))
        for fb_brw in self.browse(cr, uid, ids, context=context):
            for fbl_brw in fb_brw.fbl_ids:
                if fbl_brw.invoice_id:
                    if fbl_brw.invoice_is_imported:
                        res[fb_brw.id]['get_total_with_iva_i_sum'] += \
                            fbl_brw.total_with_iva
                    else:
                        res[fb_brw.id]['get_total_with_iva_n_sum'] += \
                            fbl_brw.total_with_iva

            res[fb_brw.id]['get_total_with_iva_sum'] = \
                res[fb_brw.id]['get_total_with_iva_i_sum'] + \
                res[fb_brw.id]['get_total_with_iva_n_sum']

        return res

    def _totalization(self, cr, uid, ids, field_name, arg, context=None):
        """ It returns summation of a fiscal book tax column (Using
        fiscal.book.taxes.summary).
        @param: field [ 'get_vat_exempt_i_sum', 'get_vat_exempt_n_sum',
            'get_vat_sdcf_n_sum', 'get_vat_sdcf_i_sum',
            'get_vat_general_i_base_sum', 'get_vat_general_i_tax_sum',
            'get_vat_additional_i_base_sum', 'get_vat_additional_i_tax_sum',
            'get_vat_reduced_i_base_sum', 'get_vat_reduced_i_tax_sum',
            'get_vat_general_n_base_sum', 'get_vat_general_n_tax_sum',
            'get_vat_additional_n_base_sum', 'get_vat_additional_n_tax_sum',
            'get_vat_reduced_n_base_sum', 'get_vat_reduced_n_tax_sum' ]
        """
        context = context or {}
        res = {}.fromkeys(ids, 0.0)
        fbts_obj = self.pool.get('fiscal.book.taxes.summary')

        #~ Identifying the field
        field_info = field_name[8:][:-4].split('_')
        field_tax, field_scope, field_amount = (len(field_info) == 3) \
            and field_info \
            or field_info + ['base']

        #~ Translation between the fb fields names and the fbts records data.
        tax_type = {'exempt': 'exento', 'sdcf': 'sdcf', 'reduced': 'reducido',
                    'general': 'general', 'additional': 'adicional'}
        amount_type = {'base': 'base_amount_sum', 'tax': 'tax_amount_sum'}
        scope_type = {'n': False, 'i': True}

        #~ Calculate
        for fb_brw in self.browse(cr, uid, ids, context=context):
            for fbts_brw in fb_brw.fbts_ids:
                if fbts_brw.tax_type == tax_type[field_tax] and fbts_brw.international == scope_type[field_scope]:
                    res[fb_brw.id] = \
                        getattr(fbts_brw, amount_type[field_amount])
        return res

    def _get_vat_sdcf_sum(self, cr, uid, ids, field_name, arg, context=None):
        """ It returns international and domestic purchase SDCF summation.
        @param field_name: field ['get_vat_sdcf_sum'] """
        context = context or {}
        res = {}.fromkeys(ids, 0.0)
        for fb_id in ids:
            fb_obj = self.browse(cr, uid, fb_id, context=context)
            res[fb_id] = fb_obj.get_vat_sdcf_n_sum + fb_obj.get_vat_sdcf_i_sum
        return res

    def _get_vat_all_base_sum(self, cr, uid, ids, field_name, arg,
                              context=None):
        """ It calculate sum of all tax base (reduced, general and additional)
        for international and domestic scope.
        @param field_name: field ['get_vat_all_i_base_sum',
                                  'get_vat_all_n_base_sum' ]
        """
        #~ TODO: it works, but can be optimized.
        context = context or {}
        res = {}.fromkeys(ids, 0.0)
        for fb_brw in self.browse(cr, uid, ids, context=context):
            if field_name == 'get_vat_all_i_base_sum':
                res[fb_brw.id] = fb_brw.get_vat_general_i_base_sum + \
                    fb_brw.get_vat_additional_i_base_sum + \
                    fb_brw.get_vat_reduced_i_base_sum
            if field_name == 'get_vat_all_n_base_sum':
                res[fb_brw.id] = fb_brw.get_vat_general_n_base_sum + \
                    fb_brw.get_vat_additional_n_base_sum + \
                    fb_brw.get_vat_reduced_n_base_sum
        return res

    def _get_total_tax_credit_debit(self, cr, uid, ids, field_names, arg,
                                    context=None):
        """ It returns sum of of all data in the fiscal book summary table.
        @param field_name: ['get_total_tax_credit_debit_base_sum',
                            'get_total_tax_credit_debit_tax_sum']"""
        context = context or {}
        res = {}.fromkeys(ids, {}.fromkeys(field_names, 0.0))
        for fb_brw in self.browse(cr, uid, ids, context=context):
            res[fb_brw.id]['get_total_tax_credit_debit_base_sum'] += \
                fb_brw.get_vat_sdcf_i_sum + \
                fb_brw.get_vat_general_i_base_sum + \
                fb_brw.get_vat_additional_i_base_sum + \
                fb_brw.get_vat_reduced_i_base_sum + \
                fb_brw.get_vat_sdcf_n_sum + \
                fb_brw.get_vat_general_n_base_sum + \
                fb_brw.get_vat_additional_n_base_sum + \
                fb_brw.get_vat_reduced_n_base_sum
            res[fb_brw.id]['get_total_tax_credit_debit_tax_sum'] += \
                fb_brw.get_vat_general_i_tax_sum + \
                fb_brw.get_vat_additional_i_tax_sum + \
                fb_brw.get_vat_reduced_i_tax_sum + \
                fb_brw.get_vat_general_n_tax_sum + \
                fb_brw.get_vat_additional_n_tax_sum + \
                fb_brw.get_vat_reduced_n_tax_sum

        return res

    def _get_wh(self, cr, uid, ids, field_names, arg, context=None):
        """ It returns sum of all data in the withholding summary table.
        @param field_name: ['get_total_wh_sum', 'get_previous_wh_sum',
                            'get_wh_sum']"""
        #~ TODO: this works if its ensuring that that emmision date is always
        #~ set and and all periods for every past dates are created.
        context = context or {}
        res = {}.fromkeys(ids, {}.fromkeys(field_names, 0.0))
        period_obj = self.pool.get('account.period')
        for fb_brw in self.browse(cr, uid, ids, context=context):
            for fbl_brw in fb_brw.fbl_ids:
                if fbl_brw.iwdl_id:
                    emission_period = period_obj.find(cr, uid,
                                                      fbl_brw.emission_date,
                                                      context=context)
                    if emission_period[0] == fb_brw.period_id.id:
                        res[fb_brw.id]['get_wh_sum'] += \
                            fbl_brw.iwdl_id.amount_tax_ret
                        res[fb_brw.id]['get_wh_debit_credit_sum'] += \
                            fbl_brw.get_wh_debit_credit
                    else:
                        res[fb_brw.id]['get_previous_wh_sum'] += \
                            fbl_brw.iwdl_id.amount_tax_ret
            res[fb_brw.id]['get_total_wh_sum'] = \
                res[fb_brw.id]['get_wh_sum'] + \
                res[fb_brw.id]['get_previous_wh_sum']
        return res

    _description = "Venezuela's Sale & Purchase Fiscal Books"
    _name = 'fiscal.book'
    _inherit = ['mail.thread']
    _columns = {
        'name': fields.char('Description', size=256, required=True),
        'company_id': fields.many2one('res.company', 'Company',
                                      help='Company', required=True),
        'period_id': fields.many2one('account.period', 'Period',
                                     help="Book's Fiscal Period",
                                     required=True),
        'state': fields.selection([('draft', 'Getting Ready'),
                                   ('open', 'Approved by Manager'),
                                   ('done', 'Seniat Submitted')],
                                  string='Status', required=True),
        'type': fields.selection([('sale', 'Sale Book'),
                                  ('purchase', 'Purchase Book')],
                                 help='Select Sale for Customers and Purchase \
                                 for Suppliers',
                                 string='Book Type', required=True),
        'base_amount': fields.float('Taxable Amount',
                                    help='Amount used as Taxing Base'),
        'tax_amount': fields.float('Taxed Amount',
                                   help='Taxed Amount on Taxing Base'),
        'fbl_ids': fields.one2many('fiscal.book.lines', 'fb_id', 'Book Lines',
                                   help='Lines being recorded in the book'),
        'fbt_ids': fields.one2many('fiscal.book.taxes', 'fb_id', 'Tax Lines',
                                   help='Taxes being recorded in the book'),
        'fbts_ids': fields.one2many('fiscal.book.taxes.summary', 'fb_id',
                                    'Tax Summary'),
        'invoice_ids': fields.one2many('account.invoice', 'fb_id', 'Invoices',
                                       help='Invoices being recorded in a \
                                       Fiscal Book'),
        'issue_invoice_ids': fields.one2many('account.invoice', 'issue_fb_id',
                                             'Issue Invoices',
                                             help='Invoices that are in \
                                             pending state. Cancel or Draft'),
        'iwdl_ids': fields.one2many('account.wh.iva.line', 'fb_id',
                                    'Vat Withholdings',
                                    help='Vat Withholdings being recorded in \
                                    a Fiscal Book'),
        'abl_ids': fields.one2many('adjustment.book.line', 'fb_id',
                                   'Adjustment Lines',
                                   help='Adjustment Lines being recorded in \
                                   a Fiscal Book'),
        'note': fields.text('Note', required=True),

        #~ Totalization fields depending on international scope
        'get_total_with_iva_i_sum': fields.function(
            _get_total_with_iva_sum,
            type="float", method=True, store=True,
            multi="get_total_with_iva",
            string='International Total with VAT Sum'),
        'get_total_with_iva_n_sum': fields.function(
            _get_total_with_iva_sum,
            type="float", method=True, store=True,
            multi="get_total_with_iva",
            string='Domestic Total with VAT Sum'),

        'get_vat_exempt_i_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            string="Exempt International Purchase Sum",
            help="Exempt International Purchase Sum"),
        'get_vat_exempt_n_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            string="Exempt Domestic Purchase Sum",
            help="Exempt Domestic Purchase Sum"),
        'get_vat_sdcf_n_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            string="NO GRAVADAS Y/O SIN DERECHO A CREDITO FISCAL",
            help="NO GRAVADAS Y/O SIN DERECHO A CREDITO FISCAL"),
        'get_vat_sdcf_i_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            string="IMPORTACIONES NO GRAVADAS Y/O SIN DERECHO A CREDITO \
            FISCAL",
            help="IMPORTACIONES NO GRAVADAS Y/O SIN DERECHO A CREDITO FISCAL"),
        'get_vat_general_i_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota General \
            (Base Imponible).",
            help="Importaciones Gravadas por Alícuota General \
            (Base Imponible)."),
        'get_vat_general_i_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota General \
            (Crédito Fiscal)",
            help="Importaciones Gravadas por Alícuota General \
            (Crédito Fiscal)."),
        'get_vat_additional_i_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota Gral. más Adicional \
            (Base Imponible).",
            help="Importaciones Gravadas por Alícuota Gral. más Adicional \
            (Base Imponible)."),
        'get_vat_additional_i_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota Gral. más Adicional \
            (Crédito Fiscal).",
            help="Importaciones Gravadas por Alícuota Gral. más Adicional \
            (Crédito Fiscal)."),
        'get_vat_reduced_i_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota Reducida \
            (Base Imponible).",
            help="Importaciones Gravadas por Alícuota Reducida \
            (Base Imponible)."),
        'get_vat_reduced_i_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Importaciones Gravadas por Alícuota Reducida \
            (Crédito Fiscal).",
            help="Importaciones Gravadas por Alícuota Reducida \
            (Crédito Fiscal)."),
        'get_vat_general_n_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas sólo por Alícuota General \
            (Base Imponible).",
            help="Internas Gravadas sólo por Alícuota General \
            (Base Imponible)."),
        'get_vat_general_n_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas sólo por Alícuota General \
            (Crédito Fiscal).",
            help="Internas Gravadas sólo por Alícuota General \
            (Crédito Fiscal)."),
        'get_vat_additional_n_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas sólo por Alícuota General más Adicional \
            (Base Imponible).",
            help="Internas Gravadas sólo por Alícuota General más Adicional \
            (Base Imponible)."),
        'get_vat_additional_n_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas sólo por Alícuota General más Adicional \
            (Crédito Fiscal).",
            help="Internas Gravadas sólo por Alícuota General más Adicional \
            (Crédito Fiscal)."),
        'get_vat_reduced_n_base_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas por Alícuota Reducida (Base Imponible).",
            help="Internas Gravadas por Alícuota Reducida (Base Imponible)."),
        'get_vat_reduced_n_tax_sum': fields.function(
            _totalization,
            type="float", method=True, store=True,
            digits_compute=dp.get_precision('Account'),
            string="Internas Gravadas por Alícuota Reducida (Crédito Fiscal).",
            help="Internas Gravadas por Alícuota Reducida (Crédito Fiscal)."),

        'get_vat_all_i_base_sum': fields.function(
            _get_vat_all_base_sum,
            type="float", method=True, store=True,
            string="International base sum (reduced, general and additional)",
            help="International base sum (reduced, general and additional)"),
        'get_vat_all_n_base_sum': fields.function(
            _get_vat_all_base_sum,
            type="float", method=True, store=True,
            string="Domestic base sum (reduced, general and additional)",
            help="Domestic base sum (reduced, general and additional)"),

        #~ Totalization fields that covers all scopes
        'get_total_with_iva_sum': fields.function(
            _get_total_with_iva_sum,
            type="float", method=True, store=True,
            multi="get_total_with_iva",
            string='Total with VAT Sum'),
        'get_vat_sdcf_sum': fields.function(
            _get_vat_sdcf_sum,
            type="float", method=True, store=True,
            string="No Gravadas y/o Sin Derecho a Crédito Fiscal",
            help="No Gravadas y/o Sin Derecho a Crédito Fiscal"),

        'get_total_tax_credit_debit_base_sum': fields.function(
            _get_total_tax_credit_debit,
            type="float", method=True, store=True,
            multi="get_total_tax_credit_debit",
            string="Base Amount for Tax (Debit/Credit) Total for \
            (Sale/Pruchase)",
            help="Base Imponible del Total (Débitos/Créditos) Fiscales para \
            el libro de (Venta/Compra)"),
        'get_total_tax_credit_debit_tax_sum': fields.function(
            _get_total_tax_credit_debit,
            type="float", method=True, store=True,
            multi="get_total_tax_credit_debit",
            string="Tax Amount for Tax (Debit/Credit) Total for \
            (Sale/Pruchase)",
            help="Monto Imponible del Total (Débitos/Créditos) Fiscales para \
            el libro de (Venta/Compra)"),

        'get_wh_sum': fields.function(
            _get_wh,
            type="float", method=True, store=True, multi="get_wh",
            string="Current Period Withholding",
            help="Used at \
            1. Totalization row in Fiscal Book Line block at Withholding VAT \
               Column \
            2. Second row at the Withholding Summary block"),
        'get_previous_wh_sum': fields.function(
            _get_wh,
            type="float", method=True, store=True, multi="get_wh",
            string="Previous Period Withholding",
            help="First row at the Withholding Summary block"),
        'get_total_wh_sum': fields.function(
            _get_wh,
            type="float", method=True, store=True, multi="get_wh",
            string="VAT Withholding Sum",
            help="Totalization row at the Withholding Summary block"),
        'get_wh_debit_credit_sum': fields.function(
            _get_wh,
            type="float", method=True, store=True, multi="get_wh",
            string="Based Tax Debit Sum",
            help="Totalization row in Fiscal Book Line block at \
            Based Tax Debit Column"),

        #~ Printable report data
        'get_partner_addr': fields.function(
            _get_partner_addr,
            type="text", method=True,
            help='Partner address printable format'),
    }

    _defaults = {
        'state': 'draft',
        'type': _get_type,
        'company_id': lambda s, c, u, ctx: \
            s.pool.get('res.users').browse(c, u, u, context=ctx).company_id.id,
    }

    _sql_constraints = [
        ('period_type_company_uniq', 'unique (period_id,type,company_id)',
            'The period and type combination must be unique!'),
    ]

    #~ action methods

    def button_update_book_invoices(self, cr, uid, ids, context=None):
        """ It take the instance of fiscal book and do the update of invoices.
        """
        context = context or {}
        self.update_book_invoices(cr, uid, ids[0], context=context)
        self.update_book_taxes_amount_fields(cr, uid, ids[0], context=context)
        return True

    def button_update_book_issue_invoices(self, cr, uid, ids, context=None):
        """ Take the instance of fiscal book and do the update of issue
        invoices. """
        context = context or {}
        self.update_book_issue_invoices(cr, uid, ids[0], context=context)
        return True

    def button_update_book_wh_iva_lines(self, cr, uid, ids, context=None):
        """ Take the instance of fiscal book and do the update of wh iva lines.
        """
        context = context or {}
        self.update_book_wh_iva_lines(cr, uid, ids[0], context=context)
        return True

    def button_update_book_lines(self, cr, uid, ids, context=None):
        """ Take the instance of fiscal book and do the update book lines. """
        context = context or {}
        self.update_book_lines(cr, uid, ids[0], context=context)
        return True

    def onchange_period_id(self, cr, uid, ids, context=None):
        """ It make clear all stuff of book. """
        context = context or {}
        self.clear_book(cr, uid, ids, context=context)
        return True

    #~ update book methods

    def _get_invoice_ids(self, cr, uid, fb_id, context=None):
        """
        It returns ids from open and paid invoices regarding to the type and
        period of the fiscal book order by date invoiced.
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        fb_brw = self.browse(cr, uid, fb_id, context=context)
        inv_type = fb_brw.type == 'sale' \
            and ['out_invoice', 'out_refund'] \
            or ['in_invoice', 'in_refund']
        inv_state = ['paid', 'open']
        #~ pull invoice data
        inv_ids = inv_obj.search(cr, uid,
                                 [('period_id', '=', fb_brw.period_id.id),
                                  ('company_id', '=', fb_brw.company_id.id),
                                  ('type', 'in', inv_type),
                                  ('state', 'in', inv_state)],
                                 order='date_invoice asc', context=context)
        return inv_ids

    def update_book(self, cr, uid, ids, context=None):
        """ It generate and fill book data with invoices, wh iva lines and
        taxes. """
        context = context or {}
        for fb_brw in self.browse(cr, uid, ids, context=context):
            self.update_book_invoices(cr, uid, fb_brw.id, context=context)
            self.update_book_wh_iva_lines(cr, uid, fb_brw.id, context=context)
            self.update_book_lines(cr, uid, fb_brw.id, context=context)
            fbl_ids = [fbl.id for fbl in fb_brw.fbl_ids]
            self.update_book_issue_invoices(cr, uid, fb_brw.id,
                                            context=context)
        return True

    def update_book_invoices(self, cr, uid, fb_id, context=None):
        """ It relate/unrelate the invoices to the fical book.
        @param fb_id: fiscal book id
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        #~ Relate invoices
        inv_ids = self._get_invoice_ids(cr, uid, fb_id, context=context)
        inv_obj.write(cr, uid, inv_ids, {'fb_id': fb_id}, context=context)
        #~ update book taxes
        self.update_book_taxes(cr, uid, fb_id, context=context)

        #~ TODO: move this process to the cancel process of the invoice
        #~ Unrelate invoices (period book change, invoice now cancel/draft or
        #~ have change its period)
        all_inv_ids = inv_obj.search(cr, uid, [('fb_id', '=', fb_id)],
                                     context=context)
        for inv_id_to_check in all_inv_ids:
            if inv_id_to_check not in inv_ids:
                inv_obj.write(cr, uid, inv_id_to_check, {'fb_id': False},
                              context=context)
        return True

    def _get_issue_invoice_ids(self, cr, uid, fb_id, context=None):
        """
        It returns ids from not open or paid invoices regarding to the type and
        period of the fiscal book order by date invoiced.
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        fb_brw = self.browse(cr, uid, fb_id, context=context)
        inv_type = fb_brw.type == 'sale' \
            and ['out_invoice', 'out_refund'] \
            or ['in_invoice', 'in_refund']
        inv_state = ['paid', 'open']
        #~ pull invoice data
        issue_inv_ids = inv_obj.search(
            cr, uid,
            ['|',
             '&', ('fb_id', '=', fb_brw.id), ('period_id', '!=', fb_brw.period_id.id),
             '&', '&', ('period_id', '=', fb_brw.period_id.id), ('type', 'in', inv_type),
                       ('state', 'not in', inv_state)],
            order='date_invoice asc', context=context)

        return issue_inv_ids

    def update_book_issue_invoices(self, cr, uid, fb_id, context=None):
        """ It relate the issue invoices to the fiscal book. That criterion is:
          - Invoices of the period in state different form open or paid state.
          - Invoices already related to the book but it have a period change.
        @param fb_id: fiscal book id
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        issue_inv_ids = self._get_issue_invoice_ids(cr, uid, fb_id,
                                                    context=context)
        inv_obj.write(cr, uid, issue_inv_ids, {'issue_fb_id': fb_id},
                      context=context)
        return issue_inv_ids

    def _get_wh_iva_line_ids(self, cr, uid, fb_id, context=None):
        """ It returns ids from wh iva lines with state 'done' regarding to the
        fiscal book period.
        @param fb_id: fiscal book id
        """
        context = context or {}
        awi_obj = self.pool.get('account.wh.iva')
        awil_obj = self.pool.get('account.wh.iva.line')
        fb_brw = self.browse(cr, uid, fb_id, context=context)
        awil_type = fb_brw.type == 'sale' \
                    and ['out_invoice', 'out_refund'] \
                    or ['in_invoice', 'in_refund']
        #~ pull wh iva line data
        awil_ids = []
        awi_ids = awi_obj.search(cr, uid,
                                 [('period_id', '=', fb_brw.period_id.id),
                                 ('type', 'in', awil_type),
                                 ('state', '=', 'done')],
                                 context=context)
        for awi_id in awi_ids:
            list_ids = awil_obj.search(cr, uid,
                                       [('retention_id', '=', awi_id)],
                                       context=context)
            awil_ids.extend(list_ids)
        return awil_ids or False

    #~ TODO: test this method.
    def update_book_wh_iva_lines(self, cr, uid, fb_id, context=None):
        """ It relate/unrelate the wh iva lines to the fiscal book.
        @param fb_id: fiscal book id
        """
        context = context or {}
        iwdl_obj = self.pool.get('account.wh.iva.line')
        #~ Relate wh iva lines
        iwdl_ids = self._get_wh_iva_line_ids(cr, uid, fb_id, context=context)
        iwdl_obj.write(cr, uid, iwdl_ids, {'fb_id': fb_id}, context=context)
        #~ Unrelate wh iva lines (period book change, wh iva line have been
        #~ cancel or have change its period)
        all_iwdl_ids = iwdl_obj.search(cr, uid, [('fb_id', '=', fb_id)],
                                       context=context)
        for iwdl_id_to_check in all_iwdl_ids:
            if iwdl_id_to_check not in iwdl_ids:
                iwdl_obj.write(cr, uid, iwdl_id_to_check, {'fb_id': False},
                               context=context)
        return True

    def _get_book_taxes_ids(self, cr, uid, fb_id, context=None):
        """ It returns account invoice taxes IDSs from the fiscal book
        invoices.
        @param fb_id: fiscal book id
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        ait_ids = []
        for inv_brw in self.browse(cr, uid, fb_id,
                                   context=context).invoice_ids:
            ait_ids += [ait.id for ait in inv_brw.tax_line]
        return ait_ids

    def update_book_taxes(self, cr, uid, fb_id, context=None):
        """ It relate/unrelate the invoices taxes from the period to the book.
        @param fb_id: fiscal book id
        """
        context = context or {}
        fbt_obj = self.pool.get('fiscal.book.taxes')
        fb_brw = self.browse(cr, uid, fb_id, context=context)
        ait_ids = self._get_book_taxes_ids(cr, uid, fb_id, context=context)
        fbt_ids = fbt_obj.search(cr, uid, [('fb_id', '=', fb_id)],
                                 context=context)
        #~ Unrelate taxes
        fbt_obj.unlink(cr, uid, fbt_ids, context=context)
        #~ Relate taxes
        data = map(lambda x: (0, 0, {'ait_id': x}), ait_ids)
        self.write(cr, uid, fb_id, {'fbt_ids': data}, context=context)
        return True

    def _get_invoice_iwdl_id(self, cr, uid, fb_id, inv_id, context=None):
        """ It check if the invoice have wh iva lines asociated and if its
        check if it is at the same period. Return the wh iva line ID or False
        instead.
        @param fb_id: fiscal book id.
        @param inv_id: invoice id to get wh line.
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        inv_brw = inv_obj.browse(cr, uid, inv_id, context=context)
        iwdl_obj = self.pool.get('account.wh.iva.line')
        iwdl_id = False
        if inv_brw.wh_iva_id:
            iwdl_id = iwdl_obj.search(cr, uid,
                                      [('invoice_id', '=', inv_brw.id),
                                       ('fb_id', '=', fb_id)],
                                      context=context)
        return iwdl_id and iwdl_id[0] or False

    def _get_orphan_iwdl_ids(self, cr, uid, fb_id, context=None):
        """ It returns a list of ids from the orphan wh iva lines in the period
        that have not associated invoice.
        @param fb_id: fiscal book id
        """
        context = context or {}
        iwdl_obj = self.pool.get('account.wh.iva.line')
        inv_ids = [inv_brw.id for inv_brw in self.browse(cr, uid, fb_id, context=context).invoice_ids]
        inv_wh_ids = \
            [iwdl_brw.invoice_id.id for iwdl_brw in self.browse(
                cr, uid, fb_id, context=context).iwdl_ids]
        orphan_inv_ids = set(inv_wh_ids) - set(inv_ids)
        orphan_inv_ids = list(orphan_inv_ids)
        return orphan_inv_ids and iwdl_obj.search(
            cr, uid, [('invoice_id', 'in', orphan_inv_ids)],
            context=context) or []

    def order_book_lines(self, cr, uid, fb_id, context=None):
        """ It order the fiscal book lines chronologically acs by a date.
        If fiscal book type is purchase then is order by emission date.
        @param fb_id: fiscal book id.
        """
        context = context or {}
        fbl_obj = self.pool.get('fiscal.book.lines')
        order_date = {'purchase': 'emission_date',
                      'sale': 'accounting_date'}
        fbl_ids = [fbl_brw.id for fbl_brw in self.browse(
            cr, uid, fb_id, context=context).fbl_ids]
        ordered_fbl_ids = fbl_obj.search(
            cr, uid, [('id', 'in', fbl_ids)],
            order=order_date[self.browse(cr, uid, fb_id, context=context).type] + ' asc',
            context=context)
        #~ TODO: this date could change with the improve of the fbl model
        for rank, fbl_id in enumerate(ordered_fbl_ids, 1):
            fbl_obj.write(cr, uid, fbl_id, {'rank': rank}, context=context)
        return True

    def _get_no_match_date_iwdl_ids(self, cr, uid, fb_id, context=None):
        """ It returns a list of wh iva lines ids that have a invoice in the
        same book period but where the invoice date_invoice is different from
        the wh iva line date.
        @param fb_id: fiscal book id.
        """
        context = context or {}
        iwdl_obj = self.pool.get('account.wh.iva.line')
        res = []
        for inv_brw in self.browse(cr, uid, fb_id,
                                   context=context).invoice_ids:
            iwdl_id = self._get_invoice_iwdl_id(cr, uid, fb_id, inv_brw.id,
                                                context=context)
            if iwdl_id:
                if inv_brw.date_invoice != \
                iwdl_obj.browse(cr, uid, iwdl_id, context=context).date_ret:
                    res.append(iwdl_id)
        return res

    def update_book_lines(self, cr, uid, fb_id, context=None):
        """ It updates the fiscal book lines values.
        @param fb_id: fiscal book id
        """
        context = context or {}
        data = []
        my_rank = 1
        iwdl_obj = self.pool.get('account.wh.iva.line')
        fbl_obj = self.pool.get('fiscal.book.lines')
        #~ delete book lines
        fbl_ids = [fbl_brw.id for fbl_brw in self.browse(
            cr, uid, fb_id, context=context).fbl_ids]
        fbl_obj.unlink(cr, uid, fbl_ids, context=context)

        #~ add book lines for withholding iva lines
        if self.browse(cr, uid, fb_id, context=context).iwdl_ids:
            orphan_iwdl_ids = self._get_orphan_iwdl_ids(cr, uid, fb_id,
                                                        context=context)
            no_match_dt_iwdl_ids = \
                self._get_no_match_date_iwdl_ids(cr, uid, fb_id,
                                                 context=context)
            iwdl_ids = orphan_iwdl_ids + no_match_dt_iwdl_ids
            for iwdl_brw in iwdl_obj.browse(cr, uid, iwdl_ids,
                                            context=context):
                values = {
                    'iwdl_id': iwdl_brw.id,
                    'rank': my_rank,
                    'accounting_date': iwdl_brw.date_ret or False,
                    'emission_date': iwdl_brw.date or iwdl_brw.date_ret or False,
                    'doc_type': self.get_doc_type(cr, uid, iwdl_id=iwdl_brw.id,
                                                  context=context),
                    'wh_number': iwdl_brw.retention_id.number or False,
                    'partner_name': iwdl_brw.retention_id.partner_id.name or False,
                    'affected_invoice_date': iwdl_brw.invoice_id.date_document \
                                             or iwdl_brw.invoice_id.date_invoice,
                    'wh_rate': iwdl_brw.wh_iva_rate,
                }
                my_rank += 1
                data.append((0, 0, values))

        #~ add book lines for invoices
        for inv_brw in self.browse(cr, uid, fb_id,
                                   context=context).invoice_ids:
            imex_invoice = self.is_invoice_imex(cr, uid, inv_brw.id,
                                                context=context)
            iwdl_id = self._get_invoice_iwdl_id(cr, uid, fb_id, inv_brw.id,
                                                context=context)
            doc_type = self.get_doc_type(cr, uid, inv_id=inv_brw.id,
                                         context=context)
            values = {
                'invoice_id': inv_brw.id,
                'rank': my_rank,
                'emission_date': (not imex_invoice) \
                                 and (inv_brw.date_document or inv_brw.date_invoice) \
                                 or False,
                'accounting_date': (not imex_invoice) and \
                                   inv_brw.date_invoice or False,
                'imex_date': imex_invoice and inv_brw.customs_form_id.date_liq or False,
                'invoice_is_imported': imex_invoice,
                'debit_affected': inv_brw.parent_id \
                                  and inv_brw.parent_id.type in ['in_invoice', 'out_invoice'] \
                                  and inv_brw.parent_id.parent_id \
                                  and inv_brw.parent_id.number or False,
                'credit_affected': inv_brw.parent_id and \
                                   inv_brw.parent_id.type in ['in_refund', 'out_refund'] \
                                   and inv_brw.parent_id.number or False,
                'ctrl_number': inv_brw.nro_ctrl or False,
                'invoice_parent': (doc_type == "N/DE" or doc_type == "N/CR") \
                                  and (inv_brw.parent_id and inv_brw.parent_id.number or False) \
                                  or False,
                'partner_name': inv_brw.partner_id.name or False,
                'partner_vat': inv_brw.partner_id.vat \
                               and inv_brw.partner_id.vat[2:] or 'N/A',
                'invoice_number': inv_brw.reference or False,
                'doc_type': doc_type,
                'void_form': inv_brw.name and \
                             (inv_brw.name.find('PAPELANULADO') >= 0 \
                             and '03-ANU' or '01-REG') \
                             or '01-REG',
                'fiscal_printer': inv_brw.fiscal_printer or False,
                'invoice_printer': inv_brw.invoice_printer or False,
                'custom_statement': inv_brw.customs_form_id.name or False,
                'iwdl_id': (iwdl_id and iwdl_id not in no_match_dt_iwdl_ids) \
                            and iwdl_id or False,
                'wh_number': (iwdl_id and iwdl_id not in no_match_dt_iwdl_ids) \
                              and iwdl_obj.browse(cr, uid, iwdl_id,
                              context=context).retention_id.number or False,
            }
            my_rank += 1
            data.append((0, 0, values))

        if data:
            self.write(cr, uid, fb_id, {'fbl_ids': data}, context=context)
            self.order_book_lines(cr, uid, fb_id, context=context)
            self.link_book_lines_and_taxes(cr, uid, fb_id, context=context)

        return True

    #~ TODO: Optimization. This method could be transform in a method for
    #~ function field fbts tax y base sum.
    def update_book_taxes_summary(self, cr, uid, fb_id, context=None):
        """ It update the summaroty of taxes by type for this book.
        @param fb_id: fiscal book id
        """
        context = context or {}
        self.clear_book_taxes_summary(cr, uid, fb_id, context=context)
        tax_types = ['exento', 'sdcf', 'reducido', 'general', 'adicional']
        n_base_sum = {}.fromkeys(tax_types, 0.0)
        n_tax_sum = {}.fromkeys(tax_types, 0.0)
        i_base_sum = {}.fromkeys(tax_types, 0.0)
        i_tax_sum = {}.fromkeys(tax_types, 0.0)
        for fbl in self.browse(cr, uid, fb_id, context=context).fbl_ids:
            if fbl.invoice_id:
                for ait in fbl.invoice_id.tax_line:
                    if ait.tax_id.appl_type:
                        if fbl.invoice_is_imported:
                            i_base_sum[ait.tax_id.appl_type] += ait.base_amount
                            i_tax_sum[ait.tax_id.appl_type] += ait.tax_amount
                        else:
                            n_base_sum[ait.tax_id.appl_type] += ait.base_amount
                            n_tax_sum[ait.tax_id.appl_type] += ait.tax_amount
        data = [(0, 0, {'tax_type': ttype,
                        'base_amount_sum': n_base_sum[ttype],
                        'tax_amount_sum': n_tax_sum[ttype],
                        'international': False}) for ttype in tax_types]
        data.extend([(0, 0, {'tax_type': ttype,
                             'base_amount_sum': i_base_sum[ttype],
                             'tax_amount_sum': i_tax_sum[ttype],
                             'international': True}) for ttype in tax_types])
        return data and self.write(cr, uid, fb_id, {'fbts_ids': data},
                                   context=context)

    #~ TODO: test this method (with presice amounts)
    def update_book_taxes_amount_fields(self, cr, uid, fb_id, context=None):
        """ It update the base_amount and the tax_amount field for fiscal book.
        @param fb_id: fiscal book id
        """
        context = context or {}
        tax_amount = base_amount = 0.0
        for fbl in self.browse(cr, uid, fb_id, context=context).fbl_ids:
            if fbl.invoice_id:
                for ait in fbl.invoice_id.tax_line:
                    if ait.tax_id:
                        base_amount = base_amount + ait.base_amount
                        if ait.tax_id.ret:
                            tax_amount = tax_amount + ait.tax_amount
        return self.write(cr, uid, fb_id,
                          {'tax_amount': tax_amount,
                           'base_amount': base_amount},
                          context=context)

    def link_book_lines_and_taxes(self, cr, uid, fb_id, context=None):
        """ Updates the fiscal book taxes. Link the tax with the corresponding
        book line and update the fields of sum taxes in the book.
        @param fb_id: the id of the current fiscal book """
        context = context or {}
        fbt_obj = self.pool.get('fiscal.book.taxes')
        fbl_obj = self.pool.get('fiscal.book.lines')
        #~ delete book taxes
        fbt_ids = fbt_obj.search(cr, uid, [('fb_id', '=', fb_id)],
                                 context=context)
        fbt_obj.unlink(cr, uid, fbt_ids, context=context)
        #~ write book taxes
        data = []
        for fbl in self.browse(cr, uid, fb_id, context=context).fbl_ids:
            if fbl.invoice_id:
                ret_tax_amount = sdcf_tax_amount = exent_tax_amount = \
                    amount_withheld = 0.0
                taxes = fbl.invoice_is_imported \
                        and fbl.invoice_id.imex_tax_line \
                        or fbl.invoice_id.tax_line
                for ait in taxes:
                    if ait.tax_id:
                        data.append((0, 0, {'fb_id': fb_id,
                                            'fbl_id': fbl.id,
                                            'ait_id': ait.id}))
                        if ait.tax_id.ret:
                            ret_tax_amount += ait.base_amount + ait.tax_amount
                        else:
                            if ait.tax_id.appl_type == 'sdcf':
                                sdcf_tax_amount += ait.base_amount
                            if ait.tax_id.appl_type == 'exento':
                                exent_tax_amount += ait.base_amount
                    else:
                        data.append((0, 0, {'fb_id':
                                    fb_id, 'fbl_id': False, 'ait_id': ait.id}))
                fbl_obj.write(
                    cr, uid, fbl.id, {'total_with_iva': ret_tax_amount},
                    context=context)
                fbl_obj.write(
                    cr, uid, fbl.id, {'vat_sdcf': sdcf_tax_amount},
                    context=context)
                fbl_obj.write(
                    cr, uid, fbl.id, {'vat_exempt': exent_tax_amount},
                    context=context)

        if data:
            self.write(cr, uid, fb_id, {'fbt_ids': data}, context=context)
        self.update_book_taxes_summary(cr, uid, fb_id, context=context)
        self.update_book_lines_taxes_fields(cr, uid, fb_id, context=context)
        self.update_book_taxes_amount_fields(cr, uid, fb_id, context=context)
        return True

    def update_book_lines_taxes_fields(self, cr, uid, fb_id, context=None):
        """ Update taxes data for every line in the fiscal book given,
        extrating de data from the fiscal book taxes associated.
        @param fb_id: fiscal book line id.
        """
        context = context or {}
        fbl_obj = self.pool.get('fiscal.book.lines')
        field_names = ['vat_reduced_base', 'vat_reduced_tax',
                       'vat_general_base', 'vat_general_tax',
                       'vat_additional_base', 'vat_additional_tax']
        tax_type = {'reduced': 'reducido', 'general': 'general',
                    'additional': 'adicional'}
        for fbl_brw in self.browse(cr, uid, fb_id, context=context).fbl_ids:
            data = {}.fromkeys(field_names, 0.0)
            for fbt_brw in fbl_brw.fbt_ids:
                for field_name in field_names:
                    field_tax, field_amount = field_name[4:].split('_')
                    if fbt_brw.ait_id.tax_id.appl_type == tax_type[field_tax]:
                        data[field_name] += field_amount == 'base' \
                            and fbt_brw.base_amount \
                            or fbt_brw.tax_amount
            fbl_obj.write(cr, uid, fbl_brw.id, data, context=context)
        return True

    #~ clear book methods

    def clear_book(self, cr, uid, fb_id, context=None):
        """ It delete all book data information.
        @param fb_id: fiscal book line id
        """
        context = context or {}
        #~ clear fields
        self.clear_book_taxes_amount_fields(cr, uid, fb_id, context=context)
        #~ delete data
        self.clear_book_lines(cr, uid, fb_id, context=context)
        self.clear_book_taxes(cr, uid, fb_id, context=context)
        self.clear_book_taxes_summary(cr, uid, fb_id, context=context)
        #~ unrelate data
        self.clear_book_invoices(cr, uid, fb_id, context=context)
        self.clear_book_issue_invoices(cr, uid, fb_id, context=context)
        self.clear_book_iwdl_ids(cr, uid, fb_id, context=context)
        return True

    def clear_book_lines(self, cr, uid, ids, context=None):
        """ It delete all book lines loaded in the book. """
        context = context or {}
        fbl_obj = self.pool.get("fiscal.book.lines")
        for fb_id in ids:
            fbl_brws = self.browse(cr, uid, fb_id, context=context).fbl_ids
            fbl_ids = [fbl.id for fbl in fbl_brws]
            fbl_obj.unlink(cr, uid, fbl_ids, context=context)
            self.clear_book_taxes_amount_fields(cr, uid, fb_id,
                                                context=context)
        return True

    def clear_book_taxes(self, cr, uid, ids, context=None):
        """ It delete all book taxes loaded in the book. """
        context = context or {}
        fbt_obj = self.pool.get("fiscal.book.taxes")
        for fb_id in ids:
            fbt_brws = self.browse(cr, uid, fb_id, context=context).fbt_ids
            fbt_ids = [fbt.id for fbt in fbt_brws]
            fbt_obj.unlink(cr, uid, fbt_ids, context=context)
            self.clear_book_taxes_amount_fields(cr, uid, fb_id,
                                                context=context)
        return True

    def clear_book_taxes_summary(self, cr, uid, fb_id, context=None):
        """ It delete fiscal book taxes summary data for the book """
        context = context or {}
        fbts_obj = self.pool.get('fiscal.book.taxes.summary')
        fbts_ids = fbts_obj.search(cr, uid, [('fb_id', '=', fb_id)],
                                   context=context)
        fbts_obj.unlink(cr, uid, fbts_ids, context=context)
        return True

    def clear_book_taxes_amount_fields(self, cr, uid, fb_id, context=None):
        """ Clean amount taxes fields in fiscal book """
        context = context or {}
        return self.write(cr, uid, fb_id,
                          {'tax_amount': 0.0, 'base_amount': 0.0},
                          context=context)

    def clear_book_invoices(self, cr, uid, ids, context=None):
        """ Unrelate all invoices of the book. And delete fiscal book taxes """
        context = context or {}
        inv_obj = self.pool.get("account.invoice")
        for fb_id in ids:
            self.clear_book_taxes(cr, uid, [fb_id], context=context)
            inv_brws = self.browse(cr, uid, fb_id, context=context).invoice_ids
            inv_ids = [inv.id for inv in inv_brws]
            inv_obj.write(cr, uid, inv_ids, {'fb_id': False}, context=context)
        return True

    def clear_book_issue_invoices(self, cr, uid, ids, context=None):
        """ Unrelate all issue invoices of the book """
        context = context or {}
        inv_obj = self.pool.get("account.invoice")
        for fb_id in ids:
            inv_brws = self.browse(
                cr, uid, fb_id, context=context).issue_invoice_ids
            inv_ids = [inv.id for inv in inv_brws]
            inv_obj.write(cr, uid, inv_ids, {'issue_fb_id': False},
                          context=context)
        return True

    def clear_book_iwdl_ids(self, cr, uid, ids, context=None):
        """ Unrelate all wh iva lines of the book. """
        context = context or {}
        iwdl_obj = self.pool.get("account.wh.iva.line")
        for fb_id in ids:
            iwdl_brws = self.browse(cr, uid, fb_id, context=context).iwdl_ids
            iwdl_ids = [iwdl.id for iwdl in iwdl_brws]
            iwdl_obj.write(
                cr, uid, iwdl_ids, {'fb_id': False}, context=context)
        return True

    def get_doc_type(self, cr, uid, inv_id=None, iwdl_id=None, context=None):
        """ Returns a string that indicates de document type. For withholding
        returns 'RET' and for invoice docuemnts returns different values
        depending of the invoice type: Debit Note 'N/DE', Credit Note 'N/CR',
        Invoice 'FACT'.
        @param inv_id : invoice id
        @param iwdl_id: wh iva line id
        """
        context = context or {}
        res = False
        if inv_id:
            inv_obj = self.pool.get('account.invoice')
            inv_brw = inv_obj.browse(cr, uid, inv_id, context=context)
            if (inv_brw.type in ["in_invoice"] and inv_brw.parent_id) \
                    or inv_brw.type in ["in_refund"]:
                res = "N/DE"
            elif (inv_brw.type in ["out_invoice"] and inv_brw.parent_id) or \
                    inv_brw.type in ["out_refund"]:
                res = "N/CR"
            elif inv_brw.type in ["in_invoice", "out_invoice"]:
                res = "FACT"

            assert res, str(inv_brw) + ": Error in the definition \
            of the document type. \n There is not type category definied for \
            your invoice."
        elif iwdl_id:
            res = 'RET'

        return res

    def get_invoice_import_form(self, cr, uid, inv_id, context=None):
        """ Returns the Invoice reference
        @param inv_id: invoice id
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        inv_brw = inv_obj.browse(cr, uid, inv_id, context=context)
        return inv_brw.reference or False

    def is_invoice_imex(self, cr, uid, inv_id, context=None):
        """ Boolean method that verify is a invoice is imported by cheking the
        customs form associated. 
        @param inv_id: invoice id
        """
        context = context or {}
        inv_obj = self.pool.get('account.invoice')
        inv_brw = inv_obj.browse(cr, uid, inv_id, context=context)
        return inv_brw.customs_form_id and True or False


class fiscal_book_lines(orm.Model):

    def _get_wh_vat(self, cr, uid, ids, field_name, arg, context=None):
        """ For a given book line it returns the withholding vat amount.
        (This is a method used in functional fields).
        @param field_name: ['get_wh_vat'].
        """
        context = context or {}
        res = {}.fromkeys(ids, 0.0)
        for fbl_brw in self.browse(cr, uid, ids, context=context):
            if fbl_brw.iwdl_id:
                res[fbl_brw.id] = fbl_brw.iwdl_id.amount_tax_ret
        return res

    def _get_based_tax_debit(self, cr, uid, ids, field_name, arg,
                             context=None):
        """ It Returns the sum of all tax amount for the taxes realeted to the
        wh iva line.
        @param field_name: ['get_based_tax_debit'].
        """
        #~ TODO: for all taxes realted? only a tax type group?
        context = context or {}
        res = {}.fromkeys(ids, 0.0)
        awilt_obj = self.pool.get("account.wh.iva.line.tax")
        for fbl_brw in self.browse(cr, uid, ids, context=context):
            if fbl_brw.iwdl_id:
                for tax in fbl_brw.iwdl_id.tax_line:
                    res[fbl_brw.id] += tax.amount
        return res

    _description = "Venezuela's Sale & Purchase Fiscal Book Lines"
    _name = 'fiscal.book.lines'
    _rec_name = 'rank'
    _order = 'rank'
    _columns = {

        'fb_id': fields.many2one('fiscal.book', 'Fiscal Book',
                                 help='Fiscal Book that owns this book line'),
        'fbt_ids': fields.one2many('fiscal.book.taxes', 'fbl_id',
                                   string='Tax Lines', help='Tax Lines being \
                                   recorded in a Fiscal Book'),
        'invoice_id': fields.many2one('account.invoice', 'Invoice',
                                      help='Invoice related to this book \
                                      line'),
        'iwdl_id': fields.many2one('account.wh.iva.line', 'Vat Withholding',
                                   help='Withholding iva line related to this \
                                   book line'),

        #~  Invoice and/or Document Data
        'rank': fields.integer("Line", required=True, help="Line Position"),
        'emission_date': fields.date(
            string='Emission Date',
            help='Invoice Document Date / Wh IVA Line Voucher Date'),
        'accounting_date': fields.date(
            string='Accounting Date',
            help='The day of the accounting record [(invoice, date_invoice), \
            (wh iva line, date_ret)]'),
        'doc_type': fields.char('Doc. Type', size=8, help='Document Type'),
        'partner_name': fields.char(size=128, string='Partner Name', help=''),
        'partner_vat': fields.char(size=128, string='Partner TIN', help=''),

        #~ Apply for wh iva lines
        'get_wh_vat': fields.function(_get_wh_vat,
                                      type="float", method=True, store=True,
                                      string="Withholding VAT",
                                      help="Withholding VAT"),
        'wh_number': fields.char(string='Withholding number', size=64,
                                 help=''),
        'affected_invoice_date': fields.date(string="Affected Invoice Date",
                                             help=""),
        'wh_rate': fields.float(string="Withholding percentage",
                                help=""),
        'get_wh_debit_credit': fields.function(
            _get_based_tax_debit,
            type="float", method=True, store=True,
            string="Based Tax Debit",
            help="Sum of all tax amount for the taxes realeted to the \
            wh iva line."),

        #~ Apply for invoice lines
        'ctrl_number': fields.char(string='Invoice Control number', size=64,
                                   help=''),
        'invoice_number': fields.char(string='Invoice number', size=64,
                                      help=''),
        'invoice_parent': fields.char(
            string='Affected Invoice',
            help='Parent Invoice for invoices that are ND or DC type'),
        'imex_date': fields.date(string='Imex Date',
                                 help='Invoice Importation/Exportation Date'),
        'debit_affected': fields.char(string='Affected Debit Notes',
                                      help='Debit notes affected'),
        'credit_affected': fields.char(string='Affected Credit Notes',
                                       help='Credit notes affected'),
        'invoice_is_imported': fields.boolean(string='Is an import'),

        'void_form': fields.char(string='Transaction type', size=192,
                                 help="Operation Type"),

        'fiscal_printer': fields.char(string='Fiscal machine number',
                                      size=192, help=""),
        'invoice_printer': fields.char(string='Fiscal printer invoice number',
                                       size=192, help=""),
        'custom_statement': fields.char(string="Custom Statement",
                                        size=192, help=""),

        'total_with_iva': fields.float('Total with IVA'),
        'vat_sdcf': fields.float('SDCF'),
        'vat_exempt': fields.float('Exent'),
        'vat_reduced_base': fields.float(
            string="8% Base",
            help="Vat Reduced Base Amount"),
        'vat_general_base': fields.float(
            string="12% Base",
            help="Vat General Base Amount"),
        'vat_additional_base': fields.float(
            string="22% Base",
            help="Vat Generald plus Additional Base Amount"),
        'vat_reduced_tax': fields.float(
            string="8% Tax",
            help="Vat Reduced Tax Amount"),
        'vat_general_tax': fields.float(
            string="12% Tax",
            help="Vat General Tax Amount"),
        'vat_additional_tax': fields.float(
            string="22% Tax",
            help="Vat General plus Additional Tax Amount"),
    }


class fiscal_book_taxes(orm.Model):

    _description = "Venezuela's Sale & Purchase Fiscal Book Taxes"
    _name = 'fiscal.book.taxes'
    _rec_name = 'ait_id'
    _columns = {
        'name': fields.related('ait_id', 'name',
                               relation="account.invoice.tax", type="char",
                               string='Description', store=True),
        'fb_id': fields.many2one(
            'fiscal.book', 'Fiscal Book',
            help='Fiscal Book where this tax is related to'),
        'fbl_id': fields.many2one(
            'fiscal.book.lines', 'Fiscal Book Lines',
            help='Fiscal Book Lines where this tax is related to'),
        'base_amount': fields.related('ait_id', 'base_amount',
                                      relation="account.invoice.tax",
                                      type="float", string='Taxable Amount',
                                      help='Amount used as Taxing Base',
                                      store=True),
        'tax_amount': fields.related('ait_id', 'tax_amount',
                                     relation="account.invoice.tax",
                                     type="float", string='Taxed Amount',
                                     help='Taxed Amount on Taxing Base',
                                     store=True),
        'ait_id': fields.many2one(
            'account.invoice.tax', 'Tax',
            help='Tax where is related to'),
    }


class fiscal_book_taxes_summary(orm.Model):

    _description = "Venezuela's Sale & Purchase Fiscal Book Taxes Summary"
    _name = 'fiscal.book.taxes.summary'

    _columns = {
        'fb_id': fields.many2one('fiscal.book', 'Fiscal Book'),
        'tax_type': fields.selection(
            [('exento', '0% Exento'),
             ('sdcf', 'Not entitled to tax credit'),
             ('general', 'General Aliquot'),
             ('reducido', 'Reducted Aliquot'),
             ('adicional', 'General Aliquot + Additional')],
            'Tax Type'),
        'base_amount_sum': fields.float('Taxable Amount Sum'),
        'tax_amount_sum': fields.float('Taxed Amount Sum'),
        'international': fields.boolean('International'),
    }


class adjustment_book_line(orm.Model):

    _name = 'adjustment.book.line'
    _columns = {
        'date_accounting': fields.date(
            'Date Accounting', required=True,
            help="Date accounting for adjustment book"),
        'date_admin': fields.date(
            'Date Administrative', required=True,
            help="Date administrative for adjustment book"),
        'vat': fields.char(
            'Vat', size=10, required=True,
            help="Vat of partner for adjustment book"),
        'partner': fields.char(
            'Partner', size=256, required=True,
            help="Partner for adjustment book"),
        'invoice_number': fields.char(
            'Invoice Number', size=256, required=True,
            help="Invoice number for adjustment book"),
        'control_number': fields.char(
            'Invoice Control', size=256, required=True,
            help="Invoice control for adjustment book"),
        'amount': fields.float(
            'Amount Document at Withholding VAT',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Amount document for adjustment book"),
        'type_doc': fields.selection([
            ('F', 'Invoice'), ('ND', 'Debit Note'), ('NC', 'Credit Note'), ],
            'Document Type', select=True, required=True,
            help="Type of Document for adjustment book: \
            -Invoice(F),-Debit Note(dn),-Credit Note(cn)"),
        'doc_affected': fields.char(
            'Affected Document', size=256, required=True,
            help="Affected Document for adjustment book"),
        'uncredit_fiscal': fields.float(
            'Sin derecho a Credito Fiscal',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Sin derechoa credito fiscal"),
        'amount_untaxed_n': fields.float(
            'Amount Untaxed',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Amount untaxed for national operations"),
        'percent_with_vat_n': fields.float(
            '% Withholding VAT',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Percent(%) VAT for national operations"),
        'amount_with_vat_n': fields.float(
            'Amount Withholding VAT',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Percent(%) VAT for national operations"),
        'amount_untaxed_i': fields.float(
            'Amount Untaxed',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Amount untaxed for international operations"),
        'percent_with_vat_i': fields.float(
            '% Withholding VAT',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Percent(%) VAT for international operations"),
        'amount_with_vat_i': fields.float(
            'Amount Withholding VAT',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Amount withholding VAT for international operations"),
        'amount_with_vat': fields.float(
            'Amount Withholding VAT Total',
            digits_compute=dp.get_precision('Account'), required=True,
            help="Amount withheld VAT total"),
        'voucher': fields.char(
            'Voucher Withholding VAT', size=256,
            required=True, help="Voucher Withholding VAT"),
        'fb_id': fields.many2one(
            'fiscal.book', 'Fiscal Book',
            help='Fiscal Book where this line is related to'),
    }
    _rec_rame = 'partner'
