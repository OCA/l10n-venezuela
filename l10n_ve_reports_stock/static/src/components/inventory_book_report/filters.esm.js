import {AccountReport} from "@l10n_ve_reports/components/account_report/account_report";
import {AccountReportFilters} from "@l10n_ve_reports/components/account_report/filters/filters";

export class InventoryBookReportFilters extends AccountReportFilters {
    static template = "l10n_ve_reports_stock.InventoryBookReportFilters";

    get selectedWarehouseName() {
        const warehouseIds = this.controller.options.warehouse_ids || [];
        if (!warehouseIds.length) {
            return "Todos los almacenes";
        }
        if (warehouseIds.length === 1) {
            return "1 almacén";
        }
        return `${warehouseIds.length} almacenes`;
    }
}

AccountReport.registerCustomComponent(InventoryBookReportFilters);
