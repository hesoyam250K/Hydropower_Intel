"""Industrial engineering design system and CSS styling for HydroPower Intelligence."""

import streamlit as st


ENGINEERING_CSS = """
<style>
    /* Global Container Adjustments */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1400px;
    }

    /* Top Banner / Brand Header */
    .app-brand {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1.25rem;
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 6px;
        margin-bottom: 1.25rem;
    }
    .app-brand-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: 0.5px;
    }
    .app-brand-sub {
        font-size: 0.8rem;
        color: #94A3B8;
        font-family: monospace;
    }

    /* Metric Cards - Industrial Engineering Aesthetic */
    div[data-testid="stMetric"] {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-family: monospace;
    }
    .badge-normal {
        background-color: #064E3B;
        color: #34D399;
        border: 1px solid #059669;
    }
    .badge-warning {
        background-color: #78350F;
        color: #FBBF24;
        border: 1px solid #D97706;
    }
    .badge-alarm {
        background-color: #7F1D1D;
        color: #F87171;
        border: 1px solid #DC2626;
    }
    .badge-simulated {
        background-color: #1E3A8A;
        color: #60A5FA;
        border: 1px solid #2563EB;
    }
    .badge-physical {
        background-color: #374151;
        color: #E5E7EB;
        border: 1px solid #6B7280;
    }

    /* Engineering Card Containers */
    .eng-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    .eng-card-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #E2E8F0;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.4rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Formula & Code Presentation Box */
    .formula-box {
        background-color: #0F172A;
        border: 1px solid #334155;
        border-left: 3px solid #2563EB;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.85rem;
        color: #E2E8F0;
        margin: 0.5rem 0;
        line-height: 1.4;
    }

    /* Data Tables */
    div[data-testid="stTable"] table {
        font-size: 0.85rem;
        color: #E2E8F0;
    }

    /* Sidebar Navigation Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #334155;
    }

    /* Restrained Button Styling */
    div.stButton > button {
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.4rem 1rem;
        border: 1px solid #475569;
        transition: all 0.15s ease-in-out;
    }
</style>
"""


def apply_engineering_theme() -> None:
    """Injects custom CSS into the Streamlit session."""
    st.markdown(ENGINEERING_CSS, unsafe_allow_html=True)


def render_header(current_project_name: str = "Clearwater Run-of-River Hydro") -> None:
    """Renders the top branding header and system mode indicator."""
    st.markdown(
        f"""
        <div class="app-brand">
            <div>
                <span class="app-brand-title">HYDROPOWER INTELLIGENCE</span>
                <span style="margin-left: 10px; color: #64748B;">|</span>
                <span style="margin-left: 10px; color: #94A3B8; font-size: 0.85rem;">Desktop Engineering Suite</span>
            </div>
            <div>
                <span style="font-size: 0.8rem; color: #94A3B8; margin-right: 8px;">ACTIVE PROJECT:</span>
                <span class="badge badge-simulated">{current_project_name}</span>
                <span style="margin-left: 10px;" class="badge badge-normal">OFFLINE ENGINE: READY</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
