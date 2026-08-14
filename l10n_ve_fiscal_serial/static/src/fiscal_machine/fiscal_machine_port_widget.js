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

const pendingDetections = new Set();

export class FiscalMachinePortDetectWidget extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachinePortDetectWidget";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.component = useComponent();
        this.fiscalSerial = useService("l10n_ve_fiscal_serial");
        this.notification = useService("notification");
        this.orm = this.env.services.orm;
        this.ui = this.env.services.ui;
        this.state = useState({ busy: false });
        this.alive = true;
        onWillUnmount(() => {
            this.alive = false;
        });
        this.driver = null;
    }

    _isAlive() {
        return this.alive && status(this.component) !== "destroyed";
    }

    _getRecordModel() {
        return this.props.record.model;
    }

    _getRootRecord() {
        return this._getRecordModel().root;
    }

    _detectionKey(record) {
        return record.resId || "new";
    }

    _filterServerValues(record, serverValues) {
        const out = {};
        for (const [key, value] of Object.entries(serverValues || {})) {
            if (key in record.fields) {
                out[key] = value;
            }
        }
        return out;
    }

    async _ensureWizardResId(record) {
        if (record.resId) {
            return record.resId;
        }
        const saved = await record.save({ reload: false });
        if (!saved || !record.resId) {
            throw new Error("No se pudo crear el asistente de configuración.");
        }
        return record.resId;
    }

    async _setPendingState(record) {
        await record.update(
            {
                detect_state: "pending",
                detect_message: "Seleccione el puerto COM/Web Serial en el navegador…",
            },
            { save: false }
        );
    }

    async _applyDetectResult(recordModel, payload) {
        const record = recordModel.root;
        await this._ensureWizardResId(record);
        const serverValues = await this.orm.call(record.resModel, "apply_detect_result", [
            [record.resId],
            payload,
        ]);
        const values = this._filterServerValues(recordModel.root, serverValues);
        if (Object.keys(values).length) {
            await recordModel.root.update(values, { save: false });
        }
        return serverValues;
    }

    async onDetectPort() {
        const recordModel = this._getRecordModel();
        const record = recordModel.root;
        const detectionKey = this._detectionKey(record);
        if (pendingDetections.has(detectionKey)) {
            return;
        }
        if (this.state.busy) {
            return;
        }
        if (!this.fiscalSerial.isSupported()) {
            this.notification.add(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS.",
                { type: "danger" }
            );
            return;
        }
        pendingDetections.add(detectionKey);
        this.state.busy = true;
        let driver = null;
        let auditLogger = null;
        let blocked = false;
        let hadError = false;
        let errorDetail = "";
        try {
            await this._ensureWizardResId(recordModel.root);
            await this._setPendingState(recordModel.root);
            if (this._isAlive()) {
                this.notification.add(
                    "Seleccione el puerto de la máquina fiscal en el cuadro del navegador.",
                    { type: "warning" }
                );
            }
            driver = this.fiscalSerial.createTfhkaFiscal();
            auditLogger = createFiscalSerialAuditLogger(this.orm, {
                source: "machine_detect",
            });
            auditLogger.attachDriver(driver);
            const currentRecord = recordModel.root;
            const baudRate = parseInt(currentRecord.data.baudrate || "9600", 10);
            const parity = currentRecord.data.parity || "even";
            const opened = await driver.openFpCtrl({ baudRate, parity });
            if (!opened) {
                throw new Error(driver.estado || "No fue posible abrir el puerto serial.");
            }
            this.ui.block({ message: "Detectando máquina fiscal…" });
            blocked = true;
            let flag21 = recordModel.root.data.flag_21 || "00";
            const payload = await autoDetectFiscalMachine(driver, {
                parseTfhkaS1StatusResponse: this.fiscalSerial.parseTfhkaS1StatusResponse,
                describeTfhkaEnqSts1,
                describeTfhkaEnqSts2,
            });
            await this._applyDetectResult(recordModel, {
                ...payload,
                flag_21: flag21,
            });
            console.log("[l10n_ve_fiscal_serial][detect]", payload);
            if (this._isAlive()) {
                const notificationType =
                    payload.enq_status === 64 &&
                    (!payload.registered_serial || !payload.fiscal_rif)
                        ? "warning"
                        : "success";
                const notificationMessage =
                    payload.detect_message ||
                    "Máquina fiscal detectada. Revise los datos y guarde.";
                this.notification.add(notificationMessage, {
                    type: notificationType,
                });
            }
        } catch (error) {
            hadError = true;
            const message =
                this.fiscalSerial.formatWebSerialError?.(error) ||
                error?.message ||
                String(error);
            errorDetail = message;
            try {
                const rootRecord = recordModel.root;
                if (rootRecord.resId) {
                    await this._applyDetectResult(recordModel, {
                        detect_state: "error",
                        detect_message: message,
                    });
                } else {
                    await rootRecord.update(
                        {
                            detect_state: "error",
                            detect_message: message,
                        },
                        { save: false }
                    );
                }
            } catch {
            }
            console.error("[l10n_ve_fiscal_serial][detect]", error);
            if (this._isAlive()) {
                this.notification.add(message, { type: "danger" });
            }
        } finally {
            if (driver) {
                try {
                    await driver.closeFpCtrl({
                        reason: hadError ? "error" : "finally_cleanup",
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
            pendingDetections.delete(detectionKey);
            if (this._isAlive()) {
                this.state.busy = false;
            }
        }
    }
}

registry.category("view_widgets").add("fiscal_machine_port_detect", {
    component: FiscalMachinePortDetectWidget,
});
