from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

VE_JOURNAL_EMISSION_TO_COMPANY_CODE = {
    "free": "free_form",
    "fiscal_machine": "fiscal_machine",
    "digital": "digital_billing",
}


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_emission_medium = fields.Selection(
        selection=[
            ("free", "Forma libre (correlativo de talonario)"),
            ("contingency", "Contingencia"),
            ("fiscal_machine", "Máquina fiscal"),
            ("digital", "Facturación digital"),
        ],
        string="Medio de emisión",
        default="free",
        copy=False,
        help=(
            "Forma libre: asigna correlativo desde el talonario interno. "
            "Contingencia: no usa el talonario; el N° de control se indica en la "
            "factura antes de confirmar. Máquina fiscal y facturación digital: "
            "tampoco generan correlativo automático del talonario; el N° de control "
            "debe consignarse manualmente antes de confirmar."
        ),
    )

    def _l10n_ve_company_emission_medium_code(self):
        """Map journal emission medium to company settings code, if applicable."""
        self.ensure_one()
        return VE_JOURNAL_EMISSION_TO_COMPANY_CODE.get(self.l10n_ve_emission_medium)

    l10n_ve_free_form_print_medium = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("continuous", "Papel continuo (ESC/P USB)"),
        ],
        string="Impresión en forma libre",
        default="pdf",
        copy=False,
        help=(
            "Solo aplica con medio de emisión «Forma libre». PDF usa el informe estándar. "
            "Papel continuo requiere el módulo «l10n_ve_invoice_escp» e imprime la factura "
            "en formato ESC/P Epson por WebUSB."
        ),
    )

    l10n_ve_invoice_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (invoices)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo del talonario para facturas de cliente. Si la ND usa otro tramo, "
        "configúrelo en “Notas de débito”.",
    )
    l10n_ve_debit_note_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (debit notes)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo opcional para notas de débito de cliente. Si está vacío, se usa "
        "el tramo de facturas.",
    )
    l10n_ve_credit_note_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (credit notes)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo del talonario para notas de crédito de cliente (out_refund).",
    )

    l10n_ve_fiscal_payment_code = fields.Char(
        string="Código forma de pago fiscal",
        size=2,
        copy=False,
        help=(
            "Código numérico de forma de pago para máquina fiscal TFHKA (01–24). "
            "Se usa al enviar pagos en la impresión fiscal cuando el registro proviene "
            "de este diario."
        ),
    )

    l10n_ve_max_invoice_lines = fields.Integer(
        string="Máximo de líneas por factura (diario)",
        default=10,
        copy=False,
        help=(
            "Si el medio de emisión no es «Forma libre», al facturar desde ventas se "
            "parte el pedido en varias facturas cuando supera este número de líneas de "
            "producto. Con «Forma libre» y tramo de talonario configurado, se usa el "
            "máximo definido en el talonario."
        ),
    )
    l10n_ve_max_picking_lines = fields.Integer(
        string="Máximo de líneas por guía de despacho (diario)",
        default=10,
        copy=False,
        help=(
            "Si el medio de emisión no es «Forma libre», al confirmar el pedido se "
            "dividen los albaranes de salida que superen este número de movimientos de "
            "producto. Con «Forma libre» y talonario en el tramo del diario, se usa el "
            "máximo del talonario."
        ),
    )

    @api.constrains("l10n_ve_fiscal_payment_code")
    def _check_l10n_ve_fiscal_payment_code(self):
        """Valida código de forma de pago para transmisión a máquina fiscal.

        Notes
        -----
        Art. 14 PA SNAT/2011/0071: requisitos de facturas en máquina fiscal.
        Art. 28 PA SNAT/2011/0071: validaciones mínimas del dispositivo.
        """

        for journal in self:
            raw = (journal.l10n_ve_fiscal_payment_code or "").strip()
            if not raw:
                continue
            if len(raw) != 2 or not raw.isdigit():
                raise ValidationError(
                    _(
                        "El código forma de pago fiscal del diario “%(journal)s” debe ser "
                        "dos dígitos (ej.: 01)."
                    )
                    % {"journal": journal.display_name}
                )
            value = int(raw)
            if value < 1 or value > 24:
                raise ValidationError(
                    _(
                        "El código forma de pago fiscal del diario “%(journal)s” debe estar "
                        "entre 01 y 24."
                    )
                    % {"journal": journal.display_name}
                )

    @api.constrains("l10n_ve_emission_medium", "l10n_ve_free_form_print_medium")
    def _check_l10n_ve_free_form_print_medium(self):
        for journal in self:
            if (
                journal.l10n_ve_free_form_print_medium == "continuous"
                and journal.l10n_ve_emission_medium != "free"
            ):
                raise ValidationError(
                    _(
                        "El formato «Papel continuo» solo está permitido cuando el medio de "
                        "emisión del diario «%(journal)s» es «Forma libre»."
                    )
                    % {"journal": journal.display_name}
                )

    @api.constrains("l10n_ve_max_invoice_lines", "l10n_ve_max_picking_lines")
    def _check_l10n_ve_journal_max_lines(self):
        for journal in self:
            if (
                journal.l10n_ve_max_invoice_lines is not None
                and journal.l10n_ve_max_invoice_lines < 1
            ):
                raise ValidationError(
                    _(
                        "El máximo de líneas por factura del diario «%(journal)s» debe "
                        "ser al menos 1."
                    )
                    % {"journal": journal.display_name}
                )
            if (
                journal.l10n_ve_max_picking_lines is not None
                and journal.l10n_ve_max_picking_lines < 1
            ):
                raise ValidationError(
                    _(
                        "El máximo de líneas por guía del diario «%(journal)s» debe "
                        "ser al menos 1."
                    )
                    % {"journal": journal.display_name}
                )

    @api.constrains(
        "l10n_ve_invoice_section_id",
        "l10n_ve_debit_note_section_id",
        "l10n_ve_credit_note_section_id",
        "company_id",
    )
    def _check_l10n_ve_sections_company(self):
        for journal in self:
            for sec in (
                journal.l10n_ve_invoice_section_id,
                journal.l10n_ve_debit_note_section_id,
                journal.l10n_ve_credit_note_section_id,
            ):
                if sec and sec.company_id != journal.company_id:
                    raise ValidationError(
                        _(
                            "The fiscal book section “%(sec)s” belongs to another "
                            "company than journal “%(journal)s”."
                        )
                        % {
                            "sec": sec.display_name,
                            "journal": journal.display_name,
                        }
                    )
