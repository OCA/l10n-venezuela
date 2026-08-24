from odoo.tools.mail import html2plaintext
from odoo.tools.misc import formatLang

_DEFAULT_ESC_P_MARGIN_LINES = 8

PAGE_WIDTH_CM = 21.25
PAGE_HEIGHT_CM = 21.5

_LPI_DEFAULT = 6

LINE_WIDTH = min(
    136,
    max(80, int(round(PAGE_WIDTH_CM / 2.54 * 17))),
)

PAGE_LENGTH_LINES = max(
    1,
    min(127, int(round(PAGE_HEIGHT_CM / 2.54 * _LPI_DEFAULT))),
)

_ESC_P_MATRIX_SLOWER = b"\x1b\x78\x01\x1b\x55\x01"
_ESC_P_MATRIX_SPEED_RESTORE = b"\x1b\x78\x00\x1b\x55\x00"
_ESC_P_DOUBLE_STRIKE_ON = b"\x1bG"
_ESC_P_DOUBLE_STRIKE_OFF = b"\x1bH"
_ESC_P_FONT_RESTORE = b"\x1b\x50\x1b\x32"


def _document_title(move):
    if move.move_type == "out_refund" and move.reversed_entry_id:
        return "NOTA DE CREDITO"
    if move.move_type == "out_invoice" and move.debit_origin_id:
        return "NOTA DE DEBITO"
    if move.move_type == "out_invoice":
        return "FACTURA"
    return "DOCUMENTO"


def _doc_number_label(move):
    if move.move_type == "out_refund":
        return "Nota de Credito:"
    if move.move_type == "out_invoice" and move.debit_origin_id:
        return "Nota de Debito:"
    return "Factura:"


def _enc(text):
    if text is None:
        text = ""
    return str(text).encode("cp858", errors="replace")


def _clip(s, max_len):
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    return s[: max_len - 2] + ".."


def _pad_left(s, width):
    s = _clip(s, width)
    return s.rjust(width)


def _pad_right(s, width):
    s = _clip(s, width)
    return s.ljust(width)


def _pad_amount(s, width):
    s = (s or "").strip()
    if len(s) <= width:
        return s.rjust(width)
    return s


def _pad_code(s, width):
    s = s or ""
    if len(s) <= width:
        return s.ljust(width)
    return s


def _center_line(text, width):
    t = _clip(text, width)
    if not t:
        return " " * width
    pad = max(0, (width - len(t)) // 2)
    line = " " * pad + t
    return line[:width].ljust(width)


def _two_cols(width, left, right, ratio_left=0.5):
    w_l = int(width * ratio_left)
    w_r = width - w_l
    return (_pad_right(left, w_l) + _pad_left(right, w_r))[:width]


def _three_cols(width, left, center, right):
    w_l = int(width * 0.40)
    w_c = int(width * 0.24)
    w_r = width - w_l - w_c
    return (_pad_right(left, w_l) + _pad_right(center, w_c) + _pad_left(right, w_r))[
        :width
    ]


def _wrap(text, line_width):
    text = (text or "").replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return []
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip() if cur else w
        if len(test) <= line_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            if len(w) <= line_width:
                cur = w
            else:
                for i in range(0, len(w), line_width):
                    lines.append(w[i : i + line_width])
                cur = ""
    if cur:
        lines.append(cur)
    return lines[:120]


def _money(env, amount, currency):
    return formatLang(env, amount, currency_obj=currency)


def _tax_line_labels(move):
    totals = move.tax_totals or {}
    all_groups = [
        group
        for subtotal in totals.get("subtotals", [])
        for group in subtotal.get("tax_groups", [])
    ]
    vat_groups = [g for g in all_groups if g.get("id") != -1]
    igtf_groups = [g for g in all_groups if g.get("id") == -1]
    vat_group = vat_groups[0] if vat_groups else {}
    igtf_group = igtf_groups[0] if igtf_groups else {}
    vat_name_tokens = [
        t for t in vat_group.get("group_name", "").replace(":", " ").split() if "%" in t
    ]
    vat_percent = vat_name_tokens[0] if vat_name_tokens else "16%"
    igtf_val = getattr(move.company_id, "l10n_ve_igtf_percent", None) or 3.0
    igtf_percent = str(igtf_val).replace(".", ",") + "%"
    return vat_percent, igtf_percent, vat_group, igtf_group, totals


def _footer_note_totals_widths(lw):
    w1 = (lw * 6) // 12
    w2 = (lw * 2) // 12
    w3 = (lw * 2) // 12
    w4 = lw - w1 - w2 - w3
    return w1, w2, w3, w4


def _l10n_ve_escp_cn_nd_single_currency(move):
    if move.company_id.account_fiscal_country_id.code != "VE":
        return False
    if move.currency_id != move.company_currency_id:
        return False
    return move.move_type == "out_refund" or (
        move.move_type == "out_invoice" and move.debit_origin_id
    )


def _footer_note_totals_widths_cn_bs(lw):
    w1 = (lw * 6) // 12
    w2 = (lw * 3) // 12
    w3 = lw - w1 - w2
    return w1, w2, w3


def _three_column_footer_line(text1, text2, text3, w1, w2, w3):
    c1 = _pad_right(_clip(text1, w1), w1)
    c2 = _pad_right(_clip(text2, w2), w2)
    c3 = _pad_amount(text3, w3)
    return c1 + c2 + c3


def _four_column_line(text1, text2, text3, text4, w1, w2, w3, w4):
    c1 = _pad_right(_clip(text1, w1), w1)
    c2 = _pad_right(_clip(text2, w2), w2)
    c3 = _pad_amount(text3, w3)
    c4 = _pad_amount(text4, w4)
    return c1 + c2 + c3 + c4


def _totals_data_rows(env, move):
    doc_currency = move.currency_id
    comp_currency = move.company_currency_id
    show_cc = comp_currency != doc_currency
    vat_percent, igtf_percent, vat_group, igtf_group, totals = _tax_line_labels(move)
    rows = []

    def add(label, doc_amt, comp_amt=0.0):
        rows.append((label, doc_amt, comp_amt if show_cc else None))

    add(
        "Subtotal:",
        totals.get("base_amount_currency", 0.0),
        totals.get("base_amount", 0.0),
    )
    add(
        f"B.I {vat_percent}:",
        vat_group.get(
            "display_base_amount_currency",
            vat_group.get("base_amount_currency", 0.0),
        ),
        vat_group.get("display_base_amount", vat_group.get("base_amount", 0.0)),
    )
    add(
        f"{vat_percent}:",
        vat_group.get("tax_amount_currency", 0.0),
        vat_group.get("tax_amount", 0.0),
    )
    add(
        "Base Imponible IGTF:",
        igtf_group.get(
            "display_base_amount_currency",
            igtf_group.get("base_amount_currency", 0.0),
        ),
        igtf_group.get("display_base_amount", igtf_group.get("base_amount", 0.0)),
    )
    add(
        f"IGTF {igtf_percent}:",
        igtf_group.get("tax_amount_currency", 0.0),
        igtf_group.get("tax_amount", 0.0),
    )
    add(
        "Total a Pagar:",
        totals.get("total_amount_currency", 0.0),
        totals.get("total_amount", 0.0),
    )
    return rows, doc_currency, comp_currency, show_cc


def _seniat_left_column_lines(move, width):
    parts = []
    if move.narration:
        parts.append(html2plaintext(move.narration or ""))
    if move.seniat_invoice_tag:
        parts.append(html2plaintext(move.seniat_invoice_tag or ""))
    text = "\n\n".join(p for p in parts if p and p.strip())
    if not text.strip():
        return []
    out = []
    for ln in _wrap(text.strip(), width):
        out.append(_clip(ln, width))
    return out


def _product_col_layout(lw, show_cc):
    gap_n_cc = 7
    gap_n_one = 6
    if show_cc:
        w_hash = 2
        w_code = 20
        w_qty = 7
        w_pu = 12
        w_tax = 10
        w_sbs = 14
        w_sd = 14
        w_desc = lw - (w_hash + w_code + w_tax + w_qty + w_pu + w_sbs + w_sd + gap_n_cc)
        w_desc = max(12, w_desc)
        return {
            "w_hash": w_hash,
            "w_code": w_code,
            "w_desc": w_desc,
            "w_qty": w_qty,
            "w_pu": w_pu,
            "w_tax": w_tax,
            "w_sbs": w_sbs,
            "w_sd": w_sd,
            "gap_n": gap_n_cc,
            "show_cc": True,
        }
    w_hash = 2
    w_code = 22
    w_qty = 7
    w_pu = 12
    w_tax = 12
    w_sd = 16
    w_desc = lw - (w_hash + w_code + w_tax + w_qty + w_pu + w_sd + gap_n_one)
    w_desc = max(14, w_desc)
    return {
        "w_hash": w_hash,
        "w_code": w_code,
        "w_desc": w_desc,
        "w_qty": w_qty,
        "w_pu": w_pu,
        "w_tax": w_tax,
        "w_sbs": 0,
        "w_sd": w_sd,
        "gap_n": gap_n_one,
        "show_cc": False,
    }


def _product_header_line(move, layout):
    doc_sym = move.currency_id.symbol or move.currency_id.name or "$"
    comp_sym = move.company_currency_id.symbol or move.company_currency_id.name
    if layout["show_cc"]:
        parts = [
            f"{'#':<{layout['w_hash']}}",
            f"{'CODIGO':<{layout['w_code']}}",
            f"{'DESCRIPCION':<{layout['w_desc']}}",
            f"{'IMP.':<{layout['w_tax']}}",
            f"{'CANT.':>{layout['w_qty']}}",
            f"{'P.U.' + doc_sym:>{layout['w_pu']}}",
            f"{'SUBT' + comp_sym:>{layout['w_sbs']}}",
            f"{'SUBT' + doc_sym:>{layout['w_sd']}}",
        ]
    else:
        parts = [
            f"{'#':<{layout['w_hash']}}",
            f"{'CODIGO':<{layout['w_code']}}",
            f"{'DESCRIPCION':<{layout['w_desc']}}",
            f"{'IMPUESTO':<{layout['w_tax']}}",
            f"{'CANT.':>{layout['w_qty']}}",
            f"{'P.U.' + doc_sym:>{layout['w_pu']}}",
            f"{'SUBTOTAL':>{layout['w_sd']}}",
        ]
    h = " ".join(parts)
    return h[:LINE_WIDTH].ljust(LINE_WIDTH)


def _format_product_row(
    env, line, item, layout, doc_currency, comp_currency, desc_cell
):
    show_cc = layout["show_cc"]
    code = (line.product_id.default_code or "") if line.product_id else ""
    tax_txt = ", ".join(line.tax_ids.mapped("name")) if line.tax_ids else ""
    qty_s = _pad_amount(f"{line.quantity:.2f}", layout["w_qty"])
    pu_s = _pad_amount(_money(env, line.price_unit, doc_currency), layout["w_pu"])
    tax_s = _clip(tax_txt, layout["w_tax"])
    sd_s = _pad_amount(_money(env, line.price_subtotal, doc_currency), layout["w_sd"])
    dcell = _pad_right(_clip(desc_cell, layout["w_desc"]), layout["w_desc"])
    if show_cc:
        sbs_s = _pad_amount(
            _money(env, line.subtotal_company_currency, comp_currency),
            layout["w_sbs"],
        )
        parts = [
            f"{str(item):<{layout['w_hash']}}",
            _pad_code(code, layout["w_code"]),
            dcell,
            _pad_right(tax_s, layout["w_tax"]),
            qty_s,
            pu_s,
            sbs_s,
            sd_s,
        ]
    else:
        parts = [
            f"{str(item):<{layout['w_hash']}}",
            _pad_code(code, layout["w_code"]),
            dcell,
            _pad_right(tax_s, layout["w_tax"]),
            qty_s,
            pu_s,
            sd_s,
        ]
    return " ".join(parts)


def _l10n_ve_max_product_table_lines(move):
    journal = move.journal_id
    if not journal or journal.type != "sale":
        return None
    section = move._l10n_ve_journal_fiscal_book_section()
    if section and section.book_id:
        mx = section.book_id.l10n_ve_max_invoice_lines
    elif journal.l10n_ve_emission_medium not in ("free", "fiscal_machine"):
        if not getattr(journal, "l10n_ve_limit_invoice_lines", False):
            return None
        mx = journal.l10n_ve_max_invoice_lines
    else:
        return None
    if mx is None or mx < 1:
        return None
    return int(mx)


def _l10n_ve_escp_invoice_margin_lines(move):
    journal = move.journal_id
    if not journal or journal.type != "sale":
        return _DEFAULT_ESC_P_MARGIN_LINES
    section = move._l10n_ve_journal_fiscal_book_section()
    if not section or not section.book_id:
        return _DEFAULT_ESC_P_MARGIN_LINES
    m = section.book_id.l10n_ve_escp_invoice_margin_lines
    if m is None or m < 0:
        return _DEFAULT_ESC_P_MARGIN_LINES
    return min(127, int(m))


def _product_desc_continuation_line(desc_chunk, layout, show_cc):
    w_h = layout["w_hash"]
    w_c = layout["w_code"]
    w_d = layout["w_desc"]
    w_t = layout["w_tax"]
    w_q = layout["w_qty"]
    w_p = layout["w_pu"]
    w_sd = layout["w_sd"]
    mid = _pad_right(_clip(desc_chunk, w_d), w_d)
    prefix = " " * w_h + " " + " " * w_c + " "
    if show_cc:
        w_sbs = layout["w_sbs"]
        suffix = (
            " "
            + " " * w_t
            + " "
            + " " * w_q
            + " "
            + " " * w_p
            + " "
            + " " * w_sbs
            + " "
            + " " * w_sd
        )
    else:
        suffix = " " + " " * w_t + " " + " " * w_q + " " + " " * w_p + " " + " " * w_sd
    row = prefix + mid + suffix
    return row[:LINE_WIDTH].ljust(LINE_WIDTH)


def _escp_start_bytes(move):
    buf = bytearray()
    buf += b"\x1b@"
    buf += _ESC_P_MATRIX_SLOWER
    buf += _ESC_P_DOUBLE_STRIKE_ON
    buf += b"\x1bt\x10"
    buf += b"\x1bC" + bytes([PAGE_LENGTH_LINES])
    buf += b"\x0f"
    buf += b"\n" * _l10n_ve_escp_invoice_margin_lines(move)
    buf += b"\x1bE\x01"
    buf += _enc(_center_line(_document_title(move), LINE_WIDTH)) + b"\n"
    buf += b"\x1bE\x00"
    buf += b"\n"
    return buf


def _header_left_stack(move, addr_wrap):
    partner = move.partner_id
    left_stack = []
    if move.l10n_ve_on_behalf_of_third_party and move.l10n_ve_third_party_partner_id:
        tp = move.l10n_ve_third_party_partner_id
        left_stack.append(f"FACT.POR TERCEROS: {tp.name}")
        left_stack.append(f"  RIF: {tp.vat or ''}")
    left_stack.append(f"RAZON SOCIAL: {partner.name or ''}")
    left_stack.append(f"RIF: {partner.vat or ''}")
    addr = (partner._display_address(without_company=True) or "").replace("\n", ", ")
    left_stack.extend(_wrap(f"DIRECCION: {addr}", addr_wrap))
    if move.ref:
        left_stack.append(f"REFERENCIA: {move.ref}")
    if move.invoice_payment_term_id.note:
        left_stack.extend(
            _wrap(f"TERMINOS DE PAGO: {move.invoice_payment_term_id.note}", addr_wrap)
        )
    return left_stack


def _header_center_stack(env, move, origin_affected, comp_currency):
    if not origin_affected:
        return []
    center_stack = [
        "DOCUMENTO AFECTADO",
        f"Factura: {origin_affected.name or ''}",
    ]
    if origin_affected.l10n_ve_invoice_date:
        center_stack.append(f"Fecha: {origin_affected.l10n_ve_invoice_date}")
    om = move.l10n_ve_origin_affected_total_company
    if om is not False:
        center_stack.append(f"Monto Orig.: {_money(env, om, comp_currency)}")
    else:
        amount = origin_affected.amount_total
        currency = origin_affected.currency_id
        center_stack.append(f"Monto Orig.: {_money(env, amount, currency)}")
    return center_stack


def _header_right_stack(move, currency):
    right_stack = [f"{_doc_number_label(move)} {move.name or ''}"]
    if move.l10n_ve_invoice_date:
        right_stack.append(f"Fecha: {move.l10n_ve_invoice_date}")
    if move.invoice_date_due:
        right_stack.append(f"Vencimiento: {move.invoice_date_due}")
    right_stack.append(f"Moneda: {currency.name or ''}")
    if move.company_id.taxpayer_type == "formal":
        right_stack.append("Contribuyente Formal")
    return right_stack


def _append_header_stacks(buf, stacks, origin_affected, lw):
    left_stack, center_stack, right_stack = stacks
    max_rows = max(len(left_stack), len(center_stack), len(right_stack))
    for i in range(max_rows):
        lv = left_stack[i] if i < len(left_stack) else ""
        cv = center_stack[i] if i < len(center_stack) else ""
        rv = right_stack[i] if i < len(right_stack) else ""
        if origin_affected:
            buf += _enc(_three_cols(lw, lv, cv, rv)) + b"\n"
        else:
            buf += _enc(_two_cols(lw, lv, rv)) + b"\n"


def _append_section_line(buf, line, lw):
    buf += b"\n"
    buf += b"\x1bE\x01"
    for ln in _wrap(line.name or "", lw):
        buf += _enc(_center_line(ln, lw)) + b"\n"
    buf += b"\x1bE\x00"
    buf += _enc("-" * lw) + b"\n"


def _append_product_line(
    buf, line, item, env, layout, currency, comp_currency, show_cc
):
    desc = line.l10n_ve_report_line_description()
    first_cell = desc[: layout["w_desc"]]
    buf += (
        _enc(
            _format_product_row(
                env, line, item, layout, currency, comp_currency, first_cell
            )
        )
        + b"\n"
    )
    tail = desc[layout["w_desc"] :].strip()
    while tail:
        chunk = tail[: layout["w_desc"]]
        tail = tail[layout["w_desc"] :].strip()
        buf += _enc(_product_desc_continuation_line(chunk, layout, show_cc)) + b"\n"


def _append_product_table(buf, move, env, layout, currency, comp_currency, show_cc, lw):
    buf += _enc(_product_header_line(move, layout)) + b"\n"
    buf += _enc("-" * lw) + b"\n"
    item = 0
    for line in move.l10n_ve_report_invoice_lines():
        if line.display_type == "line_section":
            _append_section_line(buf, line, lw)
        elif line.display_type == "line_note":
            for ln in _wrap(line.name or "", lw):
                buf += _enc(_pad_right(ln, lw)) + b"\n"
        elif line.display_type == "product":
            item += 1
            _append_product_line(
                buf, line, item, env, layout, currency, comp_currency, show_cc
            )
    max_product_slots = _l10n_ve_max_product_table_lines(move)
    if max_product_slots is not None:
        for _ in range(max(0, max_product_slots - item)):
            buf += _enc(" " * lw) + b"\n"


def _append_single_currency_footer(buf, move, env, lw):
    w1, w2, w3 = _footer_note_totals_widths_cn_bs(lw)
    seniat_lines = _seniat_left_column_lines(move, w1)
    total_rows, doc_cur, _comp_cur, _dual_cc = _totals_data_rows(env, move)
    n = max(len(seniat_lines), len(total_rows))
    for i in range(n):
        c1 = seniat_lines[i] if i < len(seniat_lines) else ""
        if i < len(total_rows):
            label, doc_amt, _comp_amt = total_rows[i]
            c2 = label
            c3 = _money(env, doc_amt, doc_cur)
        else:
            c2 = ""
            c3 = ""
        buf += _enc(_three_column_footer_line(c1, c2, c3, w1, w2, w3)) + b"\n"


def _append_dual_currency_footer(buf, move, env, lw):
    w1, w2, w3, w4 = _footer_note_totals_widths(lw)
    seniat_lines = _seniat_left_column_lines(move, w1)
    total_rows, doc_cur, comp_cur, _dual_cc = _totals_data_rows(env, move)
    n = max(len(seniat_lines), len(total_rows))
    for i in range(n):
        c1 = seniat_lines[i] if i < len(seniat_lines) else ""
        if i < len(total_rows):
            label, doc_amt, comp_amt = total_rows[i]
            c2 = label
            c3 = _money(env, doc_amt, doc_cur)
            c4 = _money(env, comp_amt, comp_cur) if comp_amt is not None else ""
        else:
            c2 = ""
            c3 = ""
            c4 = ""
        buf += _enc(_four_column_line(c1, c2, c3, c4, w1, w2, w3, w4)) + b"\n"


def _append_footer_totals(buf, move, env, lw):
    if _l10n_ve_escp_cn_nd_single_currency(move):
        _append_single_currency_footer(buf, move, env, lw)
    else:
        _append_dual_currency_footer(buf, move, env, lw)


def _append_amount_words_and_stamp(buf, move, lw):
    if move.company_id.display_invoice_amount_total_words and move.amount_total_words:
        buf += b"\n"
        for ln in _wrap(move.amount_total_words, lw):
            buf += _enc(_pad_right(_clip(ln, lw), lw)) + b"\n"
    buf += b"\n"
    if move.state == "cancel":
        buf += b"\x1bE\x01"
        buf += _enc(_center_line("ANULADA", lw)) + b"\n"
        buf += b"\x1bE\x00"
    elif move.l10n_ve_invoice_original_printed:
        buf += b"\x1bE\x01"
        buf += _enc(_center_line("Copia fiel su original", lw)) + b"\n"
        buf += b"\x1bE\x00"


def _escp_end_bytes(buf):
    buf += _ESC_P_DOUBLE_STRIKE_OFF
    buf += _ESC_P_MATRIX_SPEED_RESTORE
    buf += _ESC_P_FONT_RESTORE
    buf += b"\n\n"
    buf += b"\x12"
    buf += b"\x0c"


def build_move_escp_bytes(move):
    env = move.env
    currency = move.currency_id
    comp_currency = move.company_currency_id
    origin_affected = move.debit_origin_id or move.reversed_entry_id
    lw = LINE_WIDTH
    addr_wrap = int(lw * 0.72)
    show_cc = comp_currency != currency
    layout = _product_col_layout(lw, show_cc)
    buf = _escp_start_bytes(move)
    _append_header_stacks(
        buf,
        (
            _header_left_stack(move, addr_wrap),
            _header_center_stack(env, move, origin_affected, comp_currency),
            _header_right_stack(move, currency),
        ),
        origin_affected,
        lw,
    )
    buf += _enc("-" * lw) + b"\n"
    _append_product_table(buf, move, env, layout, currency, comp_currency, show_cc, lw)
    buf += _enc("-" * lw) + b"\n"
    _append_footer_totals(buf, move, env, lw)
    _append_amount_words_and_stamp(buf, move, lw)
    _escp_end_bytes(buf)
    return bytes(buf)
