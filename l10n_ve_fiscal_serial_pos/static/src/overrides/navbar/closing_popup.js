/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { l10nVeFiscalSerialExecuteReport } from "@l10n_ve_fiscal_serial/fiscal_serial/fiscal_serial_report";
import {
    l10nVeFiscalSerialPosGetFiscalMachineId,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

function l10nVeFiscalMachineLabel(machine) {
    const name = (machine?.name || "").trim();
    const serial = (machine?.registered_serial || "").trim();
    if (name && serial && name !== serial) {
        return `${name} (${serial})`;
    }
    return name || serial || _t("Máquina fiscal");
}

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
        this.l10nVeFiscalConnection = useService("l10n_ve_fiscal_connection");
        this.l10nVeFiscalClose = useState({
            machineId: false,
            machines: [],
        });
        onWillStart(async () => {
            if (!this.l10nVeShowFiscalReports) {
                return;
            }
            await this.l10nVeEnsureFiscalMachines();
        });
    },

    get l10nVeShowFiscalReports() {
        return l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
    },

    get l10nVeSelectedFiscalMachine() {
        const machineId = Number(this.l10nVeFiscalClose.machineId) || 0;
        if (!machineId) {
            return null;
        }
        return (
            this.l10nVeFiscalClose.machines.find((item) => item.id === machineId) || null
        );
    },

    async l10nVeEnsureFiscalMachines() {
        const connection = this.l10nVeFiscalConnection;
        if (!connection) {
            return;
        }
        if (!connection.state.machines?.length && connection.loadSystrayData) {
            try {
                await connection.loadSystrayData();
            } catch (error) {
                console.warn(
                    "[l10n_ve_fiscal_serial_pos] Cierre: systray fiscal offline",
                    error
                );
            }
        }
        if (connection.refreshAuthorization) {
            try {
                await connection.refreshAuthorization();
            } catch (error) {
                console.warn(
                    "[l10n_ve_fiscal_serial_pos] Cierre: autorización fiscal local falló",
                    error
                );
            }
        }
        let machines = [...(connection.state.authorizedMachines || [])];
        if (!machines.length && connection.state.machines?.length) {
            machines = [];
        }
        this.l10nVeFiscalClose.machines = machines;
        const preferredId =
            Number(l10nVeFiscalSerialPosGetFiscalMachineId(this.pos)) ||
            Number(connection.state.machine?.id) ||
            Number(machines[0]?.id) ||
            0;
        const exists = machines.some((item) => item.id === preferredId);
        this.l10nVeFiscalClose.machineId = exists
            ? preferredId
            : Number(machines[0]?.id) || false;
    },

    l10nVeOnFiscalMachineChange(ev) {
        this.l10nVeFiscalClose.machineId = Number(ev.target.value) || false;
    },

    async l10nVeSelectFiscalMachine() {
        await this.l10nVeEnsureFiscalMachines();
        const machines = this.l10nVeFiscalClose.machines;
        if (!machines.length) {
            this.notification.add(
                _t(
                    "No hay máquinas fiscales autorizadas en este navegador. Use «Conectar» en el systray fiscal para autorizar el puerto USB."
                ),
                { type: "warning" }
            );
            return null;
        }
        if (machines.length === 1) {
            this.l10nVeFiscalClose.machineId = machines[0].id;
            return machines[0];
        }
        const selected = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Máquina fiscal"),
            list: machines.map((machine) => ({
                id: machine.id,
                label: l10nVeFiscalMachineLabel(machine),
                isSelected: machine.id === this.l10nVeFiscalClose.machineId,
                item: machine,
            })),
        });
        if (!selected) {
            return null;
        }
        this.l10nVeFiscalClose.machineId = selected.id;
        return selected;
    },

    async l10nVeResolveReportMachine() {
        let machine = this.l10nVeSelectedFiscalMachine;
        if (!machine) {
            machine = await this.l10nVeSelectFiscalMachine();
        }
        if (!machine) {
            this.notification.add(
                _t("Seleccione la máquina fiscal para imprimir el reporte."),
                { type: "warning" }
            );
            return null;
        }
        return machine;
    },

    async l10nVePrintFiscalReport(action) {
        const machine = await this.l10nVeResolveReportMachine();
        if (!machine) {
            return false;
        }
        return l10nVeFiscalSerialExecuteReport({
            env: this.env,
            action,
            machine,
            logTag: "[l10n_ve_fiscal_serial_pos]",
        });
    },

    async l10nVePrintXReport() {
        return this.l10nVePrintFiscalReport("report_x");
    },

    async l10nVePrintZReport() {
        return this.l10nVePrintFiscalReport("report_z");
    },
});
