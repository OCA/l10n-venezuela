/** @odoo-module **/

import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";
import {FiscalMachineDebugConsole} from "./fiscal_machine_debug_console";

export class FiscalMachineDebugConsoleWidget extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachineDebugConsoleWidget";
    static components = {FiscalMachineDebugConsole};
    static props = {
        ...standardWidgetProps,
    };
}

registry.category("view_widgets").add("fiscal_machine_debug_console", {
    component: FiscalMachineDebugConsoleWidget,
});
