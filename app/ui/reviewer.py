"""SasineSense AI reviewer workspace.

The interface is intentionally evidence-first: extraction results are presented
as reviewable candidates, never as authoritative legal conclusions.
"""

from __future__ import annotations

import html
import os
from typing import Any

import requests
import streamlit as st

API = os.getenv("REVIEWER_API_URL", "http://localhost:8000").rstrip("/")
FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "tif", "tiff"]

st.set_page_config(
    page_title="SasineSense AI · Reviewer",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

        :root { --ink:#102a43; --muted:#6d8498; --line:#dce8ef; --mint:#17a887; --blue:#397ac4; --amber:#d68b18; --purple:#7d55b5; }
        .stApp { background: #f5f8fb; color: var(--ink); }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] { background: #102a43; border-right: 0; }
        [data-testid="stSidebar"] * { color: #dceaf4 !important; }
        [data-testid="stSidebar"] .stCaption { color: #9db7ca !important; }
        .block-container { max-width: 1500px; padding: 2.2rem 3.5rem 4rem; }
        h1,h2,h3,h4,p,div,span,button,label { font-family: 'Manrope', sans-serif; }
        h1 { letter-spacing:-.04em; color:var(--ink); }
        .mono { font-family:'DM Mono', monospace; }
        .brand { display:flex; align-items:center; gap:14px; margin-bottom:2.5rem; }
        .brand-mark { width:46px; height:46px; border-radius:14px; display:grid; place-items:center; background:linear-gradient(135deg,#55d6be,#397ac4); color:white; font-size:25px; box-shadow:0 10px 24px rgba(57,122,196,.23); }
        .brand-name { font-size:20px; font-weight:800; letter-spacing:-.03em; color:#f4fbff; }
        .brand-sub { font-size:11px; color:#9db7ca; letter-spacing:.08em; text-transform:uppercase; }
        .side-section { margin: 1.8rem 0 .65rem; color:#75d9c4 !important; font-size:10px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
        .hero { background:linear-gradient(120deg,#102a43 0%,#173d59 65%,#1c5362 100%); border-radius:24px; padding:32px 36px; color:white; box-shadow:0 18px 50px rgba(16,42,67,.14); position:relative; overflow:hidden; }
        .hero:after { content:''; position:absolute; width:280px; height:280px; right:-70px; top:-140px; border:1px solid rgba(117,217,196,.35); border-radius:50%; box-shadow:0 0 0 26px rgba(117,217,196,.06),0 0 0 52px rgba(117,217,196,.04); }
        .eyebrow { color:#75d9c4; text-transform:uppercase; letter-spacing:.16em; font-size:11px; font-weight:800; margin-bottom:10px; }
        .hero-title { font-size:34px; line-height:1.08; letter-spacing:-.05em; font-weight:800; max-width:700px; }
        .hero-copy { color:#bed3e2; font-size:15px; line-height:1.65; max-width:700px; margin-top:12px; }
        .notice { display:flex; align-items:center; gap:9px; margin-top:20px; color:#d7eee8; font-size:12px; }
        .dot { width:8px; height:8px; background:#55d6be; border-radius:50%; box-shadow:0 0 0 5px rgba(85,214,190,.14); }
        .section-title { font-size:18px; font-weight:800; letter-spacing:-.03em; margin:25px 0 12px; }
        .upload-card { background:#fff; border:1px solid var(--line); border-radius:18px; padding:14px; box-shadow:0 8px 25px rgba(16,42,67,.05); }
        [data-testid="stFileUploader"] { background:linear-gradient(180deg,#fbfdff,#f5fafc); border:1px dashed #9fc4d5; border-radius:14px; padding:8px; }
        [data-testid="stFileUploaderDropzoneInstructions"] svg { color:var(--mint); }
        .stat-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 20px; min-height:112px; box-shadow:0 8px 25px rgba(16,42,67,.04); }
        .stat-label { color:var(--muted); font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
        .stat-value { color:var(--ink); font-size:28px; font-weight:800; letter-spacing:-.05em; margin-top:8px; }
        .stat-note { color:var(--muted); font-size:12px; margin-top:4px; }
        .status { display:inline-flex; align-items:center; gap:7px; padding:6px 10px; border-radius:999px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
        .status-review { background:#fff3da; color:#9a6209; }
        .status-ok { background:#def7ef; color:#147a65; }
        .status-unknown { background:#eef1f5; color:#5c6d7c; }
        .field-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 20px; margin:10px 0; box-shadow:0 7px 22px rgba(16,42,67,.035); }
        .field-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
        .field-name { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
        .field-value { color:var(--ink); font-size:19px; font-weight:800; letter-spacing:-.03em; margin-top:6px; }
        .field-meta { color:var(--muted); font-size:12px; margin-top:7px; }
        .confidence { color:#167c68; font-size:12px; font-weight:800; white-space:nowrap; }
        .evidence { background:#f0faf7; border-left:3px solid #55d6be; border-radius:0 8px 8px 0; padding:10px 12px; color:#315b5b; font-size:12px; line-height:1.5; margin-top:13px; }
        .evidence-label { color:#198a73; font-size:10px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; margin-bottom:3px; }
        .empty-state { text-align:center; padding:58px 30px; background:#fff; border:1px dashed #bed1dc; border-radius:18px; color:var(--muted); }
        .empty-icon { font-size:34px; color:var(--mint); margin-bottom:10px; }
        .small-note { color:var(--muted); font-size:12px; line-height:1.5; }
        .footer-note { color:#8ba0b1; text-align:center; font-size:11px; margin-top:40px; }
        .stButton > button { border-radius:10px; font-weight:700; border:1px solid #c7dbe5; }
        .stButton > button[kind="primary"] { background:#167c68; border-color:#167c68; }
        div[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_request(method: str, url: str, **kwargs) -> requests.Response | None:
    try:
        response = requests.request(method, url, **kwargs)
        return response
    except requests.RequestException as exc:
        st.error(f"Could not reach the API at `{API}`. Start FastAPI and try again.\n\n{exc}")
        return None


def _status_chip(result: dict[str, Any]) -> str:
    if result.get("document_type") == "unknown":
        return '<span class="status status-unknown">● Needs classification</span>'
    if result.get("review_required"):
        return '<span class="status status-review">● Review required</span>'
    return '<span class="status status-ok">● Ready for review</span>'


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _evidence_html(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return ""
    snippets = []
    for span in evidence[:3]:
        text = html.escape(str(span.get("text", "")))
        page = html.escape(str(span.get("page", "?")))
        snippets.append(f'<div class="evidence"><div class="evidence-label">Evidence · page {page}</div>“{text}”</div>')
    return "".join(snippets)


def _post_review(document_id: str, field: str, action: str, previous=None, new=None, note=None):
    payload = {"document_id": document_id, "field": field, "action": action,
               "previous_value": previous, "new_value": new, "note": note}
    response = _safe_request("POST", f"{API}/documents/{document_id}/reviews", json=payload, timeout=30)
    if response is not None and response.ok:
        st.success(f"Recorded {action.replace('_', ' ')} for {field}.")
    elif response is not None:
        st.error(response.text)


def _field_reviewer(document_id: str, field_name: str, current_value: Any) -> None:
    with st.expander(f"Review candidate · {field_name.replace('_', ' ')}"):
        new_value = st.text_input("Edited value", value=str(current_value or ""), key=f"edit_{field_name}")
        note = st.text_input("Reviewer note", key=f"note_{field_name}")
        cols = st.columns(4)
        if cols[0].button("Accept", key=f"acc_{field_name}"):
            _post_review(document_id, field_name, "accept", current_value, current_value, note)
        if cols[1].button("Edit", key=f"ed_{field_name}"):
            _post_review(document_id, field_name, "edit", current_value, new_value, note)
        if cols[2].button("Flag", key=f"fl_{field_name}"):
            _post_review(document_id, field_name, "flag", current_value, None, note)
        if cols[3].button("Unresolved", key=f"un_{field_name}"):
            _post_review(document_id, field_name, "mark_unresolved", current_value, None, note)


def _render_field(document_id: str, field: dict[str, Any], field_key: str, label: str | None = None) -> None:
    value = field.get("value")
    if value is None:
        return
    confidence = _confidence(field.get("confidence"))
    method = html.escape(str(field.get("method", "unknown")))
    title = html.escape(label or field.get("name", field_key).replace("_", " "))
    value_text = html.escape(str(value))
    st.markdown(
        f'<div class="field-card"><div class="field-head"><div><div class="field-name">{title}</div>'
        f'<div class="field-value">{value_text}</div></div><div class="confidence">{confidence:.0%}</div></div>'
        f'<div class="field-meta">Method: <span class="mono">{method}</span> · '
        f'normalized: {html.escape(str(field.get("normalized_value") or "—"))}</div>'
        f'{_evidence_html(field.get("evidence", []))}</div>',
        unsafe_allow_html=True,
    )
    _field_reviewer(document_id, field_key, value)


def _render_party(document_id: str, party: dict[str, Any], index: int) -> None:
    confidence = _confidence(party.get("confidence"))
    st.markdown(
        f'<div class="field-card"><div class="field-head"><div><div class="field-name">{html.escape(str(party.get("role", "party")))}</div>'
        f'<div class="field-value">{html.escape(str(party.get("name", "Unknown")))}</div></div>'
        f'<div class="confidence">{confidence:.0%}</div></div>{_evidence_html(party.get("evidence", []))}</div>',
        unsafe_allow_html=True,
    )
    _field_reviewer(document_id, f"party_{index}", party.get("name"))


def _render_place(document_id: str, place: dict[str, Any], index: int) -> None:
    name = html.escape(str(place.get("name", "Unknown")))
    area = html.escape(str(place.get("admin_area") or "Unresolved place"))
    confidence = _confidence(place.get("confidence"))
    st.markdown(
        f'<div class="field-card"><div class="field-head"><div><div class="field-name">Place candidate</div>'
        f'<div class="field-value">{name}</div><div class="field-meta">{area}</div></div>'
        f'<div class="confidence">{confidence:.0%}</div></div>{_evidence_html(place.get("evidence", []))}</div>',
        unsafe_allow_html=True,
    )
    _field_reviewer(document_id, f"place_{index}", place.get("name"))


def _render_sidebar() -> None:
    st.sidebar.markdown('<div class="brand"><div class="brand-mark">◈</div><div><div class="brand-name">SasineSense AI</div><div class="brand-sub">Evidence workspace</div></div></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="side-section">Workspace</div>', unsafe_allow_html=True)
    st.sidebar.markdown("**Reviewer mode**")
    st.sidebar.caption("Evidence-first extraction with human sign-off.")
    st.sidebar.markdown('<div class="side-section">Pipeline</div>', unsafe_allow_html=True)
    st.sidebar.markdown("`OCR`  →  `Rules`  →  `NER`  →  `Validation`")
    st.sidebar.caption(f"API endpoint\n{API}")
    st.sidebar.markdown('<div class="side-section">Safety</div>', unsafe_allow_html=True)
    st.sidebar.caption("Outputs are non-authoritative. Conflicts and low-confidence fields must be reviewed before use.")


def main() -> None:
    _inject_styles()
    _render_sidebar()

    st.markdown(
        '<div class="hero"><div class="eyebrow">Scottish property records · reviewer workspace</div>'
        '<div class="hero-title">Turn difficult records into evidence you can inspect.</div>'
        '<div class="hero-copy">Upload a sasine, deed or title record. SasineSense AI combines OCR, deterministic rules and structured extraction, then keeps every candidate tied to its source.</div>'
        '<div class="notice"><span class="dot"></span> Human review is always part of the workflow</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">Start a review</div>', unsafe_allow_html=True)
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    uploaded = st.file_uploader("Drop a deed, sasine, title sheet or image here", type=FILE_TYPES, label_visibility="visible")
    st.markdown("</div>", unsafe_allow_html=True)

    if not uploaded:
        st.markdown('<div class="empty-state"><div class="empty-icon">⌁</div><b>Your review canvas is ready</b><br/><span>Upload a source document to see extracted fields, evidence and confidence here.</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="footer-note">SasineSense AI · research prototype · never an authoritative title decision</div>', unsafe_allow_html=True)
        return

    file_signature = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get("file_signature") != file_signature:
        st.session_state["file_signature"] = file_signature
        st.session_state.pop("document", None)
        st.session_state.pop("result", None)

    response = st.session_state.get("document")
    if response is None:
        with st.spinner("Securing document metadata…"):
            response_obj = _safe_request(
                "POST", f"{API}/documents",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}, timeout=60,
            )
        if response_obj is None:
            return
        if not response_obj.ok:
            st.error(response_obj.text)
            return
        response = response_obj.json()
        st.session_state["document"] = response

    document_id = response["document_id"]
    top = st.columns([3, 1, 1, 1])
    with top[0]:
        st.markdown(f'<div class="small-note">CURRENT DOCUMENT</div><div class="field-value">{html.escape(uploaded.name)}</div><div class="mono small-note">{document_id}</div>', unsafe_allow_html=True)
    with top[1]:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Format</div><div class="stat-value">{html.escape(uploaded.name.rsplit(".", 1)[-1].upper())}</div><div class="stat-note">{uploaded.size / 1024:.1f} KB</div></div>', unsafe_allow_html=True)
    with top[2]:
        st.markdown('<div class="stat-card"><div class="stat-label">Mode</div><div class="stat-value">OCR</div><div class="stat-note">evidence-first</div></div>', unsafe_allow_html=True)
    with top[3]:
        st.download_button("Download source", uploaded.getvalue(), file_name=uploaded.name, mime=uploaded.type or "application/octet-stream")

    if st.session_state.get("result") is None:
        st.markdown("<br/>", unsafe_allow_html=True)
        if st.button("Run extraction", type="primary", use_container_width=True):
            with st.spinner("Reading pages, finding candidates and checking evidence…"):
                extract = _safe_request("POST", f"{API}/documents/{document_id}/extract", timeout=180)
            if extract is not None and extract.ok:
                st.session_state["result"] = extract.json()
                st.rerun()
            elif extract is not None:
                st.error(extract.text)
        st.markdown('<div class="empty-state"><div class="empty-icon">✦</div><b>Ready to extract</b><br/><span>Run the pipeline to create a reviewable result.</span></div>', unsafe_allow_html=True)
        return

    result = st.session_state["result"]
    confidence = _confidence(result.get("overall_confidence"))
    st.markdown('<div class="section-title">Review overview</div>', unsafe_allow_html=True)
    metrics = st.columns(4)
    with metrics[0]:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Document type</div><div class="stat-value" style="font-size:21px">{html.escape(str(result.get("document_type", "unknown")).replace("_", " ").title())}</div><div class="stat-note">classifier output</div></div>', unsafe_allow_html=True)
    with metrics[1]:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Confidence</div><div class="stat-value">{confidence:.0%}</div><div class="stat-note">{html.escape(str(result.get("metadata", {}).get("review_tier", "manual review")).replace("_", " "))}</div></div>', unsafe_allow_html=True)
    with metrics[2]:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Pages</div><div class="stat-value">{len(result.get("source_pages", []))}</div><div class="stat-note">source pages</div></div>', unsafe_allow_html=True)
    with metrics[3]:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Evidence items</div><div class="stat-value">{sum(len(x.get("evidence", [])) for x in ([result.get("document_date")] if result.get("document_date") else []) + result.get("parties", []) + result.get("places", []) + ([result.get("consideration")] if result.get("consideration") else []))}</div><div class="stat-note">traceable spans</div></div>', unsafe_allow_html=True)

    st.progress(confidence, text=f"Overall confidence · {confidence:.0%}")
    st.markdown(_status_chip(result), unsafe_allow_html=True)

    left, right = st.columns([1.08, .92], gap="large")
    with left:
        st.markdown('<div class="section-title">Source document</div>', unsafe_allow_html=True)
        if uploaded.type and uploaded.type.startswith("image/"):
            st.image(uploaded.getvalue())
        else:
            st.markdown('<div class="empty-state"><div class="empty-icon">▧</div><b>PDF source loaded</b><br/><span>Rendered pages are available to the extraction pipeline. Download the original above to inspect it at full resolution.</span></div>', unsafe_allow_html=True)
        with st.expander("Pipeline provenance"):
            metadata = result.get("metadata", {})
            st.json({key: metadata.get(key) for key in ("ocr_provider", "ner_provider", "structured_provider", "preprocess_operations", "review_tier")})
    with right:
        st.markdown('<div class="section-title">Structured result</div>', unsafe_allow_html=True)
        date = result.get("document_date")
        if date:
            _render_field(document_id, date, "document_date", "Document date")
        consideration = result.get("consideration")
        if consideration:
            _render_field(document_id, consideration, "consideration", "Consideration / price")
        for index, party in enumerate(result.get("parties", [])):
            _render_party(document_id, party, index)
        for index, place in enumerate(result.get("places", [])):
            _render_place(document_id, place, index)
        for index, field in enumerate(result.get("title_references", [])):
            _render_field(document_id, field, f"title_reference_{index}", "Title reference")
        if not any((date, consideration, result.get("parties"), result.get("places"), result.get("title_references"))):
            st.markdown('<div class="empty-state"><div class="empty-icon">?</div><b>No supported fields found</b><br/><span>The document needs classification or manual review. No values were invented.</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Audit & provenance</div>', unsafe_allow_html=True)
    audit_left, audit_right = st.columns(2)
    with audit_left:
        with st.expander("Raw JSON result"):
            st.json(result)
    with audit_right:
        history = _safe_request("GET", f"{API}/documents/{document_id}/reviews", timeout=30)
        if history is not None and history.ok and history.json():
            st.dataframe(history.json(), use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="small-note">No reviewer actions yet. Accept, edit, flag or mark a candidate unresolved to create the append-only audit trail.</div>', unsafe_allow_html=True)

    st.warning("Human review required. Extracted values are non-authoritative and must not be treated as legal title decisions.")
    st.markdown('<div class="footer-note">SasineSense AI · every candidate keeps its evidence · history is append-only</div>', unsafe_allow_html=True)


main()
