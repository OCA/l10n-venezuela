/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { createFiscalSerialAuditLogger } from "../fiscal_serial/fiscal_serial_audit";
import { TfhkaWebSerialTransport } from "../fiscal_serial/tfhka_transport_webserial";

const ACTION_TO_CHECK_METHOD = {
    print_out_invoice: "check_print_out_invoice",
    print_out_refund: "check_print_out_refund",
    print_debit_note: "check_print_debit_note",
    reprint: "check_reprint",
};

const ACTION_LABELS = {
    print_out_invoice: "Imprimir",
    print_out_refund: "Imprimir",
    print_debit_note: "Imprimir",
    reprint: "Reimprimir",
};

const ACTION_BUTTON_CLASS = {
    print_out_invoice: "btn btn-primary",
    print_out_refund: "btn btn-primary",
    print_debit_note: "btn btn-primary",
    reprint: "btn btn-secondary",
};

const ACTION_AUDIT_SOURCE = {
    print_out_invoice: "invoice_print",
    print_out_refund: "refund_print",
    print_debit_note: "debit_note",
    reprint: "reprint",
};

export class FiscalMoveButton extends Component {
    static props = ["*"];
    static template = xml`
        <button t-att-class="buttonClass" type="button" t-on-click="onClick">
            <span t-esc="label"/>
        </button>
    `;

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.fiscalSerial = useService("l10n_ve_fiscal_serial");
        this.connection = useService("l10n_ve_fiscal_connection");
        this.ui = useService("ui");
        this._uiBlocked = false;
    }

    get label() {
        return ACTION_LABELS[this.props.action] || "Fiscal";
    }

    get buttonClass() {
        return ACTION_BUTTON_CLASS[this.props.action] || "btn btn-secondary";
    }

    async _getPayload(actionName, moveId) {
        const method = ACTION_TO_CHECK_METHOD[actionName];
        if (!method) {
            throw new Error(`Accion no soportada: ${actionName}`);
        }
        return this.orm.call("account.move", method, [[moveId]]);
    }

    async _persistResponse(actionName, moveId, response) {
        if (actionName === "reprint") {
            return;
        }
        await this.orm.call("account.move", actionName, [[moveId], response]);
    }

    async _reloadRecord() {
        if (this.props.record?.model?.root) {
            await this.props.record.model.root.load();
        }
    }

    async _reloadView() {
        await this.action.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }

    _formatErrorMessage(error) {
        const rpcData = error?.data || {};
        const rpcMessage = rpcData?.message;
        const rpcArgs = Array.isArray(rpcData?.arguments) ? rpcData.arguments : [];
        const debug = typeof rpcData?.debug === "string" ? rpcData.debug : "";
        if (rpcMessage && !/internal error/i.test(rpcMessage)) {
            return rpcMessage;
        }
        if (rpcArgs.length && rpcArgs[0]) {
            return String(rpcArgs[0]);
        }
        if (debug) {
            const lines = debug.split("\n");
            const validation = lines.find((line) =>
                /ValidationError|UserError|No se puede|No se recib/i.test(line)
            );
            if (validation) {
                return validation.trim();
            }
        }
        if (error?.message && !/internal error/i.test(error.message)) {
            return error.message;
        }
        return "Error interno al imprimir fiscalmente.";
    }

    _setBlockingProgress(percent, message = "Imprimiendo...") {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (this._uiBlocked) {
            this.ui.unblock();
            this._uiBlocked = false;
        }
        this.ui.block({ message: `${message} ${pct}%` });
        this._uiBlocked = true;
    }

    _clearBlockingProgress() {
        if (this._uiBlocked) {
            this.ui.unblock();
            this._uiBlocked = false;
        }
    }

    async onClick() {
        const actionName = this.props.action;
        const moveId =
            this.props.record?.resId ||
            this.props.record?.data?.id ||
            this.env?.model?.root?.resId ||
            this.env?.model?.root?.data?.id;
        if (!moveId) {
            this.notification.add("No se pudo detectar la factura activa.", {
                type: "danger",
            });
            return;
        }
        if (!this.fiscalSerial.isSupported()) {
            this.notification.add("Web Serial no está disponible en este navegador.", {
                type: "danger",
            });
            return;
        }
        let driver;
        let borrowed = false;
        let auditLogger;
        let hadError = false;
        try {
            this._setBlockingProgress(0, "Imprimiendo...");
            const payload = await this._getPayload(actionName, moveId);
            const machineConfig = payload.fiscal_machine || {};
            this._setBlockingProgress(15, "Imprimiendo...");
            auditLogger = createFiscalSerialAuditLogger(this.env.services.orm, {
                source: ACTION_AUDIT_SOURCE[actionName] || "other",
                moveId,
                machineId: machineConfig.machine_id || false,
            });
            const authorized = await TfhkaWebSerialTransport.resolvePort(
                machineConfig,
                { requestPort: false }
            );
            const needPortPicker =
                !authorized.port && !this.connection.state.portOpen;
            if (needPortPicker) {
                this.notification.add(
                    "Seleccione la máquina fiscal en el cuadro de puertos del navegador.",
                    { type: "warning" }
                );
            }
            driver = await this.connection.borrowDriver({
                machine: machineConfig,
                requestPort: needPortPicker,
            });
            borrowed = true;
            auditLogger.attachDriver(driver);
            this._setBlockingProgress(20, "Imprimiendo...");
            const verification = await this.fiscalSerial.verifyConnectedFiscalMachine(
                driver,
                machineConfig,
                {
                    parseTfhkaS1StatusResponse: this.fiscalSerial.parseTfhkaS1StatusResponse,
                }
            );
            if (verification.training_mode || verification.emulator_mode) {
                this.notification.add(verification.message, { type: "warning" });
            }
            this._setBlockingProgress(25, "Imprimiendo...");
            const machine = this.fiscalSerial.createTfhkaFiscalMachine(driver);
            const response = await machine.runAction({
                action: actionName,
                data: payload,
                onProgress: ({ percent, message }) => {
                    this._setBlockingProgress(percent, message || "Imprimiendo...");
                },
            });
            if (!response?.valid) {
                console.error(
                    "[l10n_ve_fiscal_serial] Impresión fiscal rechazada",
                    response?.message,
                    response?.data ?? null
                );
                throw new Error(response?.message || "Fallo la impresión fiscal.");
            }
            this._setBlockingProgress(95, "Imprimiendo...");
            await this._persistResponse(actionName, moveId, response);
            await this._reloadRecord();
            await this._reloadView();
            this._setBlockingProgress(100, "Imprimiendo...");
            this.notification.add(response.message || "Operación fiscal completada.", {
                type: "success",
            });
        } catch (error) {
            hadError = true;
            const message = this._formatErrorMessage(error);
            console.error("[l10n_ve_fiscal_serial] Error impresión fiscal:", error);
            this.notification.add(message, {
                type: "danger",
            });
        } finally {
            if (auditLogger) {
                try {
                    await auditLogger.flush();
                } finally {
                    auditLogger.detachDriver(driver);
                }
            }
            if (borrowed) {
                await this.connection.releaseDriver({ close: false });
            }
            this._clearBlockingProgress();
        }
    }
}

registry.category("view_widgets").add("l10n_ve_fiscal_serial_button", {
    component: FiscalMoveButton,
    extractProps: ({ attrs, record }) => ({
        ...attrs,
        record,
    }),
});
