import re
import html
from pathlib import Path

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

APP_DIR = Path(__file__).parent
SNAPSHOT_DIR = APP_DIR / "snapshots"

st.set_page_config(page_title="AdMatch AI", page_icon="🔎", layout="wide")

st.markdown("""
<style>
.main {background: #f7f9fd;}
.block-container {padding-top: 1.4rem; max-width: 1500px;}
.hero {padding: 1.1rem 1.4rem; border-radius: 18px; background: linear-gradient(110deg,#eef2ff,#f0f9ff); border: 1px solid #dbe5ff; margin-bottom: 1rem;}
.small-muted {color: #64748b; font-size: .9rem;}
.finding {border: 1px solid #e2e8f0; border-radius: 14px; padding: 1rem; background: white; margin: .6rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🔎 AdMatch AI</h1><div>Ad-to-Landing-Page Message Match Auditor</div><p class="small-muted">Check what an ad promises against the actual supplied landing-page snapshot. Every reported quote is verified against the source text.</p></div>', unsafe_allow_html=True)

DEMO_ROWS = [
    {
        "campaign_id": "AD-01", "campaign_name": "Personal Loan Campaign",
        "category": "Finance",
        "headline": "Get Your Personal Loan Approved in 24 Hours!",
        "description": "Apply today and receive instant approval with zero paperwork. Low interest rates and flexible repayment options.",
        "landing_page_url": "https://example.com/personal-loan",
        "snapshot_file": "personal_loan.html"
    },
    {
        "campaign_id": "AD-02", "campaign_name": "SaaS Analytics Tool",
        "category": "SaaS",
        "headline": "Understand Your Business Data in Minutes",
        "description": "Try our analytics platform free for 14 days. No credit card required.",
        "landing_page_url": "https://example.com/analytics",
        "snapshot_file": "saas_analytics.html"
    },
    {
        "campaign_id": "AD-03", "campaign_name": "E-commerce Sale",
        "category": "E-commerce",
        "headline": "Up to 50% Off Electronics",
        "description": "Shop selected electronics with free delivery on every order.",
        "landing_page_url": "https://example.com/electronics",
        "snapshot_file": "electronics.html"
    }
]

def clean_text(raw: str, is_html: bool = False) -> str:
    if is_html:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    return re.sub(r"\s+", " ", raw).strip()

def split_sentences(text: str):
    pieces = re.split(r"(?<=[.!?])\s+|[\n;]+", text)
    return [p.strip(" \t\r\n-•") for p in pieces if len(p.strip()) >= 8]

STOPWORDS = set("""a an the and or but if to of in on for from with by is are be our your you we they it this that as at into within every all any no not free get today now new best low high up per""".split())

def tokens(text: str):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}

def overlap_score(claim: str, sentence: str):
    a, b = tokens(claim), tokens(sentence)
    if not a:
        return 0.0
    return len(a & b) / len(a)

def find_exact_quote(quote: str, page_text: str):
    # A quote is only displayed as verified when its exact normalized text is present.
    norm_page = re.sub(r"\s+", " ", page_text).strip()
    norm_quote = re.sub(r"\s+", " ", quote).strip()
    return bool(norm_quote and norm_quote in norm_page)

def analyze_ad(headline, description, page_text):
    ad_text = f"{headline}. {description}".strip()
    claims = split_sentences(ad_text)
    page_sentences = split_sentences(page_text)
    if not page_sentences and page_text:
        page_sentences = [page_text[:500]]

    findings = []
    for claim in claims:
        # Search for the most similar page sentence using lexical overlap.
        ranked = sorted(
            [(overlap_score(claim, sent), sent) for sent in page_sentences],
            key=lambda x: x[0], reverse=True
        )
        best_score, best_sentence = ranked[0] if ranked else (0.0, "")
        claim_tokens = tokens(claim)

        # Detect high-risk absolute/quantified promises that require explicit support.
        high_risk_terms = [
            "guaranteed", "guarantee", "approved", "approval", "24 hours", "instant",
            "zero paperwork", "no paperwork", "free delivery", "free shipping",
            "no credit card", "100%", "up to", "50%", "same day", "same-day",
            "lowest", "risk free", "risk-free"
        ]
        lower_claim = claim.lower()
        risk_terms = [term for term in high_risk_terms if term in lower_claim]
        threshold = 0.48 if risk_terms else 0.34

        if best_score < threshold:
            severity = "High" if risk_terms else "Medium"
            issue_type = "Unsupported claim" if risk_terms else "Message not clearly supported"
            explanation = (
                "This ad sentence contains a specific or high-impact promise that was not clearly found "
                "in the supplied landing-page text."
                if risk_terms else
                "The supplied page text does not contain enough matching language to confirm this ad message."
            )
            evidence = ""
            findings.append({
                "claim": claim, "type": issue_type, "severity": severity,
                "evidence": evidence, "verified": False,
                "explanation": explanation,
                "fix": "Verify that this promise is accurate. If it is, state it clearly and prominently on the landing page; otherwise, revise the ad to match the actual offer.",
                "similarity": best_score
            })
        elif best_score < 0.72:
            quote = best_sentence
            verified = find_exact_quote(quote, page_text)
            findings.append({
                "claim": claim, "type": "Partial support", "severity": "Medium",
                "evidence": quote if verified else "",
                "verified": verified,
                "explanation": "Some related wording appears on the page, but it may not fully establish the exact promise made by the ad.",
                "fix": "Make the offer details more explicit near the main headline or call to action, and ensure the ad wording accurately reflects the page.",
                "similarity": best_score
            })

    # Add a CTA mismatch only when both sides have identifiable CTA language.
    ad_ctas = [x for x in ["apply", "buy", "shop", "sign up", "start free trial", "book", "download", "learn more"] if x in ad_text.lower()]
    page_ctas = [x for x in ["apply", "buy", "shop", "sign up", "start free trial", "book", "download", "learn more"] if x in page_text.lower()]
    if ad_ctas and not any(cta in page_ctas for cta in ad_ctas):
        findings.append({
            "claim": f"Ad call to action: {', '.join(ad_ctas)}",
            "type": "CTA mismatch", "severity": "Low", "evidence": "",
            "verified": False,
            "explanation": "The page text does not clearly show the same call-to-action language found in the ad.",
            "fix": "Align the primary landing-page button with the action promised in the ad.",
            "similarity": 0.0
        })

    # Score is a transparent heuristic, not a conversion prediction.
    weighted_penalty = 0
    for f in findings:
        weighted_penalty += {"High": 22, "Medium": 13, "Low": 6}.get(f["severity"], 10)
    score = max(0, min(100, 100 - weighted_penalty))
    if score >= 80:
        label = "Strong match"
    elif score >= 60:
        label = "Partial match"
    else:
        label = "Weak match"
    return score, label, findings, claims

def load_uploaded_dataset(uploaded):
    try:
        df = pd.read_csv(uploaded)
        required = {"headline", "description"}
        if not required.issubset(set(df.columns.str.lower())):
            st.error("CSV needs at least headline and description columns. Recommended columns: campaign_name, category, headline, description, landing_page_url, snapshot_file.")
            return None
        # Make columns case-insensitive for expected names.
        df.columns = [str(c).strip().lower() for c in df.columns]
        for col, default in [
            ("campaign_id", None), ("campaign_name", "Imported ad"),
            ("category", "Other"), ("landing_page_url", ""),
            ("snapshot_file", ""), ("snapshot_text", "")
        ]:
            if col not in df.columns:
                df[col] = default
        if "campaign_id" not in df.columns or df["campaign_id"].isna().all():
            df["campaign_id"] = [f"CSV-{i+1:03d}" for i in range(len(df))]
        return df.fillna("")
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return None

with st.sidebar:
    st.header("📂 Dataset")
    source = st.radio("Choose input", ["Try demo samples", "Upload your CSV"])
    uploaded_csv = None
    if source == "Upload your CSV":
        uploaded_csv = st.file_uploader("Upload ad dataset (.csv)", type=["csv"])
    st.divider()
    st.caption("Snapshot-first workflow")
    st.write("The live URL is shown for reference. The analysis should use the offline snapshot or text you supply, so network failures do not affect results.")
    st.caption("Prototype note: matching/scoring is a transparent baseline heuristic. Validate against the event dataset before presenting results.")

if source == "Upload your CSV" and uploaded_csv is not None:
    df = load_uploaded_dataset(uploaded_csv)
    if df is None:
        st.stop()
elif source == "Upload your CSV":
    st.info("Upload the CSV supplied by the organizers, or choose demo samples to explore the interface.")
    st.stop()
else:
    df = pd.DataFrame(DEMO_ROWS)

df["display_name"] = df["campaign_name"].astype(str) + " · " + df["campaign_id"].astype(str)
selected_label = st.selectbox("Select an ad to audit", df["display_name"].tolist())
row = df[df["display_name"] == selected_label].iloc[0]

left, right = st.columns([1, 1], gap="large")
with left:
    st.subheader("📣 Ad copy")
    st.markdown(f"**Campaign:** {row.get('campaign_name', '')}  \n**Category:** {row.get('category', 'Other')}")
    st.markdown("**Headline**")
    st.info(str(row.get("headline", "")))
    st.markdown("**Description**")
    st.info(str(row.get("description", "")))
with right:
    st.subheader("🌐 Landing page source")
    st.write(f"**URL:** {row.get('landing_page_url', '') or 'Not provided'}")
    snapshot_file = str(row.get("snapshot_file", "")).strip()
    st.write(f"**Snapshot file:** {snapshot_file or 'Upload or paste content below'}")

snapshot_upload = st.file_uploader("Upload this ad's offline snapshot (.html, .htm, .txt)", type=["html", "htm", "txt"], key=f"snapshot-{row['campaign_id']}")
pasted_text = st.text_area("Or paste extracted landing-page text / HTML", height=120, placeholder="Paste the saved page text or HTML here…")
page_text = ""

if snapshot_upload is not None:
    raw = snapshot_upload.getvalue().decode("utf-8", errors="ignore")
    page_text = clean_text(raw, is_html=snapshot_upload.name.lower().endswith((".html", ".htm")))
elif pasted_text.strip():
    page_text = clean_text(pasted_text, is_html=("<html" in pasted_text.lower() or "<body" in pasted_text.lower()))
elif str(row.get("snapshot_text", "")).strip():
    page_text = clean_text(str(row.get("snapshot_text", "")))
elif snapshot_file and (SNAPSHOT_DIR / snapshot_file).exists():
    raw = (SNAPSHOT_DIR / snapshot_file).read_text(encoding="utf-8", errors="ignore")
    page_text = clean_text(raw, is_html=snapshot_file.lower().endswith((".html", ".htm")))

if not page_text:
    st.warning("No snapshot content loaded yet. Upload the matching offline HTML/TXT snapshot or paste its content to analyze this ad.")
    st.stop()

with st.expander("Preview extracted page text", expanded=False):
    st.write(page_text[:5000] + ("…" if len(page_text) > 5000 else ""))

if st.button("🔍 Analyze message match", type="primary", use_container_width=True):
    score, label, findings, claims = analyze_ad(str(row["headline"]), str(row["description"]), page_text)
    st.session_state["last_result"] = {
        "campaign": str(row.get("campaign_name", "")),
        "campaign_id": str(row.get("campaign_id", "")),
        "score": score, "label": label, "findings": findings, "claims": claims
    }

result = st.session_state.get("last_result")
if result and result["campaign_id"] == str(row.get("campaign_id", "")):
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Message match score", f'{result["score"]}/100')
    c2.metric("Findings", len(result["findings"]))
    c3.metric("Claims checked", len(result["claims"]))
    st.caption(f'Assessment: **{result["label"]}**. Score is based on transparent heuristic penalties; it is not a probability of conversion.')

    st.subheader("🧾 Findings & recommended fixes")
    if not result["findings"]:
        st.success("No clear mismatch was detected by the baseline checker. This does not guarantee that every claim is supported; review important claims manually.")
    for i, f in enumerate(result["findings"], 1):
        color = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}.get(f["severity"], "⚪")
        with st.container(border=True):
            st.markdown(f"### {color} {i}. {f['type']} · {f['severity']} severity")
            st.markdown(f"**Ad claim**  \n{f['claim']}")
            if f["evidence"] and f["verified"]:
                st.markdown(f'**Exact page quote**  \n> "{f["evidence"]}"')
                st.success("Evidence quote verified in supplied page text.")
            else:
                st.warning("No exact supporting quote was verified for this finding. This is a gap/absence finding, not a quoted page statement.")
            st.markdown(f"**Why it matters:** {f['explanation']}")
            st.markdown(f"**Suggested fix:** {f['fix']}")
    out_rows = []
    for f in result["findings"]:
        out_rows.append({
            "campaign_id": result["campaign_id"], "campaign": result["campaign"],
            "score": result["score"], "assessment": result["label"],
            "type": f["type"], "severity": f["severity"], "ad_claim": f["claim"],
            "page_evidence": f["evidence"], "evidence_verified": f["verified"],
            "explanation": f["explanation"], "suggested_fix": f["fix"]
        })
    if out_rows:
        st.download_button(
            "⬇️ Export findings as CSV",
            data=pd.DataFrame(out_rows).to_csv(index=False).encode("utf-8"),
            file_name=f'{result["campaign_id"]}_admatch_findings.csv',
            mime="text/csv"
        )

with st.expander("Dataset format guide"):
    st.markdown("""
    Your CSV should contain at least:
    - `headline`
    - `description`

    Recommended columns:
    - `campaign_id`
    - `campaign_name`
    - `category`
    - `landing_page_url`
    - `snapshot_file` (filename inside the `snapshots/` folder)
    - `snapshot_text` (optional: extracted text can be stored directly in the CSV)

    Keep the original offline snapshots from the organizers. Do not replace them with guessed or invented page content.
    """)
