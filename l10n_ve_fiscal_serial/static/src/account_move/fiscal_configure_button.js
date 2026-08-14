/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { l10nVeFiscalSerialExecuteConfigure } from "../fiscal_serial/fiscal_serial_configure";

export class FiscalConfigureButton extends Component {
    static props = {
        ...standardWidgetProps,
        button_class: { type: String, optional: true },
    };
    static template = xml`
        <button t-att-class="buttonClass" type="button" t-on-click="onClick">
            <span t-esc="label"/>
        </button>
    `;

    setup() {
        this.notification = useService("notification");
    }

    get label() {
        return _t("Configurar");
    }

    get buttonClass() {
        return `btn ${this.props.button_class || "btn-secondary"}`;
    }

    async onClick() {
        const record = this.props.record;
        if (!record?.resId) {
            this.notification.add(_t("Guarde la máquina fiscal antes de configurar."), {
                type: "warning",
            });
            return;
        }
        if (typeof record.isDirty === "function" && (await record.isDirty())) {
            const saved = await record.save();
            if (saved === false) {
                this.notification.add(
                    _t("Corrija los errores del formulario antes de configurar."),
                    { type: "warning" }
                );
                return;
            }
        }
        await l10nVeFiscalSerialExecuteConfigure({
            env: this.env,
            machineId: record.resId,
        });
    }
}

registry.category("view_widgets").add("l10n_ve_fiscal_serial_configure_button", {
    component: FiscalConfigureButton,
    extractProps: ({ attrs }) => ({
        button_class: attrs.button_class,
    }),
});
