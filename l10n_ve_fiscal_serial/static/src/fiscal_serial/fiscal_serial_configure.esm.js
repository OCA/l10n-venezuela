/** @odoo-module **/

/* eslint-disable no-undef */

import {_t} from "@web/core/l10n/translation";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {createFiscalSerialAuditLogger} from "./fiscal_serial_audit";
import {TfhkaWebSerialTransport} from "./tfhka_transport_webserial";

export async function l10nVeFiscalSerialExecuteConfigure({
    env,
    machineId,
    logTag = "[l10n_ve_fiscal_serial]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const connection = env.services.l10n_ve_fiscal_connection;
    const notification = env.services.notification;
    const orm = env.services.orm;
    const ui = env.services.ui;
    const dialog = env.services.dialog;
    const progressLabel = _t("Configurando máquina fiscal");

    if (!machineId) {
        notification.add(_t("No se pudo detectar la máquina fiscal."), {
            type: "danger",
        });
        return false;
    }
    if (!fiscalSerial || !connection) {
        notification.add(_t("El servicio de máquina fiscal no está disponible."), {
            type: "danger",
        });
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para configurar desde el navegador."
            ),
            {type: "danger"}
        );
        return false;
    }

    const confirmed = await new Promise((resolve) => {
        dialog.add(ConfirmationDialog, {
            title: _t("Configurar máquina fiscal"),
            body: _t(
                "Se enviarán a la impresora el FLAG 21, FLAG 50, los 24 métodos de pago y el pie de página de la pestaña Configuración.\n\nNota: programar el pie de página requiere un reporte Z previo."
            ),
            confirm: () => resolve(true),
            cancel: () => resolve(false),
            confirmLabel: _t("Configurar"),
            cancelLabel: _t("Cancelar"),
        });
    });
    if (!confirmed) {
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
        const config = await orm.call(
            "l10n.ve.fiscal.machine",
            "l10n_ve_fiscal_serial_get_config",
            [[machineId]]
        );
        auditLogger = createFiscalSerialAuditLogger(orm, {
            source: "other",
            machineId: config.machine_id || machineId,
        });
        const authorized = await TfhkaWebSerialTransport.resolvePort(config, {
            requestPort: false,
        });
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
            machine: config,
            requestPort: needPortPicker,
        });
        borrowed = true;
        auditLogger.attachDriver(driver);
        setProgress(10, progressLabel);
        const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await machine.runAction({
            action: "configure_device",
            data: config,
            onProgress: ({percent, message}) => {
                setProgress(percent, message || progressLabel);
            },
        });
        if (!response?.valid) {
            throw new Error(
                response?.message || _t("No se pudo configurar la máquina fiscal.")
            );
        }
        setProgress(100, progressLabel);
        notification.add(
            response.message || _t("Configuración fiscal enviada correctamente."),
            {type: "success"}
        );
        return true;
    } catch (error) {
        const msg =
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error || _t("Error al configurar la máquina fiscal."));
        console.error(`${logTag} Error configuración fiscal:`, error);
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
