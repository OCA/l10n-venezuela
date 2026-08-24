import logging
import re
import shutil
import unicodedata
from collections import defaultdict
from io import BytesIO

import requests
from lxml import html
from PIL import Image, ImageFilter, ImageOps

from .seniat_field_mapper import (
    enrich_from_key_values,
    extract_table_key_values,
    rif_from_seniat_text,
)

_logger = logging.getLogger(__name__)

BASE = "http://contribuyente.seniat.gob.ve/BuscaRif/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CAPTCHA_MISMATCH_MARKERS = (
    "no coincide con la imagen",
    "no coincide con la imagen.",
    "el codigo no coincide",
    "el código no coincide",
)
MAX_LOG_SNIPPET = 700


def _strip_accents_lower(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return stripped.lower()


def _snippet(text, limit=MAX_LOG_SNIPPET):
    if not text:
        return ""
    one = re.sub(r"\s+", " ", text).strip()
    if len(one) <= limit:
        return one
    return one[:limit] + "…"


def _clean_tesseract_line(raw):
    if not raw:
        return ""
    text = re.sub(r"[^0-9A-Za-z]", "", raw).strip()
    if not text:
        text = re.sub(r"\s+", "", raw)
    return text[:10]


CAPTCHA_LEN_MIN = 4
CAPTCHA_LEN_MAX = 10
MIN_WORD_CONFIDENCE_LINE = 28
POST_TRIES_PER_IMAGE = 5
MAX_TESSERACT_CALLS_VARIANTS = 22
QUERY_RIF_MAX_CAPTCHA_ROUNDS = 12


def _plausible_captcha_code(s):
    if not s:
        return False
    ln = len(s)
    if ln < CAPTCHA_LEN_MIN or ln > CAPTCHA_LEN_MAX:
        return False
    if re.search(r"(.)\1{3,}", s):
        return False
    if ln >= 7 and len(set(s.lower())) / ln < 0.45:
        return False
    return True


def _line_concat_from_tesseract_data(data):
    n = len(data.get("text") or [])
    groups = defaultdict(list)
    for i in range(n):
        raw_t = (data["text"][i] or "").strip()
        if not raw_t:
            continue
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            continue
        if conf < MIN_WORD_CONFIDENCE_LINE:
            continue
        try:
            line_key = (
                int(data["page_num"][i]),
                int(data["block_num"][i]),
                int(data["par_num"][i]),
                int(data["line_num"][i]),
            )
            left = int(data["left"][i])
        except (KeyError, IndexError, ValueError, TypeError):
            continue
        groups[line_key].append((left, raw_t, conf))
    rows = []
    for parts in groups.values():
        parts.sort(key=lambda x: x[0])
        glued = "".join(p[1] for p in parts)
        cleaned = _clean_tesseract_line(glued)
        if len(cleaned) < CAPTCHA_LEN_MIN:
            continue
        min_c = min(p[2] for p in parts)
        avg_c = sum(p[2] for p in parts) / len(parts)
        if min_c < 18:
            continue
        score = avg_c * 0.62 + min_c * 0.38
        rows.append((score, min_c, avg_c, cleaned))
    rows.sort(key=lambda x: -x[0])
    return rows


def _confidence_scored_reads(image_bytes):
    import pytesseract
    from pytesseract import Output

    whitelist = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    variants = dict(_iter_captcha_variants(image_bytes))
    preferred_order = (
        "autocontrast_x5",
        "rgb_L_x5",
        "legacy_soft",
        "autocontrast_g4_x2",
        "thresh110",
        "blur12_thresh125",
        "thresh140",
    )
    scored = []
    for tag in preferred_order:
        proc = variants.get(tag)
        if proc is None:
            continue
        for psm in (7, 8):
            cfg = f"--oem 3 --psm {psm} " f"-c tessedit_char_whitelist={whitelist}"
            try:
                data = pytesseract.image_to_data(
                    proc, config=cfg, output_type=Output.DICT
                )
            except Exception:
                continue
            for score, _min_c, _avg_c, cleaned in _line_concat_from_tesseract_data(
                data
            ):
                if not _plausible_captcha_code(cleaned):
                    continue
                scored.append((score, cleaned, tag, psm))
            try:
                raw = pytesseract.image_to_string(proc, config=cfg) or ""
            except Exception:
                raw = ""
            whole = _clean_tesseract_line(raw)
            if _plausible_captcha_code(whole):
                scored.append((69.0, whole, tag, f"string_psm{psm}"))
    by_txt = {}
    for row in scored:
        sc, txt, tg, pm = row
        if txt not in by_txt or sc > by_txt[txt][0]:
            by_txt[txt] = row
    return sorted(by_txt.values(), key=lambda x: -x[0])


def _merge_confidence_and_strings(confidence_rows, string_candidates):
    best_by_text = {}
    for conf, text, tag, psm in confidence_rows:
        text = text.strip()
        if text not in best_by_text or conf > best_by_text[text][0]:
            best_by_text[text] = (float(conf), tag, psm)
    ordered_by_conf = sorted(
        best_by_text.keys(),
        key=lambda t: (
            -best_by_text[t][0],
            -min(abs(len(t) - 6), 5),
        ),
    )
    seen = set(ordered_by_conf)
    rest = [
        s for s in string_candidates if s not in seen and _plausible_captcha_code(s)
    ]
    rest.sort(key=lambda s: (-min(abs(len(s) - 6), 6), -len(s)))
    merged = ordered_by_conf + rest
    uniq = []
    for s in merged:
        if s not in uniq:
            uniq.append(s)
    return uniq, best_by_text


def _gray_mean(im_rgb):
    g = im_rgb.convert("L")
    pixels = list(g.getdata())
    if not pixels:
        return 128.0
    return sum(pixels) / len(pixels)


def _iter_captcha_variants(image_bytes):
    im = Image.open(BytesIO(image_bytes)).convert("RGB")
    g4 = _scale_gray(im, 4)
    yield "rgb_L_x5", _scale_gray(im, 5)
    yield "autocontrast_x5", ImageOps.autocontrast(_scale_gray(im, 5))
    yield (
        "autocontrast_g4_x2",
        ImageOps.autocontrast(g4).resize(
            (g4.size[0] * 2, g4.size[1] * 2),
            Image.Resampling.LANCZOS,
        ),
    )
    yield "thresh110", g4.point(lambda p: 255 if p > 110 else 0)
    yield "thresh140", g4.point(lambda p: 255 if p > 140 else 0)
    mean = _gray_mean(im)
    if mean < 130:
        yield "invert_autocontrast_x5", ImageOps.invert(_scale_gray(im, 5))
        yield (
            "invert_autocontrast_x5_ops",
            ImageOps.autocontrast(ImageOps.invert(_scale_gray(im, 5))),
        )
    mild = g4.filter(ImageFilter.GaussianBlur(radius=1.2))
    yield "blur12_thresh125", mild.point(lambda p: 255 if p > 125 else 0)
    yield "legacy_soft", _preprocess_captcha_soft(image_bytes)


def _scale_gray(im_rgb, factor):
    g = im_rgb.convert("L")
    w, h = g.size
    return g.resize((w * factor, h * factor), Image.Resampling.LANCZOS)


def _preprocess_captcha_soft(image_bytes):
    im = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = im.size
    tam = 4
    im = im.resize((w * tam, h * tam), Image.Resampling.LANCZOS)
    gray = im.convert("L")
    gray = gray.point(lambda p: 255 if p > 118 else 0)
    gray = gray.filter(ImageFilter.GaussianBlur(radius=1.8))
    gray = gray.point(lambda p: 255 if p > 120 else 0)
    gw, gh = gray.size
    per = 1.25
    canvas = Image.new("L", (int(gw * per), int(gh * per)), 255)
    x = max(0, int((gw * per - gw) / 2))
    y = max(0, int((gh * per - gh) / 2))
    canvas.paste(gray, (x, y))
    return canvas.resize((320, 96), Image.Resampling.LANCZOS)


def _raw_repr(raw):
    r = repr(raw)
    return r[:160] + ("…" if len(r) > 160 else "")


def _collect_ocr_candidates(image_bytes):
    import pytesseract

    _require_tesseract()
    whitelist = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    candidates = []
    seen = set()
    calls = 0

    for tag, proc in _iter_captcha_variants(image_bytes):
        for psm in (7, 8):
            for use_wl in (True, False):
                if calls >= MAX_TESSERACT_CALLS_VARIANTS or len(seen) >= 10:
                    return candidates
                cfg = f"--oem 3 --psm {psm}"
                if use_wl:
                    cfg += f" -c tessedit_char_whitelist={whitelist}"
                calls += 1
                try:
                    raw = pytesseract.image_to_string(proc, config=cfg) or ""
                except Exception as exc:
                    _logger.debug(
                        "l10n_ve_vat_seniat OCR skip tag=%s psm=%s wl=%s: %s",
                        tag,
                        psm,
                        use_wl,
                        exc,
                    )
                    continue
                cleaned = _clean_tesseract_line(raw)
                if len(cleaned) < CAPTCHA_LEN_MIN:
                    continue
                if not _plausible_captcha_code(cleaned):
                    continue
                if cleaned not in seen:
                    seen.add(cleaned)
                    candidates.append(cleaned)
                    _logger.debug(
                        "l10n_ve_vat_seniat OCR hit tag=%s psm=%s wl=%s raw=%s -> %r",
                        tag,
                        psm,
                        use_wl,
                        _raw_repr(raw),
                        cleaned,
                    )
    return candidates


def _ocr_ranked_codes(image_bytes):
    _require_tesseract()
    conf_rows = _confidence_scored_reads(image_bytes)
    max_conf = max((row[0] for row in conf_rows), default=0)
    long_ok = any(len(row[1]) >= 5 and row[0] >= 68 for row in conf_rows)
    if max_conf >= 78 and long_ok:
        string_fallback = []
    else:
        string_fallback = _collect_ocr_candidates(image_bytes)
    merged, conf_map = _merge_confidence_and_strings(conf_rows, string_fallback)
    if not merged:
        merged_fb = [
            s for s in _collect_ocr_candidates_fallback_loose(image_bytes) if s
        ]
        merged = merged_fb
        conf_map = {}
    top_dbg = []
    for t in merged[:5]:
        if t in conf_map:
            top_dbg.append(f"{t}({conf_map[t][0]}%)")
        else:
            top_dbg.append(t)
    _logger.info(
        "l10n_ve_vat_seniat OCR orden=%s "
        "(linea completa concatenada; max %s POST/imagen) len_bytes=%s",
        top_dbg,
        POST_TRIES_PER_IMAGE,
        len(image_bytes),
    )
    return merged


def _collect_ocr_candidates_fallback_loose(image_bytes):
    import pytesseract

    whitelist = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    seen = set()
    calls = 0
    for _tag, proc in _iter_captcha_variants(image_bytes):
        for psm in (7, 13):
            if calls >= 14 or len(seen) >= 6:
                return out
            cfg = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}"
            calls += 1
            try:
                raw = pytesseract.image_to_string(proc, config=cfg) or ""
            except Exception:
                continue
            cleaned = _clean_tesseract_line(raw)
            if len(cleaned) < 3:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                out.append(cleaned)
    return out


def _require_tesseract():
    if not shutil.which("tesseract"):
        raise RuntimeError(
            "No se encontró el binario `tesseract` en el PATH. "
            "Instale Tesseract OCR en el servidor "
            "(por ejemplo: apt install tesseract-ocr)."
        )


def _decode_response(content):
    for enc in ("cp1252", "latin-1", "utf-8"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _table_texts(tree):
    rows = []
    for tbl in tree.xpath("//table"):
        txt = " ".join(tbl.xpath(".//text()"))
        txt = re.sub(r"\s+", " ", txt).strip()
        rows.append(txt)
    return rows


def _html_plain_compact(tree):
    return re.sub(r"\s+", " ", " ".join(tree.xpath("//text()"))).strip()


def _regex_label_value(plain, label_pattern):
    m = re.search(label_pattern, plain, re.I)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _parse_buscarif_identity(head, third, plain):
    registro = "ACTIVO"
    if "REGISTRO VENCIDO" in head.upper():
        registro = "VENCIDO"
        head = head.replace("REGISTRO VENCIDO", "")
        head = re.sub(r"\s+", " ", head).strip()

    rif_token = rif_from_seniat_text(head, third, plain)
    if not rif_token and head:
        head_token = head.split(" ", 1)[0].strip()
        head_token = re.sub(r"[^JGPVE0-9]", "", head_token, flags=re.I)
        if re.match(r"^[JGPVE]\d{9}$", head_token, re.I):
            rif_token = head_token.upper()

    nombre_full = head
    if rif_token:
        nombre_full = re.sub(re.escape(rif_token), "", nombre_full, count=1, flags=re.I)
    nombre_full = re.sub(r"^[\s_\-]+", "", nombre_full)

    siglas = ""
    match = re.search(r"\(([^)]*)\)", head)
    if match:
        siglas = f"({match.group(1).strip()})"
        nombre_full = re.sub(r"\([^)]*\)", "", nombre_full, count=1)
        nombre_full = re.sub(r"\s+", " ", nombre_full).strip()
    return registro, rif_token, nombre_full, siglas


def _parse_buscarif_activity_parts(parts):
    actividad = ""
    condicion = ""
    retencion = ""
    if len(parts) > 2:
        actividad = re.sub(
            r"Condici[oó]n",
            "",
            parts[1],
            flags=re.IGNORECASE,
        ).strip()
        condicion = parts[2].replace("?", "ó").strip()
    if len(parts) > 3:
        retencion = ":".join(parts[3:]).strip()
    return actividad, condicion, retencion


def _fill_buscarif_missing_labels(parsed, plain):
    if not parsed.get("seniat_tipo_contribuyente_label"):
        value = _regex_label_value(
            plain,
            r"Tipo\s+de\s+Contribuyente\s*:?\s*([^.;\n|]+?)"
            r"(?=\s+Tipo\s+de\s+Persona|\s+%|\Z)",
        )
        if value:
            parsed["seniat_tipo_contribuyente_label"] = value
    if not parsed.get("seniat_tipo_persona_label"):
        value = _regex_label_value(
            plain,
            r"Tipo\s+de\s+Persona\s*:?\s*([^.;\n|]+?)"
            r"(?=\s+Tipo\s+de\s+Contribuyente|\s+%|\Z)",
        )
        if value:
            parsed["seniat_tipo_persona_label"] = value
    if not parsed.get("seniat_retencion_pct_label"):
        value = _regex_label_value(
            plain,
            r"(?:%|\s)de\s+Retenci[oó]n\s*:?\s*([^.;\n|]+)",
        )
        if not value:
            value = _regex_label_value(
                plain,
                r"Retenci[oó]n\s*(?:IVA)?\s*:?\s*" r"([^.;\n|]*?\d+\s*%[^.;|\n]*)",
            )
        if value:
            parsed["seniat_retencion_pct_label"] = value
    return parsed


def parse_buscarif_page(html_text):
    tree = html.fromstring(html_text)
    texts = _table_texts(tree)
    if len(texts) < 2:
        return {"ok": False, "reason": "unexpected_html", "tables": texts}

    second = texts[1]
    low = second.lower()
    fold = _strip_accents_lower(second)
    if any(m in low for m in CAPTCHA_MISMATCH_MARKERS) or (
        "no coincide" in fold and "imagen" in fold
    ):
        return {"ok": False, "reason": "captcha", "detail": second}

    if "no existe el contribuyente" in low:
        return {"ok": True, "contribuyente": False, "raw_head": second}

    third = texts[2] if len(texts) > 2 else ""
    parts = [p.strip() for p in third.split(":")] if third else []
    plain = _html_plain_compact(tree)
    registro, rif_token, nombre_full, siglas = _parse_buscarif_identity(
        second, third, plain
    )
    actividad, condicion, retencion = _parse_buscarif_activity_parts(parts)
    parsed = {
        "ok": True,
        "contribuyente": True,
        "registro": registro,
        "rif": rif_token,
        "nombre": nombre_full,
        "siglas": siglas,
        "actividad_economica": actividad,
        "condicion": condicion,
        "retencion": retencion,
        "raw_table3": third,
    }
    parsed = enrich_from_key_values(parsed, extract_table_key_values(tree))
    parsed = _fill_buscarif_missing_labels(parsed, plain)
    _logger.info(
        "l10n_ve_vat_seniat parse etiquetas tipo_contrib=%r "
        "tipo_persona=%r retencion_txt=%r kv_keys=%s",
        parsed.get("seniat_tipo_contribuyente_label"),
        parsed.get("seniat_tipo_persona_label"),
        parsed.get("seniat_retencion_pct_label"),
        list((parsed.get("seniat_table_kv") or {}).keys()),
    )
    return parsed


def query_rif(rif, max_attempts=QUERY_RIF_MAX_CAPTCHA_ROUNDS, timeout=(15, 90)):
    rif = (rif or "").strip().upper().replace("-", "").replace(" ", "")
    if not rif:
        raise ValueError("RIF vacío")
    tess_bin = shutil.which("tesseract")
    _logger.info(
        "l10n_ve_vat_seniat inicio rif=%s intentos_max=%s timeout=%s tesseract=%s",
        rif,
        max_attempts,
        timeout,
        tess_bin,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    last_detail = ""
    codes_tried = []
    for attempt in range(max_attempts):
        try:
            cap = session.get(f"{BASE}Captcha.jpg", timeout=timeout)
        except requests.RequestException as exc:
            _logger.warning(
                "l10n_ve_vat_seniat intento %s GET Captcha.jpg falló: %s",
                attempt + 1,
                exc,
            )
            raise
        _logger.info(
            "l10n_ve_vat_seniat intento %s/%s GET Captcha.jpg "
            "status=%s bytes=%s cookies=%s",
            attempt + 1,
            max_attempts,
            cap.status_code,
            len(cap.content or b""),
            list(session.cookies.keys()),
        )
        cap.raise_for_status()
        try:
            ranked_codes = _ocr_ranked_codes(cap.content)
        except Exception:
            _logger.exception(
                "l10n_ve_vat_seniat intento %s error en Tesseract/pytesseract",
                attempt + 1,
            )
            raise
        if not ranked_codes:
            last_detail = "ocr_vacio"
            codes_tried.append("")
            _logger.warning(
                "l10n_ve_vat_seniat intento %s OCR sin ningun candidato "
                "(revisar imagen/tesseract)",
                attempt + 1,
            )
            continue

        captcha_still_wrong = False
        for sub_i, codigo in enumerate(ranked_codes[:POST_TRIES_PER_IMAGE]):
            codes_tried.append(codigo)
            try:
                post = session.post(
                    f"{BASE}BuscaRif.jsp",
                    data={
                        "p_rif": rif,
                        "p_cedula": "",
                        "codigo": codigo,
                        "busca": " Buscar ",
                    },
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                _logger.warning(
                    "l10n_ve_vat_seniat intento %s POST BuscaRif.jsp falló: %s",
                    attempt + 1,
                    exc,
                )
                raise
            _logger.info(
                "l10n_ve_vat_seniat intento %s.%s POST BuscaRif.jsp status=%s bytes=%s "
                "codigo_enviado=%r",
                attempt + 1,
                sub_i + 1,
                post.status_code,
                len(post.content or b""),
                codigo,
            )
            post.raise_for_status()
            html_text = _decode_response(post.content)
            parsed = parse_buscarif_page(html_text)
            if parsed.get("reason") == "captcha":
                last_detail = parsed.get("detail", "")
                captcha_still_wrong = True
                _logger.info(
                    "l10n_ve_vat_seniat intento %s.%s captcha rechazado "
                    "codigo=%r tabla2=%r",
                    attempt + 1,
                    sub_i + 1,
                    codigo,
                    _snippet(last_detail),
                )
                continue
            if not parsed.get("ok"):
                _logger.warning(
                    "l10n_ve_vat_seniat intento %s.%s parse no ok "
                    "reason=%s tables=%s html_snippet=%r",
                    attempt + 1,
                    sub_i + 1,
                    parsed.get("reason"),
                    parsed.get("tables"),
                    _snippet(html_text),
                )
                return parsed
            _logger.info(
                "l10n_ve_vat_seniat intento %s.%s consulta parseada ok "
                "contribuyente=%s",
                attempt + 1,
                sub_i + 1,
                parsed.get("contribuyente"),
            )
            return parsed

        if captcha_still_wrong:
            continue

    _logger.warning(
        "l10n_ve_vat_seniat agotados los intentos rif=%s último_detalle=%r "
        "códigos_intentados=%s",
        rif,
        _snippet(last_detail),
        codes_tried,
    )
    return {
        "ok": False,
        "reason": "captcha_exhausted",
        "detail": last_detail,
        "attempts": max_attempts,
        "codes_tried": codes_tried,
    }
