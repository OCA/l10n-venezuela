/** @odoo-module */

import {registry} from "@web/core/registry";
import {accountDashboardKanbanView} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_view";
import {DashboardKanbanRenderer} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_renderer";
import {SeniatInvoiceDashboard} from "../../components/seniat_invoice_dashboard/seniat_invoice_dashboard";

export class SeniatDashboardKanbanRenderer extends DashboardKanbanRenderer {
    static components = {
        ...DashboardKanbanRenderer.components,
        SeniatInvoiceDashboard,
    };
    static template = "l10n_ve_seniat.DashboardKanbanRenderer";
}

registry.category("views").add(
    "account_dashboard_kanban",
    {
        ...accountDashboardKanbanView,
        Renderer: SeniatDashboardKanbanRenderer,
    },
    {force: true}
);
