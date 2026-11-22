# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

import re

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .islr_concept import PERSON_TYPES

# Voucher number: AAAAMM of the issue date plus an 8-digit monthly sequence,
# the format of the module sequence.
VOUCHER_NUMBER_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])\d{8}$")

# Once the voucher leaves draft every field is frozen except these, which
# carry no fiscal amount.
POSTED_WRITABLE_FIELDS = {"delivery_date"}

# Fields only the module fills, with the neutral value a client may send
# (the web client sends the defaults on create). Creating or writing any
# other value goes through ``_l10n_ve_create_unlocked`` /
# ``_l10n_ve_write_unlocked``, which are private and cannot be reached over
# RPC; issuing goes only through ``action_issue``. The number is not
# listed: it comes from the sequence, so a client may never send it, except
# an accounting manager registering a voucher issued outside the system.
PROTECTED_FIELDS = {
    "state": "draft",
    "source_move_id": False,
    "wh_move_id": False,
    "credit_note_id": False,
    "seniat_code": False,
    "is_tarifa2": False,
    "treaty_applied": False,
    "treaty_certificate": False,
    "base_pct": 100.0,
    "taxable_base": False,
}


class L10nVeIslrVoucher(models.Model):
    _name = "l10n.ve.islr.voucher"
    _description = "Comprobante de Retención de ISLR (art. 24, Decreto 1.808)"
    _order = "date desc, number desc"
    _rec_name = "number"
    _check_company_auto = True

    number = fields.Char(
        string="Número",
        readonly=True,
        copy=False,
        default="/",
        help="AAAAMM de la fecha de emisión + secuencial de 8 dígitos. Lo "
        "asigna la secuencia, salvo en los comprobantes emitidos fuera del "
        "sistema.",
    )
    is_external = fields.Boolean(
        string="Emitido fuera del sistema",
        copy=False,
        help="Comprobante emitido fuera de Odoo que se registra a mano con su "
        "propio número, sin consumir la secuencia. Solo lo indica un "
        "administrador de contabilidad al crear el comprobante.",
    )
    delivery_date = fields.Date(
        string="Fecha de Entrega al Proveedor",
        copy=False,
        help="Fecha en que se entregó el comprobante al sujeto retenido. No es "
        "un dato fiscal: puede registrarse después de emitido.",
    )
    partner_email_missing = fields.Boolean(
        compute="_compute_partner_email_missing",
        help="El sujeto retenido no tiene correo electrónico.",
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    period = fields.Char(
        string="Período", compute="_compute_period", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Sujeto Retenido", required=True, check_company=True
    )
    source_move_id = fields.Many2one(
        "account.move",
        string="Documento de Origen",
        copy=False,
        readonly=True,
        index="btree_not_null",
        check_company=True,
        help="Factura del proveedor cuya contabilización "
        "(abono en cuenta, art. 1 del Decreto 1.808) emitió este comprobante.",
    )
    wh_move_id = fields.Many2one(
        "account.move",
        string="Asiento de Retención",
        copy=False,
        readonly=True,
        check_company=True,
        help="Asiento que traslada el ISLR retenido de la cuenta por pagar del "
        "proveedor a la cuenta de Retenciones ISLR por Enterar, conciliado "
        "con el documento retenido.",
    )
    credit_note_id = fields.Many2one(
        "account.move",
        string="Anulado por Nota de Crédito",
        copy=False,
        readonly=True,
        check_company=True,
        help="Nota de crédito del mismo mes que anuló este comprobante. Si "
        "quedó base neta positiva, la factura tiene un nuevo comprobante por "
        "el neto; las notas de crédito nunca emiten comprobante propio.",
    )
    move_ids = fields.Many2many(
        "account.move",
        string="Facturas Afectadas",
        domain="[('move_type', 'in', ('in_invoice', 'in_receipt'))]",
        check_company=True,
    )
    concept_id = fields.Many2one(
        "l10n.ve.islr.concept", string="Concepto ISLR", required=True
    )
    person_type = fields.Selection(
        PERSON_TYPES,
        string="Tipo de Persona",
        required=True,
        default="pj_dom",
    )
    seniat_code = fields.Char(
        string="Código SENIAT",
        size=3,
        readonly=True,
        copy=False,
        help="Código del anexo 6.1 del concepto para el tipo de persona, "
        "fijado al emitir el comprobante: el XML lo declara aunque el "
        "concepto cambie después.",
    )
    base = fields.Monetary(
        currency_field="currency_id",
        help="Monto pagado o abonado sin IVA (monto de la operación del XML).",
    )
    base_pct = fields.Float(
        string="Base Imponible (%)",
        digits=(5, 2),
        default=100.0,
        help="Porcentaje del monto pagado que constituye la base imponible "
        "(enriquecimiento presunto de no residentes).",
    )
    taxable_base = fields.Monetary(
        string="Base Imponible",
        currency_field="currency_id",
        help="Base sobre la que se aplica la tarifa: monto × porcentaje de "
        "base imponible.",
    )
    is_tarifa2 = fields.Boolean(
        string="Tarifa N° 2",
        help="Retención de persona jurídica no domiciliada con la Tarifa N° 2, "
        "calculada sobre la base imponible acumulada del proveedor en el año "
        "calendario. La tarifa es la efectiva sobre la base imponible.",
    )
    treaty_applied = fields.Boolean(
        string="Convenio de Doble Tributación",
        help="La tarifa es la del convenio para evitar la doble tributación "
        "del proveedor, aplicada sobre el monto bruto.",
    )
    treaty_certificate = fields.Char(string="Certificado de Residencia Fiscal")
    rate = fields.Float(string="Tarifa (%)", digits=(5, 2))
    subtrahend = fields.Monetary(string="Sustraendo", currency_field="currency_id")
    # amount = 0 is allowed by the SENIAT XML completeness rule.
    amount = fields.Monetary(string="Monto Retenido", currency_field="currency_id")
    state = fields.Selection(
        [("draft", "Borrador"), ("issued", "Emitido"), ("cancelled", "Anulado")],
        string="Estado",
        default="draft",
        copy=False,
    )
    company_vat = fields.Char(string="RIF del Agente", related="company_id.vat")
    partner_vat = fields.Char(string="RIF del Retenido", related="partner_id.vat")

    @api.depends("date")
    def _compute_period(self):
        for voucher in self:
            voucher.period = voucher.date and voucher.date.strftime("%Y%m") or False

    @api.depends("partner_id.email")
    def _compute_partner_email_missing(self):
        for voucher in self:
            voucher.partner_email_missing = bool(
                voucher.partner_id and not voucher.partner_id.email
            )

    @api.constrains("number", "date", "is_external", "company_id")
    def _check_external_number(self):
        # Only the numbers entered by hand: the sequence numbers the rest.
        for voucher in self.filtered("is_external"):
            if not VOUCHER_NUMBER_RE.match(voucher.number or ""):
                raise ValidationError(
                    self.env._(
                        "El número de comprobante de retención de ISLR debe "
                        "tener 14 dígitos: AAAAMM + secuencial de 8 dígitos "
                        "(ej. 20260700000001)."
                    )
                )
            if voucher.number[:6] != voucher.date.strftime("%Y%m"):
                raise ValidationError(
                    self.env._(
                        "El año y mes del número de comprobante %(number)s "
                        "deben ser los de su fecha de emisión (%(period)s).",
                        number=voucher.number,
                        period=voucher.date.strftime("%Y%m"),
                    )
                )
            if self.search_count(
                [
                    ("id", "!=", voucher.id),
                    ("company_id", "=", voucher.company_id.id),
                    ("number", "=", voucher.number),
                ],
                limit=1,
            ):
                raise ValidationError(
                    self.env._(
                        "Ya existe un comprobante de retención de ISLR con el "
                        "número %s en la compañía.",
                        voucher.number,
                    )
                )

    def _l10n_ve_islr_tarifa2_key(self):
        """Return the position of the voucher in the Tarifa N° 2 sequence.

        Vouchers accumulate by date, then bill, then concept; manual
        vouchers (without bill) come first within their date.
        """
        self.ensure_one()
        return (self.date, self.source_move_id.id or 0, self.concept_id.id)

    @api.constrains("base", "taxable_base", "subtrahend", "amount")
    def _check_non_negative(self):
        # The SENIAT XML rejects negative amounts: credit notes adjust the
        # voucher of their bill instead of issuing negative vouchers.
        for voucher in self:
            currency = voucher.currency_id
            if any(
                currency.compare_amounts(value, 0.0) < 0
                for value in (
                    voucher.base,
                    voucher.taxable_base,
                    voucher.subtrahend,
                    voucher.amount,
                )
            ):
                raise ValidationError(
                    self.env._(
                        "La base, la base imponible, el sustraendo y el monto "
                        "retenido de un comprobante de ISLR no pueden ser negativos."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Create draft vouchers with the fields a user may set.

        The number is assigned here by the sequence; the form never sends
        it, as the field is readonly, except for a voucher issued outside
        the system, which an accounting manager registers with its own.
        """
        self.check_access("create")
        for vals in vals_list:
            if vals.get("is_external"):
                self._l10n_ve_check_external(vals.get("number"))
            elif "number" in vals:
                raise UserError(
                    self.env._(
                        "El número del comprobante de retención de ISLR lo "
                        "asigna la secuencia del módulo y no puede indicarse."
                    )
                )
            if any(
                (vals[name] or False) != (neutral or False)
                for name, neutral in PROTECTED_FIELDS.items()
                if name in vals
            ):
                raise UserError(
                    self.env._(
                        "Un comprobante de retención de ISLR se crea en "
                        "borrador; el estado, los vínculos con documentos y "
                        "asientos y los valores calculados solo los fija el "
                        "módulo."
                    )
                )
        self._l10n_ve_islr_set_numbers(vals_list)
        return super().create(vals_list)

    @api.model
    def _l10n_ve_check_external(self, number):
        """Check who may register the number of an external voucher.

        Only the accounting manager group, the one allowed to create
        vouchers, and always with a number: a voucher issued outside the
        system brings its own and never consumes the sequence.
        """
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(
                self.env._(
                    "Solo un administrador de contabilidad puede registrar "
                    "el número de un comprobante emitido fuera del sistema."
                )
            )
        if not number or number == "/":
            raise UserError(
                self.env._(
                    "Indique el número del comprobante emitido fuera del sistema."
                )
            )

    @api.model
    def _l10n_ve_create_unlocked(self, vals_list):
        """Create vouchers from the trusted module flows."""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        self._l10n_ve_islr_set_numbers(vals_list)
        return super().create(vals_list)

    @api.model
    def _l10n_ve_islr_set_numbers(self, vals_list):
        for vals in vals_list:
            if not vals.get("number") or vals["number"] == "/":
                seq_date = fields.Date.to_date(
                    vals.get("date")
                ) or fields.Date.context_today(self)
                company = (
                    self.env["res.company"].browse(vals["company_id"])
                    if vals.get("company_id")
                    else self.env.company
                )
                sequence = self._l10n_ve_islr_get_sequence(company)
                self._l10n_ve_islr_ensure_month_range(sequence, seq_date)
                vals["number"] = sequence.next_by_id(sequence_date=seq_date)

    @api.model
    def _l10n_ve_islr_get_sequence(self, company):
        """Get or create the voucher sequence for the withholding company."""
        sequence = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", "l10n.ve.islr.voucher"),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
        )
        if not sequence:
            sequence = (
                self.env["ir.sequence"]
                .sudo()
                .create(
                    {
                        "name": self.env._(
                            "Comprobante de Retención ISLR (%s)", company.name
                        ),
                        "code": "l10n.ve.islr.voucher",
                        "prefix": "%(year)s%(month)s",
                        "padding": 8,
                        "implementation": "no_gap",
                        "use_date_range": True,
                        "company_id": company.id,
                    }
                )
            )
        return sequence

    @api.model
    def _l10n_ve_islr_ensure_month_range(self, sequence, seq_date):
        """Create an explicit monthly range so the sequence resets monthly."""
        date_range_model = self.env["ir.sequence.date_range"].sudo()
        if not date_range_model.search_count(
            [
                ("sequence_id", "=", sequence.id),
                ("date_from", "<=", seq_date),
                ("date_to", ">=", seq_date),
            ],
            limit=1,
        ):
            start = seq_date.replace(day=1)
            date_range_model.create(
                {
                    "sequence_id": sequence.id,
                    "date_from": start,
                    "date_to": start + relativedelta(months=1, days=-1),
                }
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_issued(self):
        if any(voucher.state != "draft" for voucher in self):
            raise UserError(
                self.env._(
                    "No se puede eliminar un comprobante de retención emitido "
                    "o anulado: el correlativo fiscal debe conservarse."
                )
            )

    def write(self, vals):
        """Lock the fiscal content of vouchers that left the draft state.

        Trusted module code paths use ``_l10n_ve_write_unlocked``; it is
        private, so it cannot be reached over RPC. The number is never
        writable, except by an accounting manager on a draft voucher issued
        outside the system.
        """
        self.check_access("write")
        if "is_external" in vals:
            raise UserError(
                self.env._(
                    "Si un comprobante fue emitido fuera del sistema solo se "
                    "indica al crearlo."
                )
            )
        if set(vals) - POSTED_WRITABLE_FIELDS and any(
            voucher.state != "draft" for voucher in self
        ):
            raise UserError(
                self.env._(
                    "Un comprobante de retención de ISLR emitido o anulado no "
                    "puede modificarse: anúlelo y emita uno nuevo."
                )
            )
        if "number" in vals:
            if not all(voucher._l10n_ve_is_manual_external() for voucher in self):
                raise UserError(
                    self.env._(
                        "El número del comprobante de retención de ISLR lo "
                        "asigna la secuencia del módulo y no puede modificarse."
                    )
                )
            self._l10n_ve_check_external(vals["number"])
        if any(
            voucher._l10n_ve_islr_value_differs(name, vals[name])
            for voucher in self
            for name in PROTECTED_FIELDS.keys() & vals.keys()
        ):
            raise UserError(
                self.env._(
                    "El estado, los vínculos con documentos y asientos y los "
                    "valores calculados de un comprobante de retención de ISLR "
                    "solo los fija el módulo."
                )
            )
        return super().write(vals)

    def _l10n_ve_is_manual_external(self):
        """Return whether the voucher is an external one entered by hand.

        Those are the only vouchers whose number a user may correct, and
        only while they are still drafts.
        """
        self.ensure_one()
        return (
            self.is_external
            and self.state == "draft"
            and not (self.source_move_id or self.wh_move_id or self.credit_note_id)
        )

    def _l10n_ve_islr_value_differs(self, name, value):
        self.ensure_one()
        current = self[name]
        if isinstance(current, models.BaseModel):
            current = current.id
        return (current or False) != (value or False)

    def _l10n_ve_write_unlocked(self, vals):
        return super().write(vals)

    @api.model
    def _l10n_ve_islr_control_number(self, move):
        """Return the control number of a document, when an addon adds it."""
        if "l10n_ve_control_number" in move._fields:
            return move.l10n_ve_control_number or ""
        return ""

    def _l10n_ve_islr_get_seniat_code(self):
        """Return the code declared for the voucher.

        The code fixed when the voucher was issued; a voucher created
        directly in the issued state has none and uses the concept's.
        """
        self.ensure_one()
        return self.seniat_code or self.concept_id._get_seniat_code(self.person_type)

    def action_issue(self):
        if any(voucher.state != "draft" for voucher in self):
            raise UserError(
                self.env._("Solo se pueden emitir comprobantes en borrador.")
            )
        for voucher in self:
            concept = voucher.concept_id
            if not concept._l10n_ve_islr_applies_to(voucher.person_type):
                raise UserError(
                    self.env._(
                        "El concepto de retención ISLR %(concept)s no tiene "
                        "código SENIAT para el tipo de persona %(person_type)s "
                        "del comprobante %(number)s: cambie el concepto o el "
                        "tipo de persona.",
                        concept=concept.name,
                        person_type=dict(PERSON_TYPES)[voucher.person_type],
                        number=voucher.number,
                    )
                )
            voucher._l10n_ve_write_unlocked(
                {
                    "state": "issued",
                    "seniat_code": concept._get_seniat_code(voucher.person_type),
                    "taxable_base": voucher.currency_id.round(
                        voucher.base * voucher.base_pct / 100.0
                    ),
                }
            )

    def action_cancel(self):
        """Cancel the voucher, keeping its number (no-gap sequence).

        Cancelling is the only way out of the issued state: an issued
        voucher never returns to draft, manual ones included, since its
        number may already have been delivered or declared. A mistaken
        voucher is cancelled and a new one issued.

        The state changes before the withholding entry is undone: the entry
        is protected against reset to draft only while its voucher is issued.
        The entry is cancelled, or reversed when it can no longer be
        modified, so the withheld tax returns to the vendor payable.
        """
        if any(voucher.state == "cancelled" for voucher in self):
            raise UserError(self.env._("El comprobante de retención ya está anulado."))
        to_undo = self.filtered(
            lambda voucher: voucher.state == "issued" and voucher.wh_move_id
        )
        self._l10n_ve_write_unlocked({"state": "cancelled"})
        for voucher in to_undo:
            voucher._l10n_ve_undo_wh_move()

    def _l10n_ve_undo_wh_move(self):
        self.ensure_one()
        # Accounting operations run with the caller's rights, not sudo.
        wh_move = self.wh_move_id.sudo(False)
        if wh_move.state != "posted":
            return
        if wh_move._can_be_unlinked():
            wh_move.button_cancel()
        else:
            wh_move.line_ids.remove_move_reconcile()
            wh_move._reverse_moves(
                [
                    {
                        "date": fields.Date.context_today(self),
                        "ref": self.env._("Anulación: %s", wh_move.ref or wh_move.name),
                    }
                ],
                cancel=True,
            )
