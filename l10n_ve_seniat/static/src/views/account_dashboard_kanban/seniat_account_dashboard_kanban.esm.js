import {DashboardKanbanRenderer} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_renderer";
import {SeniatInvoiceDashboard} from "../../components/seniat_invoice_dashboard/seniat_invoice_dashboard";
import {accountDashboardKanbanView} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_view";
import {registry} from "@web/core/registry";

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
