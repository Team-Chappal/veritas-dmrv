"""
S5.6 — the project report: statutory dossier, PDF URL, and a scannable QR.

The QR exists for a specific reason worth stating. A field officer standing in
a mangrove stand with no signal cannot open a URL, and an auditor filing EUDR
evidence needs something that survives being printed and left in a folder. A QR
pointing at the immutable provenance endpoint is the bridge between the paper
dossier and the live evidence chain.

Because a QR that silently encodes the wrong URL is worse than no QR at all —
it sends an auditor to a 404 and looks like tampering — every QR this module
produces is verified by an INDEPENDENT decoder in the test suite
(``cv2.QRCodeDetector``), not by reading back the string that went in.
"""

from __future__ import annotations

import base64
import hashlib
import io
import urllib.parse

import numpy as np
import segno

from core.cloudinary_client import build_audit_pdf_url

#: 'M' recovers ~15% of a symbol. Enough for a printed, scuffed, damp label,
#: without inflating the module count so much the code will not scan at the
#: physical size a sticker actually is.
QR_ERROR_CORRECTION = "m"

#: Quiet zone in modules. The QR spec requires 4; below that many scanners fail.
QR_QUIET_ZONE = 4

#: Pixels per module when rasterising for the data-URI preview.
QR_MODULE_PIXELS = 6


class ReportError(Exception):
    """Report could not be built. Callers map this to an HTTP status."""


def report_payload_url(app_url: str, project_id: str) -> str:
    """The URL a QR encodes: the immutable provenance record, not a PDF.

    Deliberately not the PDF URL. A PDF is regenerated and its bytes can change
    with a template edit; the provenance record is content-addressed, so a code
    printed onto a physical parcel marker keeps pointing at the same evidence
    even after the report layout is revised.
    """
    if not project_id or not project_id.strip():
        raise ReportError("project_id is required to build a report QR")
    # safe="" is load-bearing: quote() leaves "/" alone by default, so an id
    # containing a slash would silently address a DIFFERENT asset's record --
    # a QR on a physical marker pointing at someone else's evidence.
    quoted = urllib.parse.quote(project_id, safe="")
    return f"{app_url.rstrip('/')}/api/v1/assets/{quoted}/provenance"


def build_qr(payload: str, *, error: str = QR_ERROR_CORRECTION) -> segno.QRCode:
    """Encode ``payload``. Separated so tests can reach the raw symbol.

    ``boost_error=False`` pins the requested level. segno boosts by default,
    which is a sensible default and the wrong one here: boosting is
    payload-dependent, so the same request yields a different symbol depending on
    how long the URL is. A QR printed onto a physical parcel marker should be the
    level that was chosen for it, at the module count that was sized for it.
    """
    if not payload:
        raise ReportError("QR payload is empty")
    return segno.make(payload, error=error, boost_error=False)


def qr_matrix(
    payload: str,
    *,
    module_pixels: int = QR_MODULE_PIXELS,
    quiet_zone: int = QR_QUIET_ZONE,
) -> np.ndarray:
    """Rasterise the QR to a 0/255 uint8 image, scale and quiet zone included.

    Returns the pixels a caller needs to write a PNG. Kept here rather than in a
    route so the test suite can hand the same array to a decoder.
    """
    if module_pixels < 1:
        raise ReportError("module_pixels must be >= 1")
    qr = build_qr(payload)
    # segno yields booleans where True is a dark module.
    modules = np.array(
        [[0 if cell else 255 for cell in row] for row in qr.matrix], dtype=np.uint8
    )
    scaled = np.kron(modules, np.ones((module_pixels, module_pixels), dtype=np.uint8))
    pad = quiet_zone * module_pixels
    return np.pad(scaled, pad, mode="constant", constant_values=255)


def qr_data_uri(payload: str, **kwargs) -> str:
    """A self-contained ``data:image/png;base64,...`` for inline embedding.

    Self-contained matters because the report may be rendered into a PDF or an
    emailed attachment where an external image reference resolves to nothing.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a hard dep
        raise ReportError("Pillow is required to rasterise the QR") from exc

    matrix = qr_matrix(payload, **kwargs)
    buf = io.BytesIO()
    Image.fromarray(matrix, mode="L").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def qr_svg(payload: str, *, error: str = QR_ERROR_CORRECTION, scale: int = 4) -> str:
    """Vector QR for print — a rasterised code goes soft at print resolution."""
    buf = io.BytesIO()
    build_qr(payload, error=error).save(
        buf, kind="svg", scale=scale, border=QR_QUIET_ZONE, dark="#000000", light="#ffffff"
    )
    return buf.getvalue().decode("utf-8")


def content_address(project_id: str, payload: str) -> str:
    """Stable id for a report body, so two builds of one report match."""
    digest = hashlib.sha256(f"{project_id}|{payload}".encode("utf-8")).hexdigest()
    return f"rpt_{digest[:16]}"


def build_report(
    *,
    project_id: str,
    project_name: str,
    region: str,
    net_tco2e_per_ha: float,
    sampling_ci90_pct: float,
    root_hash: str,
    cloud_name: str,
    app_url: str,
    warped_public_id: str,
    module_pixels: int = QR_MODULE_PIXELS,
) -> dict:
    """Assemble the report: PDF URL, scannable QR, and the numbers behind both.

    Every figure in the PDF URL is also returned as data, because a PDF
    composite is opaque: if the URL and the JSON disagree, nothing downstream
    can tell which one the auditor actually read.
    """
    if not project_id.strip():
        raise ReportError("project_id is required")
    if net_tco2e_per_ha is None:
        raise ReportError("net_tco2e_per_ha is required")

    payload = report_payload_url(app_url, project_id)
    pdf_url = build_audit_pdf_url(
        cloud_name=cloud_name,
        warped_public_id=warped_public_id,
        project_id=project_id,
        region=region,
        tco2e_per_ha=net_tco2e_per_ha,
        sampling_ci90=sampling_ci90_pct,
        root_hash=root_hash,
    )

    return {
        "project_id": project_id,
        "project_name": project_name,
        "region": region,
        "report_id": content_address(project_id, pdf_url),
        "figures": {
            "net_certified_tco2e_per_ha": net_tco2e_per_ha,
            "sampling_ci90_pct": sampling_ci90_pct,
            "root_hash": root_hash,
        },
        "pdf_url": pdf_url,
        "qr": {
            "payload": payload,
            "error_correction": QR_ERROR_CORRECTION,
            "quiet_zone_modules": QR_QUIET_ZONE,
            "png_data_uri": qr_data_uri(payload, module_pixels=module_pixels),
            "note": "Encodes the provenance record, not the PDF: that URL is content-addressed.",
        },
    }
