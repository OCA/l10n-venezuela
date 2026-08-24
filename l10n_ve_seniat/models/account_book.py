# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountBook(models.Model):
    _name = "account.book"
    _description = "Fiscal control book (talonario)"
    _order = "company_id, name, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    l10n_ve_series_prefix = fields.Char(
        string="Prefijo/Serie",
        default="00",
        help=(
            "Prefijo de establecimiento o serie SENIAT. Se aplica al número de control "
            "y al prefijo de las secuencias de todos los tramos."
        ),
    )
    number_from = fields.Integer(string="Start number", required=True)
    number_to = fields.Integer(string="End number", required=True)
    section_ids = fields.One2many(
        "account.book.section",
        "book_id",
        string="Sections",
    )
    section_count = fields.Integer(
        string="Sections count",
        compute="_compute_section_count",
    )
    document_ids = fields.One2many(
        "account.book.document",
        "book_id",
        string="Correlatives",
    )
    document_count = fields.Integer(
        string="Documents count",
        compute="_compute_document_count",
    )
    l10n_ve_void_folio_count_month = fields.Integer(
        string="Anulaciones de folio (mes actual)",
        compute="_compute_l10n_ve_void_folio_month_stats",
    )
    l10n_ve_void_folio_alert = fields.Boolean(
        compute="_compute_l10n_ve_void_folio_month_stats",
    )
    l10n_ve_void_folio_alert_text = fields.Text(
        compute="_compute_l10n_ve_void_folio_month_stats",
    )
    l10n_ve_max_invoice_lines = fields.Integer(
        string="Máximo de líneas por factura",
        default=10,
        help="Al facturar desde ventas, si el pedido supera este número de líneas de "
        "producto, se generarán varias facturas respetando el límite.",
    )
    l10n_ve_escp_invoice_margin_lines = fields.Integer(
        string="Líneas de margen (factura ESC/P)",
        default=8,
        help=(
            "Líneas en blanco al inicio del papel continuo antes del encabezado al "
            "imprimir la factura en formato ESC/P (impresora matriz). Use 0 si no "
            "requiere margen superior."
        ),
    )
    l10n_ve_invoice_header_spacing = fields.Integer(
        string="Espaciado de encabezado (factura PDF)",
        default=30,
        help=(
            "Espaciado superior del encabezado al imprimir facturas en PDF. "
            "Se aplica mediante el formato de papel asociado a este talonario."
        ),
    )
    paperformat_id = fields.Many2one(
        "report.paperformat",
        string="Formato de papel (factura PDF)",
        copy=False,
        readonly=True,
        help="Formato de papel generado automáticamente para imprimir facturas "
        "asignadas a este talonario.",
    )
    l10n_ve_max_picking_lines = fields.Integer(
        string="Máximo de líneas por guía de despacho",
        default=10,
        help="Al confirmar un pedido, si un albarán supera este número de movimientos "
        "de producto, se dividirá en varias guías de despacho.",
    )
    l10n_ve_setup_guide = fields.Html(
        string="Guía de configuración del talonario",
        compute="_compute_l10n_ve_setup_guide",
        sanitize=False,
    )

    _sql_constraints = [
        (
            "account_book_number_range",
            "CHECK(number_from <= number_to)",
            "The start number must be less than or equal to the end number.",
        ),
        (
            "account_book_number_positive",
            "CHECK(number_from >= 0 AND number_to >= 0)",
            "Numbers must be positive or zero.",
        ),
    ]

    @api.depends("section_ids")
    def _compute_section_count(self):
        for book in self:
            book.section_count = len(book.section_ids)

    @api.depends("document_ids")
    def _compute_document_count(self):
        for book in self:
            book.document_count = len(book.document_ids)

    @api.depends("document_ids", "document_ids.res_model", "document_ids.create_date")
    def _compute_l10n_ve_void_folio_month_stats(self):
        void_model = "l10n_ve.book.folio.void"
        for book in self:
            ref_date = fields.Date.context_today(book)
            n = 0
            for doc in book.document_ids:
                if doc.res_model != void_model or not doc.create_date:
                    continue
                local_d = fields.Datetime.context_timestamp(
                    book, doc.create_date
                ).date()
                if local_d.year == ref_date.year and local_d.month == ref_date.month:
                    n += 1
            book.l10n_ve_void_folio_count_month = n
            book.l10n_ve_void_folio_alert = n > 0
            book.l10n_ve_void_folio_alert_text = (
                _(
                    "Hay %(n)s anulación(es) de folio registrada(s) en el mes actual "
                    "en este talonario."
                )
                % {"n": n}
                if n
                else ""
            )

    @api.constrains(
        "l10n_ve_max_invoice_lines",
        "l10n_ve_max_picking_lines",
        "l10n_ve_escp_invoice_margin_lines",
        "l10n_ve_invoice_header_spacing",
    )
    def _check_l10n_ve_max_lines_positive(self):
        for book in self:
            if (
                book.l10n_ve_max_invoice_lines is not None
                and book.l10n_ve_max_invoice_lines < 1
            ):
                raise ValidationError(
                    _("El máximo de líneas por factura debe ser al menos 1.")
                )
            if (
                book.l10n_ve_max_picking_lines is not None
                and book.l10n_ve_max_picking_lines < 1
            ):
                raise ValidationError(
                    _("El máximo de líneas por guía de despacho debe ser al menos 1.")
                )
            if book.l10n_ve_escp_invoice_margin_lines is not None:
                m = book.l10n_ve_escp_invoice_margin_lines
                if m < 0 or m > 127:
                    raise ValidationError(
                        _("Las líneas de margen ESC/P deben estar entre 0 y 127.")
                    )
            if (
                book.l10n_ve_invoice_header_spacing is not None
                and book.l10n_ve_invoice_header_spacing < 0
            ):
                raise ValidationError(
                    _(
                        "El espaciado de encabezado de la factura PDF debe ser "
                        "positivo o cero."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        books = super().create(vals_list)
        books._l10n_ve_ensure_paperformat()
        return books

    def write(self, vals):
        res = super().write(vals)
        if any(
            field in vals
            for field in ("name", "l10n_ve_invoice_header_spacing", "company_id")
        ):
            self._l10n_ve_ensure_paperformat()
        if "l10n_ve_series_prefix" in vals:
            self._l10n_ve_sync_section_sequence_prefixes()
        return res

    def _l10n_ve_paperformat_template(self):
        return self.env.ref(
            "l10n_ve_seniat.paperformat_invoice_ve_small",
            raise_if_not_found=False,
        )

    def _l10n_ve_paperformat_vals(self):
        self.ensure_one()
        template = self._l10n_ve_paperformat_template()
        return {
            "name": _("Factura VE - %(book)s (%(company)s)")
            % {
                "book": self.name,
                "company": self.company_id.display_name,
            },
            "default": False,
            "format": template.format if template else "A4",
            "page_height": template.page_height if template else 0,
            "page_width": template.page_width if template else 0,
            "orientation": template.orientation if template else "Portrait",
            "margin_top": template.margin_top if template else 30,
            "margin_bottom": template.margin_bottom if template else 20,
            "margin_left": template.margin_left if template else 0,
            "margin_right": template.margin_right if template else 0,
            "header_line": template.header_line if template else False,
            "header_spacing": self.l10n_ve_invoice_header_spacing,
            "dpi": template.dpi if template else 90,
            "css_margins": template.css_margins if template else True,
        }

    def _l10n_ve_ensure_paperformat(self):
        Paperformat = self.env["report.paperformat"].sudo()
        for book in self:
            vals = book._l10n_ve_paperformat_vals()
            if book.paperformat_id:
                book.paperformat_id.sudo().write(vals)
            else:
                paperformat = Paperformat.create(vals)
                book.sudo().write({"paperformat_id": paperformat.id})

    @api.depends("active")
    def _compute_l10n_ve_setup_guide(self):
        html = self.env["account.book"].l10n_ve_setup_guide_html()
        for book in self:
            book.l10n_ve_setup_guide = html

    @api.model
    def l10n_ve_setup_guide_html(self):
        return Markup(
            '<div class="alert alert-info" role="alert">'
            '<p class="fw-bold mb-2">%s</p>'
            '<ul class="mb-0">'
            "<li>%s</li>"
            "<li>%s</li>"
            "<li>%s</li>"
            "<li>%s</li>"
            "<li>%s</li>"
            "<li>%s</li>"
            "</ul></div>"
        ) % (
            _("Pasos para configurar el talonario (SENIAT)"),
            _(
                "Indique el rango global del talonario (desde / hasta). "
                "Todos los números de control deben quedar dentro de ese intervalo."
            ),
            _(
                "En la pestaña «Tramos», divida el rango en segmentos contiguos "
                "sin solaparse. Cada tramo recibe una secuencia interna enlazada "
                "automáticamente."
            ),
            _(
                "«Prefijo/Serie» (por defecto 00) forma parte del número de control "
                "y del prefijo de las secuencias de los tramos. Si lo modifica tras "
                "crear tramos, pulse «Sincronizar secuencias de tramos»."
            ),
            _(
                "En el diario de ventas (Contabilidad → Diarios → pestaña SENIAT "
                "Talonario) asigne el tramo de facturas, el de notas de crédito y, "
                "si lo usa, el de notas de débito. Sin tramo no se asignará "
                "correlativo al publicar."
            ),
            _(
                "La pestaña «Correlatives» permite al administrador contable "
                "corregir o eliminar correlativos. Al modificar una línea se "
                "actualiza el N° de control del documento enlazado; al eliminarla "
                "se limpia ese N° de control."
            ),
            _(
                "«Sincronizar secuencias de tramos» alinea prefijos y el siguiente "
                "número de cada secuencia con los correlativos ya registrados en el "
                "talonario."
            ),
        )

    def _l10n_ve_ir_sequence_full_prefix(self):
        self.ensure_one()
        p = (self.l10n_ve_series_prefix or "00").strip() or "00"
        p = p.rstrip("-")
        return f"{p}-"

    def _l10n_ve_format_control_number(self, number):
        """Formatea el N° de control con prefijo de serie SENIAT.

        Parameters
        ----------
        number : int
            Correlativo numérico del tramo.

        Returns
        -------
        str

        Notes
        -----
        Art. 13 num. 3-4 PA SNAT/2011/0071: N° de control.
        Art. 27 PA SNAT/2011/0071: serie y numeración consecutiva.
        """

        self.ensure_one()
        p = (self.l10n_ve_series_prefix or "00").strip() or "00"
        p = p.rstrip("-")
        return f"{p}-{int(number):08d}"

    def l10n_ve_peek_next_formatted(self, section):
        self.ensure_one()
        if not section or section.book_id != self:
            return False
        try:
            number = self._l10n_ve_next_correlative_number_for_section(section)
        except ValidationError:
            return False
        return self._l10n_ve_format_control_number(number)

    def _l10n_ve_sync_section_sequence_prefixes(self):
        for book in self:
            prefix = book._l10n_ve_ir_sequence_full_prefix()
            for section in book.section_ids:
                section._l10n_ve_ensure_sequence()
                seq = section.l10n_ve_sequence_id
                if seq:
                    seq.sudo().write({"prefix": prefix})

    def action_l10n_ve_sync_section_sequences(self):
        for book in self:
            book._l10n_ve_sync_section_sequence_prefixes()
            for section in book.section_ids:
                section._l10n_ve_refresh_sequence_number_next()
        return True

    def l10n_ve_allocate_void_folio(self, section, reason):
        """Registra anulación de folio en el talonario fiscal.

        Notes
        -----
        Art. 27 PA SNAT/2011/0071: control de numeración.
        Art. 28 PA SNAT/2011/0071: integridad de documentos fiscales.
        """

        self.ensure_one()
        if section.book_id != self:
            raise ValidationError(_("El tramo no pertenece a este talonario."))
        void = self.env["l10n_ve.book.folio.void"].create(
            {
                "book_id": self.id,
                "section_id": section.id,
                "reason": reason,
            }
        )
        number = self._l10n_ve_next_correlative_number_for_section(section)
        self.env["account.book.document"].create(
            {
                "book_id": self.id,
                "section_id": section.id,
                "number": number,
                "res_model": "l10n_ve.book.folio.void",
                "res_id": void.id,
            }
        )
        section._l10n_ve_refresh_sequence_number_next()
        return True

    def action_l10n_ve_open_void_folio_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Anular folio"),
            "res_model": "l10n_ve.book.folio.void.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_book_id": self.id},
        }

    def _l10n_ve_last_document_in_section_span(self, section):
        self.ensure_one()
        if section.book_id != self:
            raise ValidationError(_("El tramo no pertenece a este talonario."))
        Document = self.env["account.book.document"]
        Document.flush_model(["number", "book_id"])
        return Document.search(
            [
                ("book_id", "=", self.id),
                ("number", ">=", section.number_from),
                ("number", "<=", section.number_to),
            ],
            order="number desc",
            limit=1,
        )

    def _l10n_ve_next_correlative_number_for_section(self, section):
        self.ensure_one()
        last_doc = self._l10n_ve_last_document_in_section_span(section)
        if last_doc:
            candidate = last_doc.number + 1
        else:
            candidate = section.number_from
        if candidate > section.number_to:
            raise ValidationError(
                _(
                    "No hay correlativos disponibles en el tramo «%(sec)s» "
                    "(%(sf)s–%(st)s) del talonario «%(book)s»."
                )
                % {
                    "sec": section.display_name,
                    "sf": section.number_from,
                    "st": section.number_to,
                    "book": self.display_name,
                }
            )
        return candidate

    def l10n_ve_allocate_correlative(self, section, origin_record):
        """Reserva el siguiente correlativo del talonario para un documento fiscal.

        Parameters
        ----------
        section : account.book.section
            Tramo del talonario.
        origin_record : recordset
            Documento origen (p. ej. ``account.move``).

        Returns
        -------
        account.book.document

        Notes
        -----
        Art. 13 num. 2-4 PA SNAT/2011/0071: numeración consecutiva y N° de control.
        Art. 29-31 PA SNAT/2011/0071: formatos de imprenta autorizada.
        """

        self.ensure_one()
        origin_record.ensure_one()
        number = self._l10n_ve_next_correlative_number_for_section(section)
        formatted = self._l10n_ve_format_control_number(number)
        self.env["account.book.document"].create(
            {
                "book_id": self.id,
                "section_id": section.id,
                "number": number,
                "res_model": origin_record._name,
                "res_id": origin_record.id,
            }
        )
        section._l10n_ve_refresh_sequence_number_next()
        return formatted

    def _validate_section_ranges(self):
        """Valida que los tramos del talonario no se solapen ni excedan el libro.

        Notes
        -----
        Art. 27 PA SNAT/2011/0071: serie y numeración.
        Art. 29 PA SNAT/2011/0071: rangos autorizados por imprenta.
        """

        for book in self:
            sections = book.section_ids
            for sec in sections:
                if sec.number_from < book.number_from or sec.number_to > book.number_to:
                    raise ValidationError(
                        _(
                            "Section “%(sec)s” (from %(sf)s to %(st)s) must fall "
                            "within the book range %(bf)s–%(bt)s."
                        )
                        % {
                            "sec": sec.display_name,
                            "sf": sec.number_from,
                            "st": sec.number_to,
                            "bf": book.number_from,
                            "bt": book.number_to,
                        }
                    )
            ordered = sections.sorted(lambda s: (s.number_from, s.number_to))
            for i, a in enumerate(ordered):
                for b in ordered[i + 1 :]:
                    if max(a.number_from, b.number_from) <= min(
                        a.number_to, b.number_to
                    ):
                        raise ValidationError(
                            _(
                                "Sections cannot overlap: %(a)s (%(af)s–%(at)s) and "
                                "%(b)s (%(bf)s–%(bt)s)."
                            )
                            % {
                                "a": a.display_name,
                                "af": a.number_from,
                                "at": a.number_to,
                                "b": b.display_name,
                                "bf": b.number_from,
                                "bt": b.number_to,
                            }
                        )

    @api.constrains("section_ids", "number_from", "number_to")
    def _check_sections_overlap(self):
        self._validate_section_ranges()

    @api.constrains("number_from", "number_to")
    def _check_documents_within_book(self):
        for book in self:
            for doc in book.document_ids:
                if not (book.number_from <= doc.number <= book.number_to):
                    raise ValidationError(
                        _(
                            "Correlative %(num)s is outside the book range "
                            "%(bf)s–%(bt)s."
                        )
                        % {
                            "num": doc.number,
                            "bf": book.number_from,
                            "bt": book.number_to,
                        }
                    )

    def unlink(self):
        paperformats = self.mapped("paperformat_id")
        self.env["account.book.document"].with_context(
            l10n_ve_allow_book_document_unlink=True
        ).search([("book_id", "in", self.ids)]).unlink()
        res = super().unlink()
        paperformats.sudo().unlink()
        return res


class AccountBookSection(models.Model):
    _name = "account.book.section"
    _description = "Fiscal control book section"
    _order = "book_id, number_from, id"

    name = fields.Char(translate=True)
    book_id = fields.Many2one(
        "account.book",
        string="Book",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="book_id.company_id",
        store=True,
        readonly=True,
    )
    number_from = fields.Integer(required=True)
    number_to = fields.Integer(required=True)
    l10n_ve_sequence_id = fields.Many2one(
        "ir.sequence",
        string="SENIAT sequence",
        copy=False,
        ondelete="restrict",
    )

    _sql_constraints = [
        (
            "account_book_section_number_range",
            "CHECK(number_from <= number_to)",
            "The section start number must be less than or equal to the end number.",
        ),
        (
            "account_book_section_number_positive",
            "CHECK(number_from >= 0 AND number_to >= 0)",
            "Section numbers must be positive or zero.",
        ),
    ]

    @api.constrains("number_from", "number_to", "book_id")
    def _check_section_in_book(self):
        self.mapped("book_id")._validate_section_ranges()

    @api.constrains("number_from", "number_to")
    def _check_section_documents(self):
        Document = self.env["account.book.document"]
        for sec in self:
            for doc in Document.search([("section_id", "=", sec.id)]):
                if not (sec.number_from <= doc.number <= sec.number_to):
                    raise ValidationError(
                        _(
                            "Section “%(sec)s” cannot be changed: correlative %(num)s "
                            "would fall outside the new range."
                        )
                        % {"sec": sec.display_name, "num": doc.number}
                    )

    @api.model_create_multi
    def create(self, vals_list):
        sections = super().create(vals_list)
        sections.with_context(
            skip_l10n_ve_section_sequence_patch=True
        )._l10n_ve_ensure_sequences_batch()
        return sections

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_l10n_ve_section_sequence_patch"):
            return res
        if "book_id" in vals:
            for section in self:
                seq = section.l10n_ve_sequence_id
                if seq:
                    section.with_context(
                        skip_l10n_ve_section_sequence_patch=True
                    ).write({"l10n_ve_sequence_id": False})
                    seq.sudo().unlink()
                section._l10n_ve_ensure_sequence()
                section._l10n_ve_refresh_sequence_number_next()
        elif "number_from" in vals or "number_to" in vals:
            self._l10n_ve_refresh_sequence_number_next()
        return res

    def unlink(self):
        sequences = self.mapped("l10n_ve_sequence_id")
        res = super().unlink()
        sequences.sudo().unlink()
        return res

    def _l10n_ve_ensure_sequences_batch(self):
        for section in self:
            section._l10n_ve_ensure_sequence()

    def _l10n_ve_ensure_sequence(self):
        for section in self:
            if section.l10n_ve_sequence_id:
                continue
            section._l10n_ve_create_sequence()

    def _l10n_ve_create_sequence(self):
        self.ensure_one()
        if self.l10n_ve_sequence_id:
            return
        book = self.book_id
        prefix = book._l10n_ve_ir_sequence_full_prefix()
        Document = self.env["account.book.document"]
        last_doc = Document.search(
            [
                ("book_id", "=", book.id),
                ("number", ">=", self.number_from),
                ("number", "<=", self.number_to),
            ],
            order="number desc",
            limit=1,
        )
        number_next = last_doc.number + 1 if last_doc else self.number_from
        name = _("%(book)s — %(section)s (SENIAT)") % {
            "book": book.name or book.id,
            "section": self.display_name,
        }
        seq = (
            self.env["ir.sequence"]
            .sudo()
            .create(
                {
                    "name": name,
                    "code": f"l10n_ve_book_section_{self.id}",
                    "implementation": "standard",
                    "prefix": prefix,
                    "padding": 8,
                    "number_increment": 1,
                    "number_next": number_next,
                    "company_id": book.company_id.id,
                }
            )
        )
        self.with_context(skip_l10n_ve_section_sequence_patch=True).write(
            {"l10n_ve_sequence_id": seq.id}
        )

    def _l10n_ve_refresh_sequence_number_next(self):
        Document = self.env["account.book.document"]
        for section in self:
            seq = section.l10n_ve_sequence_id
            if not seq:
                continue
            last_doc = Document.search(
                [
                    ("book_id", "=", section.book_id.id),
                    ("number", ">=", section.number_from),
                    ("number", "<=", section.number_to),
                ],
                order="number desc",
                limit=1,
            )
            number_next = last_doc.number + 1 if last_doc else section.number_from
            seq.sudo().write({"number_next": number_next})

    def name_get(self):
        result = []
        for sec in self:
            label = sec.name or f"{sec.number_from:g}-{sec.number_to:g}"
            result.append((sec.id, label))
        return result


class AccountBookDocument(models.Model):
    _name = "account.book.document"
    _description = "Control correlatives assigned to a document"
    _order = "book_id, number, id"

    book_id = fields.Many2one(
        "account.book",
        string="Book",
        required=True,
        ondelete="cascade",
        index=True,
    )
    section_id = fields.Many2one(
        "account.book.section",
        string="Section",
        ondelete="set null",
        domain="[('book_id', '=', book_id)]",
    )
    company_id = fields.Many2one(
        related="book_id.company_id",
        store=True,
        readonly=True,
    )
    number = fields.Integer(
        string="Correlative number",
        required=True,
        index=True,
    )
    l10n_ve_control_number = fields.Char(
        string="N° de control",
        compute="_compute_l10n_ve_control_number",
    )
    res_model = fields.Char(
        string="Referenced model",
        required=True,
        index=True,
    )
    res_id = fields.Many2oneReference(
        string="Referenced record id",
        model_field="res_model",
        required=True,
    )
    source_record = fields.Reference(
        string="Referenced record",
        selection="_selection_document_ref",
        compute="_compute_source_record",
        readonly=True,
    )
    l10n_ve_correlative_label = fields.Char(
        string="Documento / motivo",
        compute="_compute_l10n_ve_correlative_label",
    )

    _sql_constraints = [
        (
            "account_book_document_number_book_uniq",
            "UNIQUE(book_id, number)",
            "This correlative number is already used in this book.",
        ),
        (
            "account_book_document_book_res_uniq",
            "UNIQUE(book_id, res_model, res_id)",
            "This record is already linked to a correlative in this book.",
        ),
    ]

    @api.model
    def _selection_document_ref(self):
        selection = [
            ("account.move", "Invoice / credit note / debit note"),
            ("l10n_ve.book.folio.void", "Anulación de folio (sin movimiento)"),
        ]
        if "stock.picking" in self.env:
            selection.append(
                ("stock.picking", "Dispatch guide (picking)"),
            )
        return selection

    @api.model
    def _l10n_ve_allowed_res_models(self):
        return {code for code, _ in self._selection_document_ref()}

    @api.depends("res_model", "res_id")
    def _compute_source_record(self):
        for line in self:
            if line.res_model and line.res_id:
                line.source_record = line.env[line.res_model].browse(line.res_id)
            else:
                line.source_record = False

    @api.depends("number", "book_id", "book_id.l10n_ve_series_prefix")
    def _compute_l10n_ve_control_number(self):
        for line in self:
            if line.book_id and line.number:
                line.l10n_ve_control_number = (
                    line.book_id._l10n_ve_format_control_number(line.number)
                )
            else:
                line.l10n_ve_control_number = False

    @api.depends("res_model", "res_id", "source_record")
    def _compute_l10n_ve_correlative_label(self):
        void_model = "l10n_ve.book.folio.void"
        for line in self:
            if line.res_model == void_model and line.res_id:
                void = self.env[void_model].browse(line.res_id)
                line.l10n_ve_correlative_label = void.reason if void.exists() else ""
            elif line.source_record:
                line.l10n_ve_correlative_label = line.source_record.display_name
            else:
                line.l10n_ve_correlative_label = ""

    @api.constrains("res_model")
    def _check_res_model_allowed(self):
        allowed = self._l10n_ve_allowed_res_models()
        for line in self:
            if line.res_model and line.res_model not in allowed:
                raise ValidationError(
                    _("Model “%(m)s” is not allowed for fiscal correlatives.")
                    % {"m": line.res_model}
                )

    @api.constrains("number", "book_id", "section_id")
    def _check_correlative_sequence_no_gaps(self):
        """Verifica continuidad de correlativos asignados en el tramo.

        Notes
        -----
        Art. 13 num. 2 PA SNAT/2011/0071: numeración consecutiva y única.
        """

        if self.env.context.get("l10n_ve_allow_book_document_admin_edit"):
            return
        for line in self:
            book = line.book_id
            if not book:
                continue
            for section in book.section_ids:
                docs = self.search(
                    [
                        ("book_id", "=", book.id),
                        ("number", ">=", section.number_from),
                        ("number", "<=", section.number_to),
                    ]
                )
                nums = sorted(set(docs.mapped("number")))
                if not nums:
                    continue
                if nums[0] != section.number_from:
                    raise ValidationError(
                        _(
                            "En el tramo «%(sec)s» del talonario «%(book)s», los "
                            "correlativos deben empezar en %(start)s."
                        )
                        % {
                            "sec": section.display_name,
                            "book": book.display_name,
                            "start": section.number_from,
                        }
                    )
                for i in range(1, len(nums)):
                    if nums[i] != nums[i - 1] + 1:
                        raise ValidationError(
                            _(
                                "No se permiten saltos en el tramo «%(sec)s» del "
                                "talonario «%(book)s». Falta el número %(missing)s."
                            )
                            % {
                                "sec": section.display_name,
                                "book": book.display_name,
                                "missing": nums[i - 1] + 1,
                            }
                        )

    @api.constrains("number", "book_id", "section_id")
    def _check_number_in_ranges(self):
        """Valida que el correlativo esté dentro del rango autorizado del tramo.

        Notes
        -----
        Art. 13 num. 4 PA SNAT/2011/0071: total de N° de control asignados.
        Art. 27 PA SNAT/2011/0071: rangos de serie.
        """

        for line in self:
            book = line.book_id
            if not book:
                continue
            if not (book.number_from <= line.number <= book.number_to):
                raise ValidationError(
                    _(
                        "Correlative %(num)s must be between %(bf)s and %(bt)s "
                        "for this book."
                    )
                    % {
                        "num": line.number,
                        "bf": book.number_from,
                        "bt": book.number_to,
                    }
                )
            if line.section_id:
                sec = line.section_id
                if sec.book_id != book:
                    raise ValidationError(_("The section belongs to another book."))
                if not (sec.number_from <= line.number <= sec.number_to):
                    raise ValidationError(
                        _(
                            "Correlative %(num)s must fall within section "
                            "“%(sec)s” (%(sf)s–%(st)s)."
                        )
                        % {
                            "num": line.number,
                            "sec": sec.display_name,
                            "sf": sec.number_from,
                            "st": sec.number_to,
                        }
                    )

    @api.constrains("res_model", "res_id", "book_id")
    def _check_document_company(self):
        for line in self:
            if not line.res_model or not line.res_id or not line.book_id:
                continue
            ref = line.env[line.res_model].browse(line.res_id).exists()
            if not ref:
                continue
            book_company = line.book_id.company_id
            doc_company = False
            if line.res_model == "account.move" and "company_id" in ref._fields:
                doc_company = ref.company_id
            elif line.res_model == "stock.picking" and "company_id" in ref._fields:
                doc_company = ref.company_id
            if doc_company and doc_company != book_company:
                raise ValidationError(
                    _("The document company must match the book company (%(c)s).")
                    % {"c": book_company.display_name}
                )

    def _l10n_ve_check_can_admin_edit(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise ValidationError(
                _(
                    "Solo un administrador contable puede modificar o eliminar "
                    "correlativos del talonario."
                )
            )

    def _l10n_ve_sync_source_control_number(self, clear=False):
        for line in self:
            if not line.res_model or not line.res_id:
                continue
            record = line.env[line.res_model].browse(line.res_id).exists()
            if record and "l10n_ve_control_number" in record._fields:
                record.write(
                    {
                        "l10n_ve_control_number": (
                            False
                            if clear
                            else line.book_id._l10n_ve_format_control_number(
                                line.number
                            )
                        )
                    }
                )

    def write(self, vals):
        if self.ids and ("number" in vals or "book_id" in vals or "section_id" in vals):
            self._l10n_ve_check_can_admin_edit()
            sections = self.mapped("section_id")
            docs = self.with_context(l10n_ve_allow_book_document_admin_edit=True)
            res = super(AccountBookDocument, docs).write(vals)
            self._l10n_ve_sync_source_control_number()
            (
                sections | self.mapped("section_id")
            )._l10n_ve_refresh_sequence_number_next()
            return res
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_internal_book_cleanup(self):
        if not self.env.context.get("l10n_ve_allow_book_document_unlink"):
            self._l10n_ve_check_can_admin_edit()

    def unlink(self):
        if not self.env.context.get("l10n_ve_allow_book_document_unlink"):
            self._l10n_ve_check_can_admin_edit()
        sections = self.mapped("section_id")
        self._l10n_ve_sync_source_control_number(clear=True)
        res = super().unlink()
        sections._l10n_ve_refresh_sequence_number_next()
        return res
