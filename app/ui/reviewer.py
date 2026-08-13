"""Streamlit reviewer UI (Phase 10).

Displays the rendered document, structured extraction, confidence, evidence and
validation flags, and lets a human accept / edit / flag / mark-unresolved each
field. Reviewer actions are posted to the append-only audit log via the API;
history is never deleted. Outputs are non-authoritative and require review.
"""

import os

import requests
import streamlit as st

API = os.getenv("REVIEWER_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Property Record Reviewer", layout="wide")
st.title("AI-Assisted Property Record Reviewer")
st.caption("Research prototype — outputs are non-authoritative and require review.")


def _post_review(document_id: str, field: str, action: str, previous=None, new=None, note=None):
    payload = {
        "document_id": document_id,
        "field": field,
        "action": action,
        "previous_value": previous,
        "new_value": new,
        "note": note,
    }
    resp = requests.post(f"{API}/documents/{document_id}/reviews", json=payload, timeout=30)
    if resp.ok:
        st.success(f"Recorded '{action}' on {field}.")
    else:
        st.error(resp.text)


def _field_reviewer(document_id: str, field_name: str, current_value):
    with st.expander(f"Review: {field_name}", expanded=False):
        st.write(f"Current value: `{current_value}`")
        new_value = st.text_input("New value (for edit)", value=str(current_value or ""),
                                  key=f"edit_{field_name}")
        note = st.text_input("Note", key=f"note_{field_name}")
        cols = st.columns(4)
        if cols[0].button("Accept", key=f"acc_{field_name}"):
            _post_review(document_id, field_name, "accept", current_value, current_value, note)
        if cols[1].button("Edit", key=f"ed_{field_name}"):
            _post_review(document_id, field_name, "edit", current_value, new_value, note)
        if cols[2].button("Flag", key=f"fl_{field_name}"):
            _post_review(document_id, field_name, "flag", current_value, None, note)
        if cols[3].button("Unresolved", key=f"un_{field_name}"):
            _post_review(document_id, field_name, "mark_unresolved", current_value, None, note)


uploaded = st.file_uploader(
    "Upload a deed, sasine, title-related document, PDF or image",
    type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"],
)

if uploaded:
    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
    response = requests.post(f"{API}/documents", files=files, timeout=60)

    if not response.ok:
        st.error(response.text)
    else:
        doc = response.json()
        document_id = doc["document_id"]
        st.success(f"Uploaded: {document_id}")

        if st.button("Run extraction"):
            extract = requests.post(f"{API}/documents/{document_id}/extract", timeout=120)
            if not extract.ok:
                st.error(extract.text)
            else:
                st.session_state["result"] = extract.json()

        result = st.session_state.get("result")
        if result and result.get("document_id") == document_id:
            col1, col2 = st.columns([1, 1])

            with col1:
                st.subheader("Document")
                st.write(uploaded.name)
                if uploaded.type and uploaded.type.startswith("image/"):
                    # Keep compatibility with older Streamlit releases.
                    st.image(uploaded.getvalue())

            with col2:
                st.subheader("Structured extraction")
                tier = result.get("metadata", {}).get("review_tier", "unknown")
                st.metric("Overall confidence", result.get("overall_confidence"))
                st.write(f"Review tier: **{tier}** · "
                         f"review required: **{result.get('review_required')}**")

                date = result.get("document_date")
                if date:
                    st.markdown("**Document date**")
                    st.write(f"{date['value']} → {date.get('normalized_value')} "
                             f"(confidence {date['confidence']})")
                    if date.get("validation"):
                        st.caption(f"Validation: {date['validation']['status']} "
                                   f"{date['validation']['rules']}")
                    for span in date.get("evidence", []):
                        st.caption(f"Evidence (p{span['page']}): “{span['text']}”")
                    _field_reviewer(document_id, "document_date", date["value"])

                if result.get("parties"):
                    st.markdown("**Parties**")
                    for i, party in enumerate(result["parties"]):
                        st.write(f"- {party['name']} ({party['role']}, "
                                 f"conf {party['confidence']})")
                        _field_reviewer(document_id, f"party_{i}", party["name"])

                if result.get("places"):
                    st.markdown("**Places**")
                    for i, place in enumerate(result["places"]):
                        coords = (place.get("latitude"), place.get("longitude"))
                        st.write(f"- {place['name']} ({place.get('admin_area')}, "
                                 f"{coords}, conf {place['confidence']})")
                        _field_reviewer(document_id, f"place_{i}", place["name"])

                with st.expander("Raw JSON + provenance"):
                    st.json(result)

            st.warning("Human review required. Do not treat extracted values as authoritative.")

            history = requests.get(f"{API}/documents/{document_id}/reviews", timeout=30)
            if history.ok and history.json():
                st.subheader("Review history (append-only)")
                st.table(history.json())
