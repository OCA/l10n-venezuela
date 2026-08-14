/** @odoo-module **/

import { Component, onWillUnmount, status, useComponent, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { autoDetectFiscalMachine } from "./fiscal_machine_detect";
import { createFiscalSerialAuditLogger } from "../fiscal_serial/fiscal_serial_audit";
import {
    describeTfhkaEnqSts1,
    describeTfhkaEnqSts2,
} from "../fiscal_serial/tfhka_protocol";

export class FiscalMachinePortUpdateWidget extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachinePortUpdateWidget";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.component = useComponent();
        this.fiscalSerial = useService("l10n_ve_fiscal_serial");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.state = useState({ busy: false });
        this.alive = true;
        onWillUnmount(() => {
            this.alive = false;
        });
    }

    _isAlive() {
        return this.alive && status(this.component) !== "destroyed";
    }

    _formatError(error) {
        return (
            this.fiscalSerial.formatWebSerialError?.(error) ||
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error)
        );
    }

    async onUpdatePort() {
        const record = this.props.record;
        if (!record?.resId || this.state.busy) {
            return;
        }
        if (!this.fiscalSerial.isSupported()) {
            this.notification.add(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS.",
                { type: "danger" }
            );
            return;
        }
        this.state.busy = true;
        let driver = null;
        let auditLogger = null;
        let blocked = false;
        let hadError = false;
        let errorDetail = "";
        try {
            this.notification.add(
                "Seleccione el puerto USB de esta máquina fiscal en el navegador.",
                { type: "warning" }
            );
            driver = this.fiscalSerial.createTfhkaFiscal();
            auditLogger = createFiscalSerialAuditLogger(this.orm, {
                source: "machine_port_update",
                machineId: record.resId,
            });
            auditLogger.attachDriver(driver);
            const baudRate = parseInt(record.data.baudrate || "9600", 10);
            const parity = record.data.parity === "none" ? "none" : "even";
            const opened = await driver.openFpCtrl({ baudRate, parity });
            if (!opened) {
                throw new Error(driver.estado || "No fue posible abrir el puerto serial.");
            }
            this.ui.block({ message: "Actualizando puerto de la máquina fiscal…" });
            blocked = true;
            const payload = await autoDetectFiscalMachine(driver, {
                parseTfhkaS1StatusResponse: this.fiscalSerial.parseTfhkaS1StatusResponse,
                describeTfhkaEnqSts1,
                describeTfhkaEnqSts2,
            });
            const result = await this.orm.call(
                "l10n.ve.fiscal.machine",
                "apply_port_update_from_detect",
                [[record.resId], payload]
            );
            await record.model.root.load();
            if (this._isAlive()) {
                this.notification.add(
                    result.message || "Puerto actualizado correctamente.",
                    {
                        type: result.training_mode ? "warning" : "success",
                    }
                );
            }
        } catch (error) {
            hadError = true;
            const message = this._formatError(error);
            errorDetail = message;
            console.error("[l10n_ve_fiscal_serial][port_update]", error);
            if (this._isAlive()) {
                this.notification.add(message, { type: "danger" });
            }
        } finally {
            if (driver) {
                try {
                    await driver.closeFpCtrl({
                        reason: hadError ? "error" : "port_update",
                        detail: errorDetail,
                    });
                } catch {
                }
            } else if (auditLogger) {
                await auditLogger.flush();
            }
            if (blocked) {
                this.ui.unblock();
            }
            if (this._isAlive()) {
                this.state.busy = false;
            }
        }
    }
}

registry.category("view_widgets").add("fiscal_machine_port_update", {
    component: FiscalMachinePortUpdateWidget,
});
