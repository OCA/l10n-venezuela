from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_invoice_dispatch_guides = fields.Char(
        string="Guías de despacho",
        compute="_compute_l10n_ve_invoice_dispatch_guides",
        store=True,
        copy=False,
        readonly=True,
    )

    def l10n_ve_portal_control_number_display(self):
        self.ensure_one()
        return (self.sudo().l10n_ve_control_number or "").strip()

    def _l10n_ve_dispatch_guides_text_from_pickings(self):
        self.ensure_one()
        numbers = []
        seen = set()
        for picking in self.picking_ids.sorted(
            lambda picking: (
                picking.l10n_ve_control_number or "",
                picking.name or "",
                picking.id if isinstance(picking.id, int) else 0,
            )
        ):
            n = (picking.l10n_ve_control_number or "").strip()
            if n and n not in seen:
                seen.add(n)
                numbers.append(n)
        if not numbers:
            return False
        return _("Guía de Despacho: %s") % ",".join(numbers)

    @api.depends(
        "picking_ids",
        "picking_ids.l10n_ve_control_number",
        "state",
    )
    def _compute_l10n_ve_invoice_dispatch_guides(self):
        for move in self:
            if move.state == "posted":
                if move._origin.state == "posted":
                    move.l10n_ve_invoice_dispatch_guides = (
                        move._origin.l10n_ve_invoice_dispatch_guides
                    )
                else:
                    move.l10n_ve_invoice_dispatch_guides = (
                        move._origin.l10n_ve_invoice_dispatch_guides
                        or move._l10n_ve_dispatch_guides_text_from_pickings()
                    )
                continue
            move.l10n_ve_invoice_dispatch_guides = (
                move._l10n_ve_dispatch_guides_text_from_pickings()
            )
