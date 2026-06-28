"""
 HEIC -> JPG  |  Streamlit Upload & Convert  |  v6.0
"""

import os
import io
import tempfile
import zipfile
from pathlib import Path

from heic_engine import convert_file, check_heif_support, load_history, undo_last
from PIL import Image

import streamlit as st

st.set_page_config(
    page_title="HEIC -> JPG Converter",
    page_icon="#",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if not check_heif_support()[0]:
    st.error("pillow-heif not installed. Run: pip install pillow pillow-heif")
    st.stop()

# ── Dark theme ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    * { font-family: 'Inter', system-ui, sans-serif; }
    .stApp { background: #0b0e14; }
    h1, h2, h3 { color: #e6edf3 !important; }
    .stButton button {
        background: linear-gradient(135deg, #1f6feb, #58a6ff) !important;
        border: none !important; color: #fff !important;
        font-weight: 600 !important; border-radius: 8px !important;
        transition: all 0.2s !important;
    }
    .stButton button:hover { transform: translateY(-1px); box-shadow: 0 4px 20px #1f6feb55; }
    .stSlider > div > div { background: #161b22 !important; }
    [data-testid="stFileUploadDropzone"] {
        background: #161b22 !important; border: 2px dashed #30363d !important;
        border-radius: 12px !important; padding: 2rem !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #58a6ff !important;
    }
    [data-testid="stFileUploadDropzone"] small {
        color: #484f58 !important;
    }
    .glitch {
        font-size: 2.2rem; font-weight: 900;
        background: linear-gradient(135deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin-bottom: 0.2rem;
    }
    .subtitle { text-align: center; color: #8b949e; font-size: 0.9rem; margin-bottom: 0.5rem; }


    .history-item {
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 0.6rem 1rem; margin-bottom: 0.4rem; font-size: 0.8rem; color: #8b949e;
    }
    .history-item strong { color: #e6edf3; }
    .file-row {
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 0.5rem 0.8rem; margin-bottom: 0.3rem; font-size: 0.82rem;
    }
    header [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    .stDeployButton { display: none !important; }
    section[data-testid="stSidebar"] .stButton button {
        background: transparent !important; border: 1px solid #30363d !important;
        font-size: 0.75rem !important; padding: 0.2rem 0.5rem !important;
        border-radius: 6px !important; font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        border-color: #58a6ff !important;
    }
    section[data-testid="stSidebar"] .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #1f6feb, #58a6ff) !important;
        border: none !important;
    }
    .sidebar-header {
        display: flex; align-items: center; gap: 0.5rem;
        font-size: 0.95rem; font-weight: 700; color: #e6edf3;
        padding: 0.25rem 0 0.75rem 0;
    }
    .quality-visual {
        margin-top: 0.5rem; height: 4px; border-radius: 4px;
        background: #30363d; overflow: hidden; position: relative;
    }
    .quality-visual-fill {
        height: 100%; border-radius: 4px; transition: width 0.2s;
    }

    [data-testid="stSidebarCollapsedButton"] {
        position: fixed !important;
        bottom: 1rem !important; top: auto !important; left: 1rem !important;
        width: 40px !important; height: 40px !important; border-radius: 12px !important;
        background: #1c2333 !important; border: 1.5px solid #30363d !important;
        opacity: 0.85 !important; transition: all 0.2s !important;
        z-index: 999999 !important;
    }
    [data-testid="stSidebarCollapsedButton"]:hover {
        opacity: 1 !important; border-color: #58a6ff !important; background: #1f6feb33 !important;
        transform: scale(1.05) !important;
    }
    [data-testid="stSidebarCollapsedButton"] svg { fill: #8b949e !important; }
    [data-testid="stSidebarCollapsedButton"]:hover svg { fill: #58a6ff !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown('<div class="glitch"># HEIC &rarr; JPG #</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">upload &middot; convert &middot; download &mdash; originals never leave your device</div>', unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-header">⚙️ Settings</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Lossless", use_container_width=True):
            st.session_state.quality_target = 100
    with c2:
        if st.button("High", use_container_width=True):
            st.session_state.quality_target = 95
    with c3:
        if st.button("Standard", use_container_width=True):
            st.session_state.quality_target = 80

    quality = st.session_state.get("quality_target", 100)
    quality = st.slider(
        "JPEG quality",
        min_value=1, max_value=100, value=quality,
        help="100 = highest quality. 95+ recommended.",
        key="quality_slider",
    )
    st.session_state.quality_target = quality

    tier = "lossless" if quality == 100 else "high" if quality >= 95 else "standard" if quality >= 70 else "low"
    tier_colors = {"lossless": "#3fb950", "high": "#58a6ff", "standard": "#d29922", "low": "#f85149"}
    bar_color = tier_colors[tier]
    bar_pct = quality

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.25rem">'
        f'<span style="font-size:0.75rem;color:#8b949e">{quality}%</span>'
        f'<span style="font-size:0.7rem;color:{bar_color};font-weight:600;text-transform:uppercase">{tier}</span>'
        f'</div>'
        f'<div class="quality-visual"><div class="quality-visual-fill" style="width:{bar_pct}%;background:linear-gradient(90deg,#1f6feb,{bar_color})"></div></div>',
        unsafe_allow_html=True,
    )

    hint = "📦 Best quality, larger files" if quality >= 95 else "📦 Balanced size & quality" if quality >= 70 else "📦 Smaller files, quality loss"
    st.caption(hint)

    st.markdown("---")
    st.markdown("### History")

    history = load_history()
    if history:
        for h in reversed(history[-10:]):
            ts = h.get("timestamp", "?")[:19].replace("T", " ")
            convs = h.get("conversions", h.get("renames", []))
            st.markdown(
                f'<div class="history-item"><strong>{len(convs)} files</strong> &middot; Q{h.get("quality", "?")} &middot; {ts}</div>',
                unsafe_allow_html=True,
            )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Undo Last", use_container_width=True):
                ok, msg = undo_last()
                st.success(msg) if ok else st.warning(msg)
                st.rerun()
        with col2:
            if st.button("Clear", use_container_width=True):
                Path.home().joinpath(".heic_renamer_history.json").write_text("[]")
                st.rerun()
    else:
        st.markdown('<div class="history-item" style="text-align:center">No sessions yet</div>', unsafe_allow_html=True)

# ── Main: File upload ───────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "Drop your HEIC/HEIF files here",
    type=["heic", "HEIC", "heif", "HEIF"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    st.markdown(
        f'<div style="margin:0.3rem 0;color:#8b949e;font-size:0.85rem">'
        f'<strong style="color:#58a6ff">{len(uploaded_files)}</strong> file(s) selected'
        f'</div>',
        unsafe_allow_html=True,
    )

    for f in uploaded_files:
        stem = Path(f.name).stem
        size_kb = len(f.getvalue()) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
        c1, c2, c3 = st.columns([3, 1, 3])
        with c1:
            st.markdown(f'<span style="color:#e6edf3;font-size:0.85rem">{f.name}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<span style="color:#8b949e;font-size:0.82rem">{size_str}</span>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<span style="color:#3fb950;font-size:0.85rem">{stem}.jpg</span>', unsafe_allow_html=True)

    if st.button("Convert All", type="primary", use_container_width=True):
        progress_bar = st.progress(0, text="Preparing...")
        status_text = st.empty()
        results = []

        for i, uploaded in enumerate(uploaded_files):
            stem = Path(uploaded.name).stem
            orig_size = len(uploaded.getvalue())
            status_text.markdown(
                f'<span style="color:#58a6ff">Converting</span> '
                f'<span style="color:#8b949e">{uploaded.name}</span>',
                unsafe_allow_html=True,
            )
            progress_bar.progress((i + 1) / len(uploaded_files))

            with tempfile.NamedTemporaryFile(delete=False, suffix=".heic") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            out_path = Path(tmp_path).with_suffix(".jpg")
            try:
                conv_result = convert_file(Path(tmp_path), out_path, quality=quality)
                jpg_bytes = out_path.read_bytes()
                jpg_size = len(jpg_bytes)
                pct = (1 - jpg_size / orig_size) * 100
                results.append({
                    "name": f"{stem}.jpg",
                    "bytes": jpg_bytes,
                    "size": jpg_size,
                    "original": orig_size,
                    "savings": pct,
                })
            except Exception as e:
                st.error(f"{uploaded.name}: {e}")
            finally:
                os.unlink(tmp_path)
                if out_path.exists():
                    os.unlink(out_path)

        st.session_state.results = results
        st.rerun()

# ── Download results ───────────────────────────────────────────────────────
if "results" in st.session_state and st.session_state.results:
    results = st.session_state.results
    total_orig = sum(r["original"] for r in results)
    total_new = sum(r["size"] for r in results)
    total_pct = (1 - total_new / total_orig) * 100

    st.markdown("---")
    st.markdown("### Converted")

    col_summary = st.columns(3)
    with col_summary[0]:
        st.markdown(
            f'<div style="text-align:center;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:0.8rem">'
            f'<div style="font-size:1.4rem;font-weight:700;color:#58a6ff">{len(results)}</div>'
            f'<div style="font-size:0.7rem;color:#8b949e">FILES</div></div>',
            unsafe_allow_html=True,
        )
    with col_summary[1]:
        color = "#3fb950" if total_pct > 0 else "#8b949e"
        label = f"{abs(total_pct):.1f}% smaller" if total_pct > 0 else "same size"
        st.markdown(
            f'<div style="text-align:center;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:0.8rem">'
            f'<div style="font-size:1.4rem;font-weight:700;color:{color}">{label}</div>'
            f'<div style="font-size:0.7rem;color:#8b949e">SIZE CHANGE</div></div>',
            unsafe_allow_html=True,
        )
    with col_summary[2]:
        st.markdown(
            f'<div style="text-align:center;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:0.8rem">'
            f'<div style="font-size:1.4rem;font-weight:700;color:#e6edf3">Q{quality}</div>'
            f'<div style="font-size:0.7rem;color:#8b949e">QUALITY</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="color:#8b949e;font-size:0.82rem;margin-bottom:0.5rem">'
        f'<strong style="color:#e6edf3">Original:</strong> {total_orig / 1048576:.1f} MB &rarr; '
        f'<strong style="color:#e6edf3">JPG:</strong> {total_new / 1048576:.1f} MB</div>',
        unsafe_allow_html=True,
    )

    for r in results:
        size_str = f"{r['size'] / 1024:.1f} KB" if r['size'] < 1048576 else f"{r['size'] / 1048576:.1f} MB"
        orig_str = f"{r['original'] / 1024:.1f} KB" if r['original'] < 1048576 else f"{r['original'] / 1048576:.1f} MB"
        savings_color = "#3fb950" if r["savings"] > 0 else "#f85149"
        st.markdown(
            f'<div class="file-row" style="display:flex;justify-content:space-between;align-items:center">'
            f'<span style="color:#e6edf3">{r["name"]}</span>'
            f'<span><span style="color:#8b949e">{orig_str}</span>'
            f'<span style="color:#8b949e;margin:0 0.3rem">&rarr;</span>'
            f'<span style="color:#e6edf3">{size_str}</span>'
            f'<span style="color:{savings_color};margin-left:0.5rem">{r["savings"]:.1f}%</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Build ZIP in memory
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            zf.writestr(r["name"], r["bytes"])
    zip_bytes = zip_buf.getvalue()

    col_btns = st.columns([1, 1, 1])
    with col_btns[0]:
        st.download_button(
            label=f"Download All ({len(results)} files)",
            data=zip_bytes,
            file_name="converted-images.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with col_btns[1]:
        if st.button("Convert More", use_container_width=True):
            for key in ["results"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
else:
    if not uploaded_files:
        st.markdown(
            '<div style="text-align:center;padding:1.5rem;color:#484f58;font-size:0.9rem">'
            'Drop HEIC/HEIF files above to convert them to JPG</div>',
            unsafe_allow_html=True,
        )
