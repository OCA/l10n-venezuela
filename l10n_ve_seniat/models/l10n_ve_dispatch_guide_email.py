import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date, format_datetime

_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_unfactured_dispatch_email_recipient = fields.Char(
        string="Correo guías no facturadas",
        default="proveedores.sistemas@seniat.gob.ve",
    )
    l10n_ve_unfactured_dispatch_email_interval_number = fields.Integer(
        string="Intervalo de envío",
        default=1,
    )
    l10n_ve_unfactured_dispatch_email_interval_type = fields.Selection(
        selection=[
            ("minutes", "Minutos"),
            ("hours", "Horas"),
            ("days", "Días"),
            ("weeks", "Semanas"),
        ],
        string="Unidad de intervalo",
        default="days",
    )
    l10n_ve_unfactured_dispatch_email_schedule_enabled = fields.Boolean(
        string="Enviar guías no facturadas automáticamente",
        default=False,
    )
    l10n_ve_unfactured_dispatch_email_last_sent = fields.Datetime(
        string="Último envío guías no facturadas",
        readonly=True,
        copy=False,
    )

    @api.constrains(
        "l10n_ve_unfactured_dispatch_email_recipient",
        "l10n_ve_unfactured_dispatch_email_schedule_enabled",
    )
    def _check_l10n_ve_unfactured_dispatch_email_recipient(self):
        for company in self:
            if (
                "l10n_ve_dispatch_guide_enabled" in company._fields
                and not company.l10n_ve_dispatch_guide_enabled
            ):
                continue
            recipient = (company.l10n_ve_unfactured_dispatch_email_recipient or "").strip()
            if not recipient:
                if company.l10n_ve_unfactured_dispatch_email_schedule_enabled:
                    raise ValidationError(
                        _(
                            "Indique el correo destinatario para el envío automático "
                            "de guías de despacho no facturadas."
                        )
                    )
                continue
            if not _EMAIL_RE.match(recipient):
                raise ValidationError(
                    _(
                        "El correo destinatario “%(email)s” no tiene un formato válido."
                    )
                    % {"email": recipient}
                )

    @api.constrains("l10n_ve_unfactured_dispatch_email_interval_number")
    def _check_l10n_ve_unfactured_dispatch_email_interval(self):
        for company in self:
            if company.l10n_ve_unfactured_dispatch_email_interval_number < 1:
                raise ValidationError(
                    _("El intervalo de envío debe ser al menos 1.")
                )

    def write(self, vals):
        res = super().write(vals)
        dispatch_fields = {
            "l10n_ve_dispatch_guide_enabled",
            "l10n_ve_unfactured_dispatch_email_recipient",
            "l10n_ve_unfactured_dispatch_email_schedule_enabled",
            "l10n_ve_unfactured_dispatch_email_interval_number",
            "l10n_ve_unfactured_dispatch_email_interval_type",
        }
        if dispatch_fields.intersection(vals):
            self._l10n_ve_sync_unfactured_dispatch_cron()
        return res

    @api.model
    def _l10n_ve_sync_unfactured_dispatch_cron(self):
        cron = self.env.ref(
            "l10n_ve_seniat.ir_cron_unfactured_dispatch_guides_email",
            raise_if_not_found=False,
        )
        if not cron:
            return
        domain = [
            (
                "l10n_ve_unfactured_dispatch_email_schedule_enabled",
                "=",
                True,
            ),
            ("l10n_ve_unfactured_dispatch_email_recipient", "!=", False),
        ]
        if "l10n_ve_dispatch_guide_enabled" in self._fields:
            domain.append(("l10n_ve_dispatch_guide_enabled", "=", True))
        cron.active = bool(self.search_count(domain))

    def _l10n_ve_dispatch_email_interval_elapsed(self, now=None):
        self.ensure_one()
        if not self.l10n_ve_unfactured_dispatch_email_last_sent:
            return True
        now = now or fields.Datetime.now()
        interval_type = self.l10n_ve_unfactured_dispatch_email_interval_type or "days"
        interval_number = self.l10n_ve_unfactured_dispatch_email_interval_number or 1
        next_send = self.l10n_ve_unfactured_dispatch_email_last_sent + relativedelta(
            **{interval_type: interval_number}
        )
        return now >= next_send

    def l10n_ve_unfactured_dispatch_guides_for_email(self):
        """Lista guías de despacho pendientes de facturación para reporte SENIAT.

        Returns
        -------
        recordset

        Notes
        -----
        Art. 21 PA SNAT/2011/0071: órdenes de entrega y guías de despacho.
        Art. 10 PA SNAT/2024/000102: guías en facturación digital.
        """

        self.ensure_one()
        pickings, available = self.env[
            "account.journal"
        ]._l10n_ve_seniat_unfactured_dispatch_guides(self)
        if not available:
            return []
        rows = []
        for picking in pickings.sorted("date_done", reverse=True):
            control_number = ""
            if "l10n_ve_control_number" in picking._fields:
                control_number = picking.l10n_ve_control_number or ""
            date_done_label = ""
            if picking.date_done:
                date_done_label = format_datetime(self.env, picking.date_done)
            rows.append(
                {
                    "name": picking.name,
                    "partner": picking.partner_id.display_name or "",
                    "origin": picking.origin or "",
                    "date_done": date_done_label,
                    "control_number": control_number or "—",
                }
            )
        return rows

    def l10n_ve_unfactured_dispatch_email_report_date(self):
        self.ensure_one()
        return format_datetime(self.env, fields.Datetime.now())

    def l10n_ve_unfactured_dispatch_email_issue_date(self):
        self.ensure_one()
        return format_date(self.env, fields.Date.context_today(self))

    def l10n_ve_unfactured_dispatch_email_count(self):
        self.ensure_one()
        return len(self.l10n_ve_unfactured_dispatch_guides_for_email())

    def _l10n_ve_send_unfactured_dispatch_guides_email(self):
        self.ensure_one()
        recipient = (self.l10n_ve_unfactured_dispatch_email_recipient or "").strip()
        if not recipient:
            raise UserError(
                _(
                    "Configure el correo destinatario en Ajustes → Contabilidad "
                    "→ Venezuela."
                )
            )
        pickings, available = self.env[
            "account.journal"
        ]._l10n_ve_seniat_unfactured_dispatch_guides(self)
        if not available:
            raise UserError(
                _(
                    "Las guías de despacho requieren el módulo de inventario SENIAT "
                    "(l10n_ve_stock)."
                )
            )
        template = self.env.ref(
            "l10n_ve_seniat.mail_template_unfactured_dispatch_guides",
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_("No se encontró la plantilla de correo configurada."))
        email_values = {"email_to": recipient}
        implementer_from = self.l10n_ve_implementer_email_from()
        if implementer_from:
            email_values["email_from"] = implementer_from
        elif self.email_formatted:
            email_values["email_from"] = self.email_formatted
        template.send_mail(
            self.id,
            force_send=True,
            email_values=email_values,
        )
        self.sudo().write(
            {"l10n_ve_unfactured_dispatch_email_last_sent": fields.Datetime.now()}
        )
        return True

    @api.model
    def _cron_l10n_ve_send_unfactured_dispatch_guides_email(self):
        domain = [
            ("account_fiscal_country_id.code", "=", "VE"),
            ("l10n_ve_unfactured_dispatch_email_schedule_enabled", "=", True),
            ("l10n_ve_unfactured_dispatch_email_recipient", "!=", False),
        ]
        if "l10n_ve_dispatch_guide_enabled" in self._fields:
            domain.append(("l10n_ve_dispatch_guide_enabled", "=", True))
        companies = self.search(domain)
        now = fields.Datetime.now()
        for company in companies:
            if not company._l10n_ve_dispatch_email_interval_elapsed(now):
                continue
            try:
                company._l10n_ve_send_unfactured_dispatch_guides_email()
            except UserError:
                continue

    def l10n_ve_unfactured_dispatch_email_last_sent_label(self):
        self.ensure_one()
        if not self.l10n_ve_unfactured_dispatch_email_last_sent:
            return False
        return format_datetime(
            self.env,
            self.l10n_ve_unfactured_dispatch_email_last_sent,
        )
