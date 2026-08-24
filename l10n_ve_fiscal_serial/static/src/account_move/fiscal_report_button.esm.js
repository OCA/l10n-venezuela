import {Component, xml} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {l10nVeFiscalSerialExecuteReport} from "../fiscal_serial/fiscal_serial_report";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const ACTION_LABELS = {
    report_x: _t("Reporte X"),
    report_z: _t("Reporte Z"),
};

export class FiscalReportButton extends Component {
    static props = ["*"];
    static template = xml`
        <button t-att-class="buttonClass" type="button" t-on-click="onClick">
            <span t-esc="label"/>
        </button>
    `;

    setup() {
        this.notification = useService("notification");
    }

    get label() {
        return ACTION_LABELS[this.props.action] || _t("Reporte fiscal");
    }

    get buttonClass() {
        return `btn ${this.props.button_class || "btn-secondary"}`;
    }

    async onClick() {
        const action = this.props.action;
        if (!action) {
            this.notification.add(_t("Acción fiscal no configurada."), {
                type: "danger",
            });
            return;
        }
        await l10nVeFiscalSerialExecuteReport({
            env: this.env,
            action,
        });
    }
}

registry.category("view_widgets").add("l10n_ve_fiscal_serial_report_button", {
    component: FiscalReportButton,
    extractProps: ({attrs}) => ({
        action: attrs.action,
        button_class: attrs.button_class,
    }),
});
