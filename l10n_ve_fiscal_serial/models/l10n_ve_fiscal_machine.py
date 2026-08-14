# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nVeFiscalMachine(models.Model):
    _name = "l10n.ve.fiscal.machine"
    _description = "Venezuela Fiscal Machine"
    _order = "name, id"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    connection_type = fields.Selection(
        selection=[
            ("web_serial", "Web Serial (navegador)"),
        ],
        string="Tipo de conexión",
        required=True,
        default="web_serial",
    )
    serial_port = fields.Char(
        string="Puerto de conexión",
        help="Identificador del puerto serie o adaptador USB detectado.",
    )
    baudrate = fields.Selection(
        selection=[
            ("9600", "9600"),
            ("19200", "19200"),
            ("38400", "38400"),
            ("57600", "57600"),
            ("115200", "115200"),
        ],
        default="9600",
        required=True,
    )
    parity = fields.Selection(
        selection=[
            ("none", "Ninguna"),
            ("even", "Par"),
            ("odd", "Impar"),
        ],
        default="even",
        required=True,
    )
    data_bits = fields.Selection(
        selection=[("7", "7"), ("8", "8")],
        default="8",
        required=True,
    )
    stop_bits = fields.Selection(
        selection=[("1", "1"), ("2", "2")],
        default="1",
        required=True,
    )
    webserial_usb_vendor_id = fields.Integer(string="USB Vendor ID")
    webserial_usb_product_id = fields.Integer(string="USB Product ID")
    webserial_usb_serial_number = fields.Char(string="USB Serial Number")
    printer_type = fields.Selection(
        selection=[
            ("hka80", "HKA 80"),
            ("vmax801", "VMAX801"),
            ("other", "Otro"),
        ],
        string="Tipo de impresora",
        default="hka80",
        required=True,
    )
    printer_model_code = fields.Char(string="Código de modelo")
    printer_model_name = fields.Char(string="Modelo")
    country_code = fields.Char(string="País")
    registered_serial = fields.Char(string="Serial fiscal")
    fiscal_rif = fields.Char(string="RIF fiscal")
    flag_21 = fields.Selection(
        related="company_id.l10n_ve_fiscal_flag_21",
        readonly=False,
        string="FLAG 21",
    )
    flag_50 = fields.Selection(
        related="company_id.l10n_ve_fiscal_flag_50",
        readonly=False,
        string="FLAG 50",
    )
    use_barcode = fields.Boolean(
        related="company_id.l10n_ve_fiscal_use_barcode",
        readonly=False,
        string="Código de barras al final de la factura",
    )
    fiscal_footer = fields.Text(
        related="company_id.l10n_ve_fiscal_footer",
        readonly=False,
        string="Pie de página",
    )
    fiscal_payment_method_ids = fields.One2many(
        related="company_id.l10n_ve_fiscal_payment_method_ids",
        readonly=False,
        string="Métodos de pago",
    )
    l10n_ve_fiscal_default_payment_method_id = fields.Many2one(
        related="company_id.l10n_ve_fiscal_default_payment_method_id",
        readonly=False,
        string="Método de pago por defecto",
        domain="[('company_id', '=', company_id)]",
    )
    use_emulator = fields.Boolean(
        string="Usando emulador fiscal",
        help=(
            "Si está activo, el flujo de impresión fiscal por WebSerial "
            "omite la consulta previa de estado de la impresora."
        ),
    )
    send_default_code_in_name = fields.Boolean(
        string="Enviar codigo en nombre de producto",
        help=(
            "Si está activo y la línea tiene codigo interno, el nombre enviado "
            "a la máquina fiscal será: [CODIGO] Producto."
        ),
    )
    last_invoice_number = fields.Char(
        string="Última factura",
        readonly=True,
    )
    last_credit_note_number = fields.Char(
        string="Última nota de crédito",
        readonly=True,
    )
    last_debit_note_number = fields.Char(
        string="Última nota de débito",
        readonly=True,
    )
    daily_closure_counter = fields.Char(
        string="Último Z",
        readonly=True,
        help="Contador de cierre diario (reporte Z) reportado por la máquina.",
    )
    enq_status = fields.Integer(string="ENQ STS1", readonly=True)
    enq_error = fields.Integer(string="ENQ STS2", readonly=True)
    enq_status_label = fields.Char(readonly=True)
    enq_error_label = fields.Char(readonly=True)
    last_connection = fields.Datetime(readonly=True)
    s1_raw = fields.Text(readonly=True)
    sv_raw = fields.Text(readonly=True)
    audit_count = fields.Integer(compute="_compute_audit_count")

    _sql_constraints = [
        (
            "registered_serial_company_uniq",
            "unique(registered_serial, company_id)",
            "Ya existe una máquina fiscal con este serial en la compañía.",
        ),
    ]

    def _compute_audit_count(self):
        audit_model = self.env["l10n.ve.fiscal.serial.audit"]
        machine_ids = self.ids
        counts = {
            machine.id: 0
            for machine in self
        }
        if machine_ids:
            for machine_id, count in audit_model._read_group(
                [("machine_id", "in", machine_ids)],
                groupby=["machine_id"],
                aggregates=["__count"],
            ):
                if machine_id:
                    counts[machine_id.id] = count
        for machine in self:
            machine.audit_count = counts.get(machine.id, 0)

    def read(self, fields=None, load="_classic_read"):
        if self:
            self.mapped("company_id")._l10n_ve_fiscal_ensure_payment_methods()
        return super().read(fields=fields, load=load)

    @api.model
    def create_from_detect_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_("Payload de detección inválido."))
        vals = self._prepare_vals_from_detect_payload(payload)
        if not vals.get("registered_serial"):
            raise ValidationError(
                _("No se pudo leer el serial fiscal (S1). Verifique la conexión.")
            )
        existing = self.search(
            [
                ("company_id", "=", vals["company_id"]),
                ("registered_serial", "=", vals["registered_serial"]),
            ],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing.id
        return self.create(vals).id

    @api.model
    def _prepare_vals_from_detect_payload(self, payload):
        company_id = payload.get("company_id") or self.env.company.id
        registered_serial = (payload.get("registered_serial") or "").strip()
        printer_model_name = (payload.get("printer_model_name") or "").strip()
        name = (payload.get("name") or "").strip()
        if not name:
            if registered_serial and printer_model_name:
                name = f"{printer_model_name} ({registered_serial})"
            elif registered_serial:
                name = registered_serial
            else:
                name = payload.get("serial_port") or _("Máquina fiscal")
        return {
            "name": name,
            "company_id": company_id,
            "connection_type": payload.get("connection_type") or "web_serial",
            "serial_port": payload.get("serial_port"),
            "baudrate": payload.get("baudrate") or "9600",
            "parity": payload.get("parity") or "even",
            "data_bits": payload.get("data_bits") or "8",
            "stop_bits": payload.get("stop_bits") or "1",
            "webserial_usb_vendor_id": payload.get("webserial_usb_vendor_id") or 0,
            "webserial_usb_product_id": payload.get("webserial_usb_product_id") or 0,
            "webserial_usb_serial_number": payload.get("webserial_usb_serial_number"),
            "printer_type": payload.get("printer_type") or "hka80",
            "printer_model_code": payload.get("printer_model_code"),
            "printer_model_name": printer_model_name or None,
            "country_code": payload.get("country_code"),
            "registered_serial": registered_serial,
            "fiscal_rif": payload.get("fiscal_rif"),
            "use_emulator": payload.get("use_emulator"),
            "send_default_code_in_name": payload.get("send_default_code_in_name"),
            "last_invoice_number": payload.get("last_invoice_number"),
            "last_credit_note_number": payload.get("last_credit_note_number"),
            "last_debit_note_number": payload.get("last_debit_note_number"),
            "daily_closure_counter": payload.get("daily_closure_counter"),
            "enq_status": payload.get("enq_status"),
            "enq_error": payload.get("enq_error"),
            "enq_status_label": payload.get("enq_status_label"),
            "enq_error_label": payload.get("enq_error_label"),
            "last_connection": fields.Datetime.now(),
            "s1_raw": payload.get("s1_raw"),
            "sv_raw": payload.get("sv_raw"),
        }

    def action_open_setup_wizard(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {"company_id": self.env.company.id}
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_ve_fiscal_serial.action_l10n_ve_fiscal_machine_setup_wizard"
        )
        action["res_id"] = wizard.id
        return action

    def action_view_serial_audit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Auditoría fiscal serial"),
            "res_model": "l10n.ve.fiscal.serial.audit",
            "view_mode": "list,form",
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }

    def apply_s1_counters(self, payload):
        """Persist printer counters after a fiscal report or status refresh."""
        self.ensure_one()
        if not isinstance(payload, dict):
            raise ValidationError(_("Payload de contadores fiscales inválido."))
        vals = {}
        for field_name in (
            "daily_closure_counter",
            "last_invoice_number",
            "last_credit_note_number",
            "last_debit_note_number",
            "registered_serial",
        ):
            value = payload.get(field_name)
            if value not in (None, False, ""):
                vals[field_name] = str(value).strip()
        if not vals:
            return False
        vals["last_connection"] = fields.Datetime.now()
        self.write(vals)
        return {
            "id": self.id,
            "daily_closure_counter": self.daily_closure_counter or "",
            "last_invoice_number": self.last_invoice_number or "",
            "last_credit_note_number": self.last_credit_note_number or "",
            "last_debit_note_number": self.last_debit_note_number or "",
            "registered_serial": self.registered_serial or "",
        }

    def apply_port_update_from_detect(self, payload):
        """Update connection fields after selecting a port on another PC.

        Notes
        -----
        Keeps the fiscal identity (registered serial) unless the record had none.
        Rejects updates when the detected serial belongs to a different machine.
        """
        self.ensure_one()
        if not isinstance(payload, dict):
            raise ValidationError(_("Payload de detección inválido."))
        detected_serial = (payload.get("registered_serial") or "").strip()
        current_serial = (self.registered_serial or "").strip()
        if current_serial and detected_serial and current_serial != detected_serial:
            raise ValidationError(
                _(
                    "El puerto seleccionado corresponde a otra máquina fiscal "
                    "(serial %(detected)s). Esta ficha es %(current)s."
                )
                % {"detected": detected_serial, "current": current_serial}
            )
        vals = {
            "last_connection": fields.Datetime.now(),
        }
        if "serial_port" in payload and payload.get("serial_port"):
            vals["serial_port"] = payload.get("serial_port")
        if payload.get("baudrate"):
            vals["baudrate"] = payload.get("baudrate")
        if payload.get("parity"):
            vals["parity"] = payload.get("parity")
        if payload.get("data_bits"):
            vals["data_bits"] = payload.get("data_bits")
        if payload.get("stop_bits"):
            vals["stop_bits"] = payload.get("stop_bits")
        if "webserial_usb_vendor_id" in payload:
            vals["webserial_usb_vendor_id"] = (
                payload.get("webserial_usb_vendor_id") or 0
            )
        if "webserial_usb_product_id" in payload:
            vals["webserial_usb_product_id"] = (
                payload.get("webserial_usb_product_id") or 0
            )
        if "webserial_usb_serial_number" in payload:
            vals["webserial_usb_serial_number"] = (
                payload.get("webserial_usb_serial_number") or False
            )
        if "enq_status" in payload:
            vals["enq_status"] = payload.get("enq_status")
        if "enq_error" in payload:
            vals["enq_error"] = payload.get("enq_error")
        if "enq_status_label" in payload:
            vals["enq_status_label"] = payload.get("enq_status_label")
        if "enq_error_label" in payload:
            vals["enq_error_label"] = payload.get("enq_error_label")
        if "s1_raw" in payload:
            vals["s1_raw"] = payload.get("s1_raw")
        if "sv_raw" in payload:
            vals["sv_raw"] = payload.get("sv_raw")
        if detected_serial and not current_serial:
            vals["registered_serial"] = detected_serial
        if payload.get("fiscal_rif") and not self.fiscal_rif:
            vals["fiscal_rif"] = payload.get("fiscal_rif")
        if payload.get("printer_model_name"):
            vals["printer_model_name"] = payload.get("printer_model_name")
        if payload.get("printer_model_code"):
            vals["printer_model_code"] = payload.get("printer_model_code")
        if payload.get("printer_type"):
            vals["printer_type"] = payload.get("printer_type")
        if payload.get("country_code"):
            vals["country_code"] = payload.get("country_code")
        if payload.get("last_invoice_number"):
            vals["last_invoice_number"] = payload.get("last_invoice_number")
        if payload.get("last_credit_note_number"):
            vals["last_credit_note_number"] = payload.get("last_credit_note_number")
        if payload.get("last_debit_note_number"):
            vals["last_debit_note_number"] = payload.get("last_debit_note_number")
        if payload.get("daily_closure_counter"):
            vals["daily_closure_counter"] = payload.get("daily_closure_counter")
        self.write(vals)
        return {
            "serial_port": self.serial_port,
            "registered_serial": self.registered_serial,
            "webserial_usb_vendor_id": self.webserial_usb_vendor_id,
            "webserial_usb_product_id": self.webserial_usb_product_id,
            "webserial_usb_serial_number": self.webserial_usb_serial_number or "",
            "enq_status_label": self.enq_status_label or "",
            "enq_error_label": self.enq_error_label or "",
            "last_connection": fields.Datetime.to_string(self.last_connection)
            if self.last_connection
            else False,
            "training_mode": bool(
                payload.get("enq_status") == 64
                and not detected_serial
            ),
            "message": _(
                "Puerto actualizado para este navegador/PC. "
                "Use el systray «Verificar conexión» si hace falta."
            ),
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env["res.company"].browse(
            res.get("company_id") or self.env.company.id
        )
        company._l10n_ve_fiscal_ensure_payment_methods()
        return res

    def l10n_ve_fiscal_serial_get_config(self):
        self.ensure_one()
        shared = self.company_id.l10n_ve_fiscal_get_shared_config()
        baud = self.baudrate or "9600"
        return {
            **shared,
            "machine_id": self.id,
            "name": self.name or "",
            "registered_serial": self.registered_serial or "",
            "baudrate": int(baud) if str(baud).isdigit() else 9600,
            "parity": self.parity
            if self.parity in ("none", "even", "odd")
            else "even",
            "serial_port": self.serial_port or "",
            "webserial_usb_vendor_id": self.webserial_usb_vendor_id or 0,
            "webserial_usb_product_id": self.webserial_usb_product_id or 0,
            "webserial_usb_serial_number": self.webserial_usb_serial_number or "",
            "use_emulator": bool(self.use_emulator),
            "send_default_code_in_name": bool(self.send_default_code_in_name),
        }

    @api.model
    def l10n_ve_fiscal_serial_get_systray_data(self):
        company = self.env.company
        visible = company._l10n_ve_has_emission_medium("fiscal_machine")
        if not visible:
            return {"visible": False}
        machines = self.search(
            [("company_id", "=", company.id), ("active", "=", True)],
            order="name, id",
        )
        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", company.id),
                ("type", "=", "sale"),
                ("l10n_ve_emission_medium", "=", "fiscal_machine"),
                ("l10n_ve_fiscal_machine_id", "!=", False),
            ],
            limit=1,
        )
        primary = journal.l10n_ve_fiscal_machine_id or machines[:1]
        return {
            "visible": True,
            "company_name": company.display_name,
            "primary_machine_id": primary.id if primary else False,
            "machines": [
                {
                    "id": machine.id,
                    "name": machine.name,
                    "serial_port": machine.serial_port or "",
                    "registered_serial": machine.registered_serial or "",
                    "fiscal_rif": machine.fiscal_rif or "",
                    "printer_model_name": machine.printer_model_name or "",
                    "baudrate": machine.baudrate or "9600",
                    "parity": machine.parity or "even",
                    "webserial_usb_vendor_id": machine.webserial_usb_vendor_id or 0,
                    "webserial_usb_product_id": machine.webserial_usb_product_id or 0,
                    "webserial_usb_serial_number": (
                        machine.webserial_usb_serial_number or ""
                    ),
                    "last_connection": fields.Datetime.to_string(
                        machine.last_connection
                    )
                    if machine.last_connection
                    else False,
                    "enq_status_label": machine.enq_status_label or "",
                    "enq_error_label": machine.enq_error_label or "",
                }
                for machine in machines
            ],
        }