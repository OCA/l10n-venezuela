/* eslint-disable no-undef */
export function formatWebSerialError(err) {
    if (!err) {
        return "Error desconocido.";
    }
    const name = err.name || "";
    const msg = (err.message && String(err.message).trim()) || "";
    const base = msg || String(err);
    if (name === "AbortError") {
        return "Selección de puerto cancelada.";
    }
    if (name === "NotAllowedError") {
        return "Permiso denegado para acceder al puerto serie.";
    }
    if (name === "NotFoundError") {
        return `Dispositivo no encontrado: ${base}`;
    }
    if (name === "SecurityError") {
        return `Web Serial bloqueado: use HTTPS y un origen permitido. ${base}`;
    }
    if (name === "InvalidStateError") {
        return `Puerto en estado inválido (puede estar abierto en otra pestaña). ${base}`;
    }
    if (/setSignals|control signals/i.test(base)) {
        return (
            "El adaptador USB no permite controlar las señales DTR/RTS; " +
            "se continuará sin ellas. Si falla la comunicación, cierre otras pestañas " +
            "que usen el puerto y vuelva a intentar."
        );
    }
    if (/locked to a reader|getReader/i.test(base)) {
        return (
            "El puerto serie está ocupado por otra lectura. Espere un momento " +
            "e intente de nuevo (cierre otras pestañas que usen el puerto si persiste)."
        );
    }
    if (name === "NetworkError") {
        return `Error de comunicación en el puerto serie: ${base}`;
    }
    return base || name || "Error desconocido.";
}

export function formatWebSerialPortLabel(portInfo = {}) {
    const parts = [];
    if (portInfo.usbVendorId) {
        parts.push(`USB:${portInfo.usbVendorId.toString(16).padStart(4, "0")}`);
    }
    if (portInfo.usbProductId) {
        parts.push(portInfo.usbProductId.toString(16).padStart(4, "0"));
    }
    if (portInfo.usbSerialNumber) {
        parts.push(portInfo.usbSerialNumber);
    }
    if (parts.length) {
        return parts.join("-");
    }
    return "Web Serial";
}

export function readWebSerialPortInfo(port) {
    if (!port?.getInfo) {
        return {
            usbVendorId: null,
            usbProductId: null,
            usbSerialNumber: null,
            label: "Web Serial",
        };
    }
    const info = port.getInfo();
    const portInfo = {
        usbVendorId: info.usbVendorId ?? null,
        usbProductId: info.usbProductId ?? null,
        usbSerialNumber: info.usbSerialNumber ?? null,
    };
    return {
        ...portInfo,
        label: formatWebSerialPortLabel(portInfo),
    };
}

function mergeUint8Arrays(chunks) {
    let n = 0;
    for (const c of chunks) {
        n += c.length;
    }
    const out = new Uint8Array(n);
    let o = 0;
    for (const c of chunks) {
        out.set(c, o);
        o += c.length;
    }
    return out;
}

export class TfhkaWebSerialTransport {
    constructor() {
        this.port = null;
        this._ioChain = Promise.resolve();
    }

    static isSupported() {
        return typeof navigator !== "undefined" && "serial" in navigator;
    }

    static async getAuthorizedPorts() {
        if (!TfhkaWebSerialTransport.isSupported()) {
            return [];
        }
        return navigator.serial.getPorts();
    }

    static portMatchesMachine(port, machine = {}) {
        if (!port || !machine) {
            return false;
        }
        const vendorId = Number(machine.webserial_usb_vendor_id || 0) || 0;
        const productId = Number(machine.webserial_usb_product_id || 0) || 0;
        const serialNumber = String(machine.webserial_usb_serial_number || "").trim();
        if (!vendorId && !productId && !serialNumber) {
            return false;
        }
        const info = port.getInfo?.() || {};
        if (vendorId && info.usbVendorId !== vendorId) {
            return false;
        }
        if (productId && info.usbProductId !== productId) {
            return false;
        }
        if (serialNumber && info.usbSerialNumber !== serialNumber) {
            return false;
        }
        return true;
    }

    static matchPortToMachine(ports, machine = {}, {strict = false} = {}) {
        if (!ports?.length) {
            return null;
        }
        const vendorId = Number(machine.webserial_usb_vendor_id || 0) || 0;
        const productId = Number(machine.webserial_usb_product_id || 0) || 0;
        const serialNumber = String(machine.webserial_usb_serial_number || "").trim();
        if (!vendorId && !productId && !serialNumber) {
            return strict ? null : ports[0];
        }
        const matched = ports.find((port) =>
            TfhkaWebSerialTransport.portMatchesMachine(port, machine)
        );
        if (matched) {
            return matched;
        }
        if (strict) {
            return null;
        }
        return ports.length === 1 ? ports[0] : null;
    }

    static filterAuthorizedMachines(machines, ports) {
        if (!machines?.length || !ports?.length) {
            return [];
        }
        return machines.filter((machine) =>
            Boolean(
                TfhkaWebSerialTransport.matchPortToMachine(ports, machine, {
                    strict: true,
                })
            )
        );
    }

    static async getAuthorizedMachines(machines) {
        const ports = await TfhkaWebSerialTransport.getAuthorizedPorts();
        return TfhkaWebSerialTransport.filterAuthorizedMachines(machines, ports);
    }

    /**
     * Resolve a Web Serial port for a fiscal machine.
     * Prefers already-authorized ports; only opens the browser picker when needed.
     *
     * @returns {Promise<{port: SerialPort|null, requested: boolean}>}
     */
    static async resolvePort(machine = {}, {requestPort = false, filters = []} = {}) {
        const ports = await TfhkaWebSerialTransport.getAuthorizedPorts();
        const matched = TfhkaWebSerialTransport.matchPortToMachine(ports, machine);
        if (matched) {
            return {port: matched, requested: false};
        }
        if (!requestPort) {
            return {port: null, requested: false};
        }
        if (!TfhkaWebSerialTransport.isSupported()) {
            throw new Error("Web Serial API no disponible en este navegador.");
        }
        const port = await navigator.serial.requestPort({filters});
        return {port, requested: true};
    }

    async requestPort(filters = []) {
        if (!TfhkaWebSerialTransport.isSupported()) {
            throw new Error("Web Serial API no disponible en este navegador.");
        }
        return navigator.serial.requestPort({filters});
    }

    _withIoLock(fn) {
        const run = this._ioChain.then(fn, fn);
        this._ioChain = run.then(
            () => undefined,
            () => undefined
        );
        return run;
    }

    async _releaseReader(reader, pendingRead) {
        if (pendingRead) {
            try {
                await reader.cancel();
            } catch {}
            try {
                await pendingRead;
            } catch {}
        }
        try {
            reader.releaseLock();
        } catch {}
    }

    async open(serialPort, options = {}) {
        const openOptions = {
            baudRate: options.baudRate ?? 9600,
            dataBits: options.dataBits ?? 8,
            stopBits: options.stopBits ?? 1,
            parity: options.parity ?? "even",
            bufferSize: options.bufferSize ?? 512,
            flowControl: options.flowControl ?? "none",
        };
        if (this.port && this.port !== serialPort) {
            await this.close();
        }
        if (this.port === serialPort && this.isOpen()) {
            return;
        }
        try {
            await serialPort.open(openOptions);
        } catch (err) {
            if (err?.name === "InvalidStateError") {
                try {
                    await serialPort.close();
                } catch {}
                await new Promise((resolve) => setTimeout(resolve, 100));
                await serialPort.open(openOptions);
            } else {
                throw err;
            }
        }
        this.port = serialPort;
        this._ioChain = Promise.resolve();
    }

    async close() {
        if (!this.port) {
            return;
        }
        const port = this.port;
        this.port = null;
        this._ioChain = Promise.resolve();
        try {
            await port.close();
        } catch {}
        await new Promise((resolve) => setTimeout(resolve, 50));
    }

    isOpen() {
        return Boolean(this.port && this.port.readable && this.port.writable);
    }

    async writeBytes(bytes, options = {}) {
        return this._withIoLock(async () => {
            if (!this.isOpen()) {
                throw new Error("Puerto serie cerrado.");
            }
            const postMs = options.postWriteDelayMs ?? 35;
            const writer = this.port.writable.getWriter();
            try {
                await writer.write(
                    bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
                );
            } finally {
                try {
                    writer.releaseLock();
                } catch {}
            }
            await new Promise((r) => setTimeout(r, postMs));
        });
    }

    async drainInput(maxTotalMs = 200) {
        return this._withIoLock(async () => {
            if (!this.isOpen()) {
                return;
            }
            const deadline = Date.now() + maxTotalMs;
            while (Date.now() < deadline) {
                const chunk = await this._readSomeUnlocked({
                    byteTimeout: 12,
                    totalTimeout: 45,
                    maxLen: 512,
                });
                if (chunk.length === 0) {
                    break;
                }
            }
        });
    }

    async readSome(options = {}) {
        return this._withIoLock(() => this._readSomeUnlocked(options));
    }

    async _readSomeUnlocked(options = {}) {
        if (!this.isOpen()) {
            return new Uint8Array(0);
        }
        const byteTimeout = options.byteTimeout ?? 20;
        const totalTimeout = options.totalTimeout ?? 1000;
        const maxLen = options.maxLen ?? 512;
        const reader = this.port.readable.getReader();
        const chunks = [];
        let total = 0;
        const start = Date.now();
        let lastData = Date.now();
        let pendingRead = null;
        try {
            while (Date.now() - start < totalTimeout && total < maxLen) {
                const wait = Math.min(
                    byteTimeout,
                    Math.max(1, start + totalTimeout - Date.now())
                );
                if (!pendingRead) {
                    pendingRead = reader.read().then(
                        (result) => ({kind: "read", result}),
                        (error) => ({kind: "error", error})
                    );
                }
                const raced = await Promise.race([
                    pendingRead,
                    new Promise((resolve) =>
                        setTimeout(() => resolve({kind: "timeout"}), wait)
                    ),
                ]);
                if (raced.kind === "timeout") {
                    if (total > 0 && Date.now() - lastData >= byteTimeout) {
                        break;
                    }
                    continue;
                }
                pendingRead = null;
                if (raced.kind === "error") {
                    throw raced.error;
                }
                const {value, done} = raced.result;
                if (done) {
                    break;
                }
                if (value && value.length) {
                    chunks.push(value);
                    total += value.length;
                    lastData = Date.now();
                } else if (total > 0 && Date.now() - lastData >= byteTimeout) {
                    break;
                }
            }
        } finally {
            await this._releaseReader(reader, pendingRead);
        }
        return mergeUint8Arrays(chunks);
    }

    async readOneByte(timeoutMs) {
        return this._withIoLock(async () => {
            if (!this.isOpen()) {
                return null;
            }
            const reader = this.port.readable.getReader();
            let pendingRead = reader.read().then(
                (result) => ({kind: "read", result}),
                (error) => ({kind: "error", error})
            );
            try {
                const raced = await Promise.race([
                    pendingRead,
                    new Promise((resolve) =>
                        setTimeout(() => resolve({kind: "timeout"}), timeoutMs)
                    ),
                ]);
                if (raced.kind === "timeout") {
                    return null;
                }
                pendingRead = null;
                if (raced.kind === "error") {
                    throw raced.error;
                }
                const {value} = raced.result;
                if (value && value.length) {
                    return value[0];
                }
                return null;
            } finally {
                await this._releaseReader(reader, pendingRead);
            }
        });
    }

    async setSignals(signals) {
        if (!this.port || typeof this.port.setSignals !== "function") {
            return false;
        }
        try {
            await this.port.setSignals(signals);
            return true;
        } catch (err) {
            console.warn(
                "[l10n_ve_fiscal_serial] setSignals omitido:",
                formatWebSerialError(err)
            );
            return false;
        }
    }
}
