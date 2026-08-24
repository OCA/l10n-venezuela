import base64
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .edi_mixin import STATE_FAILED, STATE_NOT_SENT, STATE_QUEUED, STATE_SENT


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "l10n_ve.edi.mixin"]

    l10n_ve_edi_journal_id = fields.Many2one(
        related="journal_id",
        string="EDI Journal",
    )

    l10n_ve_edi_show_tab = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_tab",
        string="Show EDI Tab",
    )

    @api.depends(
        "journal_id",
        "journal_id.l10n_ve_edi_provider",
        "journal_id.l10n_ve_emission_medium",
    )
    def _compute_l10n_ve_edi_show_tab(self):
        for move in self:
            journal = move.journal_id
            provider = journal.l10n_ve_edi_provider if journal else False
            move.l10n_ve_edi_show_tab = bool(
                journal
                and journal.l10n_ve_emission_medium == "digital"
                and provider
                and provider != "none"
            )

    def write(self, vals):
        res = super().write(vals)
        if vals.get("l10n_ve_edi_send_state") == STATE_SENT:
            ve_code = self.env.ref("base.ve").code
            for move in self:
                if (
                    move.country_code == ve_code
                    and move.move_type in ("out_invoice", "out_refund")
                    and move.l10n_ve_journal_emission_medium == "digital"
                    and move.l10n_ve_edi_sent_at
                ):
                    move.write({"l10n_ve_invoice_date": move.l10n_ve_edi_sent_at})
        return res

    l10n_ve_edi_portal_digital_printer_url = fields.Char(
        compute="_compute_l10n_ve_edi_portal_digital_printer_url",
        string="Portal: URL imprenta digital",
    )
    l10n_ve_edi_portal_show_abrir_imprenta = fields.Boolean(
        compute="_compute_l10n_ve_edi_portal_show_abrir_imprenta",
        string="Portal: mostrar Abrir en imprenta",
    )

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "journal_id.l10n_ve_emission_medium",
        "journal_id.l10n_ve_edi_provider",
        "l10n_ve_edi_send_state",
        "l10n_ve_edi_response_json",
    )
    def _compute_l10n_ve_edi_portal_digital_printer_url(self):
        for move in self:
            url = move._l10n_ve_edi_get_portal_digital_printer_url()
            move.l10n_ve_edi_portal_digital_printer_url = url if url else ""

    @api.depends(
        "l10n_ve_edi_portal_digital_printer_url",
        "country_code",
        "move_type",
        "state",
        "journal_id.l10n_ve_emission_medium",
        "l10n_ve_edi_send_state",
    )
    def _compute_l10n_ve_edi_portal_show_abrir_imprenta(self):
        for move in self:
            move.l10n_ve_edi_portal_show_abrir_imprenta = bool(
                move.l10n_ve_edi_portal_digital_printer_url
                and move.state == "posted"
                and move.country_code == "VE"
                and move.move_type in ("out_invoice", "out_refund")
                and move.l10n_ve_edi_send_state == STATE_SENT
                and move.journal_id.l10n_ve_emission_medium == "digital"
            )

    def _l10n_ve_edi_get_portal_digital_printer_url(self):
        self.ensure_one()
        return False

    def _generate_control_number(self):
        self.ensure_one()
        if (
            self.journal_id.l10n_ve_edi_provider
            and self.journal_id.l10n_ve_edi_provider != "none"
        ):
            return
        return super()._generate_control_number()

    def _l10n_ve_should_show_control_number_ui(self):
        if super()._l10n_ve_should_show_control_number_ui():
            return True
        self.ensure_one()
        ve_code = self.env.ref("base.ve").code
        if (
            self.country_code == ve_code
            and self.move_type in ("in_invoice", "in_refund")
            and self.state == "posted"
        ):
            if not (self.l10n_ve_control_number or "").strip():
                return True
            if (
                "l10n_ve_invoice_number" in self._fields
                and not (self.l10n_ve_invoice_number or self.ref or "").strip()
            ):
                return True
        return False

    def _l10n_ve_edi_is_invoice_target(self):
        self.ensure_one()
        return (
            self.state == "posted"
            and self.country_code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "digital"
            and self.journal_id.l10n_ve_edi_provider
            and self.journal_id.l10n_ve_edi_provider != "none"
        )

    def _l10n_ve_edi_should_auto_send_on_igtf_accrual(self):
        self.ensure_one()
        if not self._l10n_ve_edi_is_invoice_target():
            return False
        if self.l10n_ve_edi_send_state != STATE_NOT_SENT:
            return False
        if not hasattr(self, "l10n_ve_igtf_document_has_igtf"):
            return False
        return self.l10n_ve_igtf_document_has_igtf()

    def _l10n_ve_edi_try_auto_send_on_igtf_accrual(self):
        for move in self:
            if not move._l10n_ve_edi_should_auto_send_on_igtf_accrual():
                continue
            move._l10n_ve_edi_enqueue_send(reuse_payload=False)

    def _l10n_ve_edi_create_payload_attachment(self, payload):
        self.ensure_one()
        filename = (self.name or f"move_{self.id}").replace("/", "_")
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        datas = base64.b64encode(content.encode("utf-8"))
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": f"l10n_ve_edi_payload_{filename}.json",
                    "type": "binary",
                    "datas": datas,
                    "mimetype": "application/json",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )
        return attachment

    def _build_payload_to_send(self):
        self.ensure_one()
        provider = self.journal_id.l10n_ve_edi_provider
        if not provider or provider == "none":
            raise UserError(
                _(
                    "Seleccione un proveedor de facturacion digital en el "
                    "diario de la factura."
                )
            )
        self._l10n_ve_edi_validate_parties_identification()
        return self._l10n_ve_edi_build_payload_for_provider(provider)

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        raise UserError(
            _(
                "No hay modulo instalado para el proveedor EDI %(code)s. "
                "Instale el conector correspondiente (por ejemplo "
                "l10n_ve_edi_tfhka para TFHKA)."
            )
            % {"code": provider}
        )

    def _l10n_ve_edi_send_uses_queue_job(self):
        return False

    def _l10n_ve_edi_prepare_send(self, reuse_payload=False):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id if reuse_payload else False
        if not attachment:
            payload = self._build_payload_to_send()
            attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write(
            {
                "l10n_ve_edi_payload_attachment_id": attachment.id,
                "l10n_ve_edi_send_state": STATE_QUEUED,
                "l10n_ve_edi_last_error": False,
                "l10n_ve_edi_response_json": False,
            }
        )
        return attachment

    def _l10n_ve_edi_schedule_send(self):
        self.ensure_one()
        self._run_job()

    def _l10n_ve_edi_enqueue_send(self, reuse_payload=False):
        self.ensure_one()
        self._l10n_ve_edi_prepare_send(reuse_payload=reuse_payload)
        self._l10n_ve_edi_schedule_send()

    def action_l10n_ve_edi_send(self):
        for move in self:
            if move.state != "posted":
                raise UserError(_("Solo se pueden enviar facturas confirmadas."))
            if not move._l10n_ve_edi_is_invoice_target():
                raise UserError(
                    _(
                        "El diario no tiene proveedor de facturacion digital "
                        "configurado o el documento no aplica."
                    )
                )
            if move.l10n_ve_edi_send_state == STATE_QUEUED:
                raise UserError(
                    _("Ya hay una solicitud de envio en cola para este documento.")
                )
            if move.l10n_ve_edi_send_state == STATE_SENT:
                raise UserError(_("El documento ya fue enviado a facturacion digital."))
            move._l10n_ve_edi_enqueue_send(reuse_payload=False)
        return True

    def action_l10n_ve_edi_retry_send(self):
        return self.action_l10n_ve_edi_send()

    def _l10n_ve_edi_get_company_partner(self):
        self.ensure_one()
        return self.company_id.partner_id.commercial_partner_id

    def _l10n_ve_edi_get_buyer_partner(self):
        self.ensure_one()
        return self.partner_id.commercial_partner_id

    def _l10n_ve_edi_get_company_vat(self):
        self.ensure_one()
        company_partner = self._l10n_ve_edi_get_company_partner()
        return company_partner.vat or self.company_id.vat

    def _l10n_ve_edi_get_seller_identification(self):
        self.ensure_one()
        return self._l10n_ve_edi_parse_ve_vat(self._l10n_ve_edi_get_company_vat())

    def _l10n_ve_edi_get_buyer_identification(self):
        self.ensure_one()
        buyer = self._l10n_ve_edi_get_buyer_partner()
        return self._l10n_ve_edi_parse_ve_vat(buyer.vat)

    def _l10n_ve_edi_validate_parties_identification(self):
        self.ensure_one()
        buyer = self._l10n_ve_edi_get_buyer_partner()
        buyer_prefix, buyer_number = self._l10n_ve_edi_get_buyer_identification()
        if not buyer_prefix or not buyer_number:
            raise UserError(
                _(
                    "El RIF del cliente no es valido o falta para el payload "
                    "EDI. Valor actual: %(vat)s"
                )
                % {"vat": buyer.vat or "VACIO"}
            )
        company_vat = self._l10n_ve_edi_get_company_vat()
        seller_prefix, seller_number = self._l10n_ve_edi_get_seller_identification()
        if not seller_prefix or not seller_number:
            raise UserError(
                _(
                    "El RIF del emisor (su empresa en Odoo) no es valido o "
                    "falta para el payload EDI. Configuracion: Ajustes > "
                    "Empresas, campo NIF/CIF (no el RIF del cliente). "
                    "Valor leido: %(vat)s"
                )
                % {"vat": company_vat or "VACIO"}
            )

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        provider = self.journal_id.l10n_ve_edi_provider
        return {
            "success": False,
            "error": _(
                "Proveedor EDI no soportado o modulo no instalado: %(provider)s."
            )
            % {"provider": provider or "none"},
        }

    def _l10n_ve_edi_on_dispatch_success(self, response):
        self.ensure_one()

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        if self.env.context.get("install_mode"):
            return res
        posted = self.filtered(lambda move: move.state == "posted")
        if posted:
            posted._l10n_ve_edi_try_auto_send_on_igtf_accrual()
        return res

    def _run_job(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id
        error_message = False
        if not attachment or not attachment.datas:
            error_message = _("Falta el adjunto con el payload EDI.")
        else:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
            dispatch = self._l10n_ve_edi_dispatch_payload(payload)
            if dispatch.get("success"):
                response = dispatch.get("response")
                try:
                    self._l10n_ve_edi_on_dispatch_success(response)
                except (UserError, ValidationError) as exc:
                    error_message = str(exc)
                    response_json = False
                    if response is not None:
                        response_json = json.dumps(
                            response, ensure_ascii=False, indent=2
                        )
                    self.write(
                        {
                            "l10n_ve_edi_send_state": STATE_SENT,
                            "l10n_ve_edi_sent_at": fields.Datetime.now(),
                            "l10n_ve_edi_last_error": error_message,
                            "l10n_ve_edi_response_json": response_json,
                        }
                    )
                    self.message_post(
                        body=_(
                            "El envio a facturacion digital fue exitoso, pero "
                            "hubo una incidencia de validacion en Odoo: "
                            "%(error)s"
                        )
                        % {"error": error_message}
                    )
                    return True
                response_json = False
                if response is not None:
                    response_json = json.dumps(response, ensure_ascii=False, indent=2)
                self.write(
                    {
                        "l10n_ve_edi_send_state": STATE_SENT,
                        "l10n_ve_edi_sent_at": fields.Datetime.now(),
                        "l10n_ve_edi_last_error": False,
                        "l10n_ve_edi_response_json": response_json,
                    }
                )
                self.message_post(
                    body=_("Documento enviado exitosamente a facturacion digital.")
                )
                return True
            error_message = dispatch.get("error") or _(
                "El conector EDI no completo el envio."
            )
        if error_message:
            self.write(
                {
                    "l10n_ve_edi_send_state": STATE_FAILED,
                    "l10n_ve_edi_last_error": error_message,
                }
            )
            self.message_post(
                body=_("Fallo el envio a facturacion digital. Motivo: %(error)s")
                % {"error": error_message}
            )
        return False

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "l10n_ve_invoice_original_printed",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_edi_send_state",
        "journal_id.l10n_ve_edi_provider",
    )
    def _compute_l10n_ve_hide_invoice_preview_send(self):
        return super()._compute_l10n_ve_hide_invoice_preview_send()

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_edi_send_state",
        "journal_id.l10n_ve_edi_provider",
    )
    def _compute_l10n_ve_hide_invoice_print_pdf(self):
        return super()._compute_l10n_ve_hide_invoice_print_pdf()

    @api.depends(
        "country_code",
        "move_type",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_edi_send_state",
    )
    def _compute_l10n_ve_digital_invoice_sent(self):
        return super()._compute_l10n_ve_digital_invoice_sent()

    @api.model
    def _job_l10n_ve_edi_send_invoice(self, move_id):
        move = self.sudo().browse(move_id).exists()
        if not move:
            return False
        return move._run_job()
