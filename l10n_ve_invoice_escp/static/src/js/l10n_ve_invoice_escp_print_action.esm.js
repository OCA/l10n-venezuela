/** @odoo-module **/

import {Component, onMounted, xml} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

const USB_CHUNK = 16384;
const EPSON_USB_VENDOR_ID = 0x04b8;

function isUsbOpenAccessDeniedError(error) {
    if (!error) {
        return false;
    }
    const name = error.name || "";
    const msg = (error.message || "").toLowerCase();
    return (
        name === "SecurityError" ||
        name === "NetworkError" ||
        msg.includes("access denied") ||
        msg.includes("failed to execute 'open'") ||
        msg.includes("failed to open")
    );
}

function decodePayloadBytes(b64) {
    return Uint8Array.from(globalThis.atob(b64), (c) => c.charCodeAt(0));
}

function extractErrorMessage(error) {
    let msg = error?.message || String(error);
    if (error?.data?.message) {
        msg =
            typeof error.data.message === "string"
                ? error.data.message
                : error.data.message?.toString?.() || msg;
    }
    if (
        error?.message === "USB_OPEN_ACCESS_DENIED" ||
        error?.message === "USB_CLAIM_ACCESS_DENIED"
    ) {
        return _t(
            "Permiso USB denegado. Cierre otras pestañas que usen la impresora o conceda acceso en el navegador."
        );
    }
    return msg;
}

function throwIfUsbDenied(error, code) {
    if (isUsbOpenAccessDeniedError(error)) {
        const denied = new Error(code);
        denied.cause = error;
        throw denied;
    }
    throw error;
}

async function openEpsonUsbDevice() {
    const usb = globalThis.navigator && globalThis.navigator.usb;
    if (!usb) {
        throw new Error(_t("WebUSB no está disponible (use Chrome/Edge y HTTPS)."));
    }
    const device = await usb.requestDevice({
        filters: [{vendorId: EPSON_USB_VENDOR_ID}],
    });
    try {
        await device.open();
    } catch (error) {
        throwIfUsbDenied(error, "USB_OPEN_ACCESS_DENIED");
    }
    return device;
}

function resolveUsbConfiguration(device) {
    return (
        device.configuration ||
        device.configurations.find((item) => item.configurationValue === 1) ||
        device.configurations[0]
    );
}

function findBulkOutEndpoint(alternate) {
    if (!alternate) {
        return null;
    }
    return (
        alternate.endpoints.find(
            (endpoint) => endpoint.type === "bulk" && endpoint.direction === "out"
        ) || null
    );
}

async function transferUsbChunks(device, endpointNumber, uint8Array) {
    for (let offset = 0; offset < uint8Array.length; offset += USB_CHUNK) {
        const chunk = uint8Array.subarray(
            offset,
            Math.min(offset + USB_CHUNK, uint8Array.length)
        );
        await device.transferOut(endpointNumber, chunk);
    }
}

async function sendOnBulkInterface(device, iface, uint8Array) {
    const bulkOut = findBulkOutEndpoint(iface.alternates[0]);
    if (!bulkOut) {
        return false;
    }
    try {
        await device.claimInterface(iface.interfaceNumber);
    } catch (error) {
        throwIfUsbDenied(error, "USB_CLAIM_ACCESS_DENIED");
    }
    try {
        await transferUsbChunks(device, bulkOut.endpointNumber, uint8Array);
    } finally {
        await device.releaseInterface(iface.interfaceNumber);
    }
    return true;
}

async function sendEpsonEscpWebUSB(uint8Array) {
    const device = await openEpsonUsbDevice();
    try {
        const config = resolveUsbConfiguration(device);
        if (!config) {
            throw new Error(_t("El dispositivo USB no tiene configuración."));
        }
        if (device.configuration === null) {
            await device.selectConfiguration(config.configurationValue);
        }
        for (const iface of device.configuration.interfaces) {
            if (await sendOnBulkInterface(device, iface, uint8Array)) {
                return;
            }
        }
        throw new Error(
            _t(
                "No se encontró un endpoint de salida compatible. Compruebe que sea una impresora Epson ESC/P por USB."
            )
        );
    } finally {
        try {
            await device.close();
        } catch {
            /* Ignore */
        }
    }
}

export class L10nVeInvoiceEscpPrintAction extends Component {
    static target = "new";
    static props = {...standardActionServiceProps};
    static template = xml`<div class="o_invisible_modifier"/>`;

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        onMounted(() => this.run());
    }

    async run() {
        const moveId = this.props.action.params?.move_id;
        try {
            if (!moveId) {
                this.notification.add(_t("Falta el identificador de la factura."), {
                    type: "danger",
                });
                return;
            }
            const {payload_b64: b64} = await this.orm.call(
                "account.move",
                "l10n_ve_invoice_escp_get_payload",
                [moveId]
            );
            await sendEpsonEscpWebUSB(decodePayloadBytes(b64));
            await this.orm.call(
                "account.move",
                "l10n_ve_invoice_escp_confirm_printed",
                [moveId]
            );
            this.notification.add(_t("Impresión enviada a la impresora."), {
                type: "success",
            });
        } catch (error) {
            this.notification.add(extractErrorMessage(error), {type: "danger"});
        } finally {
            try {
                await this.action.doAction({type: "ir.actions.act_window_close"});
            } catch {
                /* Dialog closed */
            }
        }
    }
}

registry
    .category("actions")
    .add("l10n_ve_invoice_escp_print", L10nVeInvoiceEscpPrintAction);
