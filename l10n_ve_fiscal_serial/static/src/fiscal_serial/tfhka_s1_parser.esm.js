/** @odoo-module **/

export function mfReportzFromDailyClosureString(counter) {
    if (counter === undefined || counter === null || String(counter).trim() === "") {
        return null;
    }
    const s = String(counter).trim();
    if (!/^\d+$/.test(s)) {
        return null;
    }
    const n = parseInt(s, 10);
    if (!Number.isFinite(n)) {
        return null;
    }
    const next = n + 1;
    const width = Math.max(4, s.length);
    return String(next).padStart(width, "0");
}

function normalizeS1Raw(raw) {
    return String(raw || "")
        .replace(/\r/g, "")
        .replace(/\x02/g, "")
        .replace(/\x03[\s\S]*$/g, "")
        .trim();
}

function splitS1Parts(raw) {
    const normalized = normalizeS1Raw(raw);
    return normalized
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
}

export function parseTfhkaS1StatusResponse(raw) {
    const text = String(raw || "");
    const parts = splitS1Parts(text);
    const out = {
        raw: text,
        LastInvoiceNumber: null,
        LastCreditNoteNumber: null,
        LastDebitNoteNumber: null,
        DailyClosureCounter: null,
        RegisteredMachineNumber: null,
        DailySalesTotal: null,
        CashierCode: null,
        InvoicesCountDay: null,
    };
    if (!parts.length) {
        return out;
    }
    let i = 0;
    if (/^S1/i.test(parts[0])) {
        out.CashierCode = parts[0].length > 2 ? parts[0].slice(2) : null;
        i = 1;
    }
    if (i < parts.length && /^\d+$/.test(parts[i])) {
        out.DailySalesTotal = parts[i];
        i++;
    }
    let invIdx = -1;
    if (i < parts.length && /^\d{8}$/.test(parts[i])) {
        out.LastInvoiceNumber = parts[i];
        invIdx = i;
        i++;
    } else if (
        i + 1 < parts.length &&
        /^\d{5,8}$/.test(parts[i]) &&
        !/^\d{8}$/.test(parts[i]) &&
        /^\d{8}$/.test(parts[i + 1])
    ) {
        invIdx = i + 1;
        out.LastInvoiceNumber = parts[i + 1];
        i += 2;
    }
    if (invIdx >= 0 && invIdx + 4 < parts.length) {
        const p1 = parts[invIdx + 1];
        const p2 = parts[invIdx + 2];
        const p3 = parts[invIdx + 3];
        const p4 = parts[invIdx + 4];
        if (
            /^\d{5}$/.test(p1) &&
            /^\d{8}$/.test(p2) &&
            /^\d{5}$/.test(p3) &&
            /^\d{8}$/.test(p4)
        ) {
            out.InvoicesCountDay = p1;
            out.LastCreditNoteNumber = p4;
        } else if (/^\d{5}$/.test(p1) && /^\d{8}$/.test(p2)) {
            out.InvoicesCountDay = p1;
        }
    }
    const rifIdx = parts.findIndex(
        (p) =>
            typeof p === "string" &&
            (/^[JVGE]-/i.test(p) || /^[JVGE]\d/i.test(p) || /^[VEJ]-\d{9,}/i.test(p))
    );
    if (rifIdx > 0) {
        const beforeRif = parts[rifIdx - 1];
        if (/^\d{4}$/.test(beforeRif)) {
            out.DailyClosureCounter = beforeRif;
        }
        if (rifIdx + 1 < parts.length) {
            const afterRif = parts[rifIdx + 1];
            if (
                typeof afterRif === "string" &&
                afterRif.length >= 8 &&
                afterRif.length <= 16 &&
                /[A-Za-z]/.test(afterRif) &&
                /^[A-Z0-9-]+$/i.test(afterRif)
            ) {
                out.RegisteredMachineNumber = afterRif.trim();
            }
        }
    }
    if (!out.RegisteredMachineNumber) {
        const m = parts.find(
            (p) =>
                p &&
                p.length === 10 &&
                /^[A-Z][A-Z0-9]{9}$/i.test(p) &&
                /[A-Z]/i.test(p)
        );
        if (m) {
            out.RegisteredMachineNumber = m;
        }
    }
    if (!out.LastCreditNoteNumber) {
        out.LastCreditNoteNumber = out.LastInvoiceNumber;
    }
    out.LastDebitNoteNumber = out.LastInvoiceNumber;
    if (!out.LastInvoiceNumber) {
        const groups = text.match(/\d+/g) || [];
        const fallback = groups.length ? groups[groups.length - 1] : null;
        out.LastInvoiceNumber = fallback;
        if (!out.LastCreditNoteNumber) {
            out.LastCreditNoteNumber = fallback;
        }
        if (!out.LastDebitNoteNumber) {
            out.LastDebitNoteNumber = fallback;
        }
    }
    return out;
}
