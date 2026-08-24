/* eslint-disable complexity */
import {TfhkaWebSerialTransport} from "./tfhka_transport_webserial";
import {_t} from "@web/core/l10n/translation";
import {createFiscalSerialAuditLogger} from "./fiscal_serial_audit";

const REPORT_LABELS = {
    report_x: _t("Reporte X"),
    report_z: _t("Reporte Z"),
};

async function l10nVeFiscalSerialPersistReportZCounters({env, machineId, response}) {
    const orm = env.services.orm;
    const connection = env.services.l10n_ve_fiscal_connection;
    const data = response?.data || {};
    const targetId = Number(machineId) || 0;
    if (!orm || !targetId) {
        return false;
    }
    const payload = {};
    if (data.daily_closure_counter) {
        payload.daily_closure_counter = String(data.daily_closure_counter);
    }
    if (data.last_invoice_number) {
        payload.last_invoice_number = String(data.last_invoice_number);
    }
    if (data.last_credit_note_number) {
        payload.last_credit_note_number = String(data.last_credit_note_number);
    }
    if (data.last_debit_note_number) {
        payload.last_debit_note_number = String(data.last_debit_note_number);
    }
    if (data.serial_machine) {
        payload.registered_serial = String(data.serial_machine);
    }
    if (!Object.keys(payload).length) {
        return false;
    }
    const pos = env.services.pos;
    const localMachine = pos?.models?.["l10n.ve.fiscal.machine"]?.get?.(targetId);
    if (localMachine?.update) {
        localMachine.update(payload);
    }
    let updated = false;
    try {
        updated = await orm.call("l10n.ve.fiscal.machine", "apply_s1_counters", [
            [targetId],
            payload,
        ]);
        if (connection?.loadSystrayData) {
            await connection.loadSystrayData();
        }
    } catch (error) {
        console.warn(
            "[l10n_ve_fiscal_serial] Contadores Z guardados localmente (sin servidor).",
            error
        );
        updated = payload;
    }
    return Boolean(updated);
}

export async function l10nVeFiscalSerialExecuteReport({
    env,
    action,
    machine = null,
    logTag = "[l10n_ve_fiscal_serial]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const connection = env.services.l10n_ve_fiscal_connection;
    const notification = env.services.notification;
    const ui = env.services.ui;
    const progressLabel = REPORT_LABELS[action] || _t("Imprimiendo reporte fiscal");

    if (!fiscalSerial || !connection) {
        notification.add(_t("El servicio de máquina fiscal no está disponible."), {
            type: "danger",
        });
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir desde el navegador."
            ),
            {type: "danger"}
        );
        return false;
    }

    let borrowed = false;
    let driver = null;
    let auditLogger = null;
    let blocked = false;
    const setProgress = (percent, message) => {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (blocked) {
            ui.unblock();
            blocked = false;
        }
        ui.block({message: `${message || progressLabel} ${pct}%`});
        blocked = true;
    };

    try {
        setProgress(0, progressLabel);
        const machineId = Number(machine?.machine_id || machine?.id || 0) || 0;
        if (machineId && connection.setPrimaryMachine) {
            await connection.setPrimaryMachine(machineId);
        }
        auditLogger = createFiscalSerialAuditLogger(env.services.orm, {
            source: "report",
            machineId: machineId || connection.state.machine?.id || false,
        });
        const authorized = await TfhkaWebSerialTransport.resolvePort(
            machine || connection.state.machine || {},
            {requestPort: false}
        );
        const needPortPicker = !authorized.port && !connection.state.portOpen;
        if (needPortPicker) {
            notification.add(
                _t(
                    "Seleccione la máquina fiscal en el cuadro de puertos del navegador."
                ),
                {type: "warning"}
            );
        }
        driver = await connection.borrowDriver({
            machine: machine || undefined,
            requestPort: needPortPicker,
        });
        borrowed = true;
        auditLogger.attachDriver(driver);
        setProgress(50, progressLabel);
        const tfhka = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await tfhka.runAction({action, data: {}});
        if (!response?.valid) {
            throw new Error(
                response?.message || _t("No se pudo imprimir el reporte fiscal.")
            );
        }
        if (action === "report_z") {
            await l10nVeFiscalSerialPersistReportZCounters({
                env,
                machineId: machineId || Number(connection.state.machine?.id || 0) || 0,
                response,
            });
        }
        setProgress(100, progressLabel);
        notification.add(response.message || `${progressLabel} ${_t("completado.")}`, {
            type: "success",
        });
        return true;
    } catch (error) {
        const msg =
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error || _t("Error al imprimir el reporte fiscal."));
        console.error(`${logTag} Error reporte fiscal:`, error);
        notification.add(msg, {type: "danger"});
        return false;
    } finally {
        if (auditLogger) {
            try {
                await auditLogger.flush();
            } finally {
                auditLogger.detachDriver(driver);
            }
        }
        if (borrowed) {
            await connection.releaseDriver({close: false});
        }
        if (blocked) {
            ui.unblock();
        }
    }
}
