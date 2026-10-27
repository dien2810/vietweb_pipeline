"""Dashboard for browsing pipeline results.

Install: pip install streamlit
Run: streamlit run dashboard/app.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "outputs" / "stats"
PROC = ROOT / "data" / "processed"

st.set_page_config(page_title="vietweb pipeline", layout="wide")
st.title("Vietnamese web text pipeline")

funnel_file = STATS / "funnel.csv"
if not funnel_file.exists():
    st.warning("outputs/stats/funnel.csv not found. Run: python -m vietweb run")
    st.stop()

funnel = pd.read_csv(funnel_file)
c1, c2, c3 = st.columns(3)
c1.metric("Input documents", f"{int(funnel.iloc[0]['docs_in']):,}")
c2.metric("Kept", f"{int(funnel.iloc[-1]['docs_out']):,}")
c3.metric("Kept share", f"{funnel.iloc[-1]['pct_of_input']:.1f}%")

st.subheader("Processing funnel")
st.bar_chart(funnel.set_index("stage")["docs_out"])
st.dataframe(funnel)


@st.cache_data
def load(kind: str) -> pd.DataFrame:
    files = sorted((PROC / kind).glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True) if files else pd.DataFrame()


dropped = load("dropped")
kept = load("kept")

if not dropped.empty:
    st.subheader("Removal reasons")
    st.bar_chart(dropped["drop_reason"].value_counts())

st.subheader("Top domains (kept set)")
if not kept.empty:
    st.bar_chart(kept["domain"].value_counts().head(20))

st.subheader("Browse documents")
kind = st.radio("Set", ["kept", "dropped"], horizontal=True)
df = kept if kind == "kept" else dropped
if kind == "dropped" and not df.empty:
    reason = st.selectbox("Reason", sorted(df["drop_reason"].unique()))
    df = df[df["drop_reason"] == reason]
if not df.empty:
    i = st.number_input("Document index", 0, len(df) - 1, 0)
    row = df.iloc[int(i)]
    st.caption(row["url"])
    st.text(row["text"][:3000])
