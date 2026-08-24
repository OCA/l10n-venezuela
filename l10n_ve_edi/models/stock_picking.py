import base64
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .edi_mixin import STATE_FAILED, STATE_NOT_SENT, STATE_QUEUED, STATE_SENT


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "l10n_ve.edi.mixin"]

    l10n_ve_edi_journal_id = fields.Many2one(
        "account.journal",
        compute="_compute_l10n_ve_edi_journal_id",
        string="EDI Journal",
    )

    @api.depends("company_id", "sale_id", "sale_id.journal_id")
    def _compute_l10n_ve_edi_journal_id(self):
        for picking in self:
            picking.l10n_ve_edi_journal_id = picking._l10n_ve_edi_get_edi_journal()

    def _l10n_ve_edi_get_dispatch_journal(self):
        self.ensure_one()
        sale = self.sale_id
        if not sale:
            return self.env["account.journal"]
        return sale.journal_id

    def _l10n_ve_edi_get_digital_emission_journal(self):
        self.ensure_one()
        journal = self._l10n_ve_edi_get_dispatch_journal()
        if (
            journal
            and journal.l10n_ve_emission_medium == "digital"
            and journal.l10n_ve_edi_provider
            and journal.l10n_ve_edi_provider != "none"
        ):
            return journal
        return self.env["account.journal"]

    def _l10n_ve_edi_dispatch_guide_uses_digital(self):
        self.ensure_one()
        if not self._l10n_ve_dispatch_requires_control_number():
            return False
        return bool(self._l10n_ve_edi_get_digital_emission_journal())

    def _l10n_ve_edi_dispatch_guide_qualifies_for_factura_guia(self):
        self.ensure_one()
        if not (self.l10n_ve_control_number or "").strip():
            return False
        return bool(self._l10n_ve_edi_get_digital_emission_journal())

    def _l10n_ve_edi_get_edi_journal(self):
        self.ensure_one()
        return self._l10n_ve_edi_get_dispatch_journal()

    def _l10n_ve_edi_get_dispatch_edi_provider(self):
        self.ensure_one()
        journal = self._l10n_ve_edi_get_digital_emission_journal()
        if journal:
            return journal.l10n_ve_edi_provider
        return False

    l10n_ve_edi_show_tab = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_tab",
        string="Show EDI Tab",
    )
    l10n_ve_edi_show_sent_document_actions = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_sent_document_actions",
        string="EDI Sent Document Actions",
    )

    @api.depends(
        "state",
        "picking_type_code",
        "l10n_ve_edi_send_state",
        "company_id",
        "sale_id",
        "sale_id.journal_id",
        "sale_id.journal_id.l10n_ve_emission_medium",
        "sale_id.journal_id.l10n_ve_edi_provider",
        "move_ids",
        "move_ids.state",
        "move_ids.quantity",
        "move_ids.product_uom_qty",
        "move_ids.sale_line_id",
        "move_ids.product_id",
        "invoice_ids",
    )
    def _compute_l10n_ve_edi_show_sent_document_actions(self):
        for picking in self:
            picking.l10n_ve_edi_show_sent_document_actions = (
                picking._l10n_ve_edi_dispatch_guide_sent_document_available()
            )

    def _l10n_ve_edi_dispatch_guide_sent_document_available(self):
        self.ensure_one()
        return False

    def action_l10n_ve_edi_download_sent_document(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_sent_document_available():
            raise UserError(
                _("No hay documento digital enviado disponible para descargar.")
            )
        raise UserError(
            _(
                "Instale el conector EDI del proveedor configurado en el diario "
                "para descargar el documento digital."
            )
        )

    def action_l10n_ve_edi_open_sent_document_url(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_sent_document_available():
            raise UserError(
                _("No hay documento digital enviado disponible para consultar.")
            )
        raise UserError(
            _(
                "Instale el conector EDI del proveedor configurado en el diario "
                "para consultar el documento digital."
            )
        )

    @api.depends(
        "state",
        "picking_type_code",
        "company_id",
        "sale_id",
        "sale_id.journal_id",
        "sale_id.journal_id.l10n_ve_emission_medium",
        "sale_id.journal_id.l10n_ve_edi_provider",
        "move_ids",
        "move_ids.state",
        "move_ids.quantity",
        "move_ids.product_uom_qty",
        "move_ids.sale_line_id",
        "move_ids.product_id",
        "invoice_ids",
    )
    def _compute_l10n_ve_edi_show_tab(self):
        for picking in self:
            picking.l10n_ve_edi_show_tab = (
                picking._l10n_ve_edi_dispatch_guide_uses_digital()
            )

    def _l10n_ve_edi_is_picking_target(self):
        self.ensure_one()
        return (
            self.state == "done"
            and self._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
            and self._l10n_ve_edi_dispatch_guide_uses_digital()
        )

    def _l10n_ve_edi_dispatch_guide_blocking_print_before_digital_sent(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_uses_digital():
            return False
        return self.state == "done" and self.l10n_ve_edi_send_state != "sent"

    def _l10n_ve_edi_get_buyer_partner(self):
        self.ensure_one()
        partner = self.partner_id or self.sale_id.partner_id
        return partner.commercial_partner_id if partner else partner

    def _l10n_ve_edi_get_company_partner(self):
        self.ensure_one()
        return self.company_id.partner_id.commercial_partner_id

    def _l10n_ve_edi_get_company_vat(self):
        self.ensure_one()
        company_partner = self._l10n_ve_edi_get_company_partner()
        return company_partner.vat or self.company_id.vat

    def _l10n_ve_edi_get_buyer_identification(self):
        self.ensure_one()
        buyer = self._l10n_ve_edi_get_buyer_partner()
        if not buyer:
            return "", ""
        return self._l10n_ve_edi_parse_ve_vat(buyer.vat)

    def _l10n_ve_edi_get_seller_identification(self):
        self.ensure_one()
        return self._l10n_ve_edi_parse_ve_vat(self._l10n_ve_edi_get_company_vat())

    def _l10n_ve_edi_validate_parties_identification(self):
        self.ensure_one()
        buyer = self._l10n_ve_edi_get_buyer_partner()
        if not buyer:
            raise UserError(
                _(
                    "La guia de despacho debe tener un cliente o "
                    "destinatario con RIF valido."
                )
            )
        buyer_prefix, buyer_number = self._l10n_ve_edi_get_buyer_identification()
        if not buyer_prefix or not buyer_number:
            raise UserError(
                _(
                    "El RIF del cliente no es valido o falta para el payload EDI. "
                    "Valor actual: %(vat)s"
                )
                % {"vat": buyer.vat or "VACIO"}
            )
        company_vat = self._l10n_ve_edi_get_company_vat()
        seller_prefix, seller_number = self._l10n_ve_edi_get_seller_identification()
        if not seller_prefix or not seller_number:
            raise UserError(
                _(
                    "El RIF del emisor (su empresa) no es valido o falta "
                    "para el payload EDI. Valor leido: %(vat)s"
                )
                % {"vat": company_vat or "VACIO"}
            )

    def _l10n_ve_edi_validate_dispatch_guide_lines(self):
        self.ensure_one()
        moves = self.move_ids.filtered(
            lambda move: move.product_id and move.state == "done"
        )
        if not moves:
            raise UserError(
                _("La guia de despacho no tiene lineas de producto validadas.")
            )

    def _l10n_ve_edi_create_payload_attachment(self, payload):
        self.ensure_one()
        filename = (self.name or f"picking_{self.id}").replace("/", "_")
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        datas = base64.b64encode(content.encode("utf-8"))
        return (
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

    def _build_payload_to_send(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_uses_digital():
            raise UserError(
                _(
                    "Esta guia no aplica a facturacion digital. Solo se envian guias "
                    "de despacho con numero de control (entrega parcial no facturada) "
                    "cuando el diario de ventas del pedido esta en emision digital "
                    "con proveedor EDI configurado."
                )
            )
        provider = self._l10n_ve_edi_get_dispatch_edi_provider()
        if not provider:
            raise UserError(
                _(
                    "No hay proveedor EDI disponible. Configure facturacion digital "
                    "en un diario de ventas."
                )
            )
        if self.state != "done":
            raise UserError(_("Solo se pueden enviar guias de despacho validadas."))
        self._l10n_ve_edi_validate_parties_identification()
        self._l10n_ve_edi_validate_dispatch_guide_lines()
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
        for picking in self:
            if picking.state != "done":
                raise UserError(_("Solo se pueden enviar guias de despacho validadas."))
            if not picking._l10n_ve_edi_is_picking_target():
                raise UserError(
                    _(
                        "Esta guia no aplica a facturacion digital o el "
                        "diario de ventas del pedido no esta en emision "
                        "digital con proveedor EDI."
                    )
                )
            if picking.l10n_ve_edi_send_state == STATE_QUEUED:
                raise UserError(
                    _("Ya hay una solicitud de envio en cola para este documento.")
                )
            if picking.l10n_ve_edi_send_state == STATE_SENT:
                raise UserError(_("El documento ya fue enviado a facturacion digital."))
            picking._l10n_ve_edi_enqueue_send(reuse_payload=False)
        return True

    def action_l10n_ve_edi_retry_send(self):
        for picking in self:
            if picking.l10n_ve_edi_send_state != STATE_FAILED:
                raise UserError(_("Solo puede reintentar envios fallidos."))
            picking.write(
                {
                    "l10n_ve_edi_send_state": STATE_NOT_SENT,
                    "l10n_ve_edi_last_error": False,
                }
            )
        return self.action_l10n_ve_edi_send()

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        provider = self._l10n_ve_edi_get_dispatch_edi_provider()
        return {
            "success": False,
            "error": _(
                "Proveedor EDI no soportado o modulo no instalado: %(provider)s."
            )
            % {"provider": provider or "none"},
        }

    def _l10n_ve_edi_on_dispatch_success(self, response):
        self.ensure_one()

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
                            "El envio a facturacion digital fue exitoso, pero hubo una "
                            "incidencia de validacion en Odoo: %(error)s"
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
                    body=_(
                        "Guia de despacho enviada exitosamente a "
                        "facturacion digital."
                    )
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

    @api.model
    def _job_l10n_ve_edi_send_picking(self, picking_id):
        picking = self.sudo().browse(picking_id).exists()
        if not picking:
            return False
        return picking._run_job()

    def _l10n_ve_assign_dispatch_control_number(self):
        if any(picking._l10n_ve_edi_dispatch_guide_uses_digital() for picking in self):
            digital_pickings = self.filtered(
                lambda picking: picking._l10n_ve_edi_dispatch_guide_uses_digital()
            )
            others = self - digital_pickings
            if others:
                return super(
                    StockPicking, others
                )._l10n_ve_assign_dispatch_control_number()
            return
        return super()._l10n_ve_assign_dispatch_control_number()

    def _l10n_ve_will_assign_dispatch_control_number_on_validate(self):
        self.ensure_one()
        if self._l10n_ve_edi_dispatch_guide_uses_digital():
            return False
        return super()._l10n_ve_will_assign_dispatch_control_number_on_validate()

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
        "sale_id.journal_id",
        "sale_id.journal_id.l10n_ve_emission_medium",
        "sale_id.journal_id.l10n_ve_edi_provider",
        "picking_type_id.warehouse_id.l10n_ve_dispatch_guide_section_id",
        "sale_id.order_line.qty_invoiced_posted",
        "sale_id.order_line.qty_delivered",
    )
    def _compute_l10n_ve_control_number_placeholder(self):
        digital_pickings = self.filtered(
            lambda picking: picking._l10n_ve_edi_dispatch_guide_uses_digital()
        )
        res = super(
            StockPicking, self - digital_pickings
        )._compute_l10n_ve_control_number_placeholder()
        for picking in digital_pickings:
            picking.l10n_ve_control_number_placeholder = False
        return res

    def action_l10n_ve_print_dispatch_guide(self):
        blocked = self.filtered(
            lambda picking: (
                picking._l10n_ve_edi_dispatch_guide_blocking_print_before_digital_sent()
            )
        )
        if blocked:
            raise UserError(
                _(
                    "No puede imprimir la guia hasta que el envio a "
                    "facturacion digital finalice correctamente "
                    "(estado EDI: enviado)."
                )
            )
        return super().action_l10n_ve_print_dispatch_guide()
