import os, re, time, requests
from datetime import datetime, timezone
from collections import Counter
import streamlit as st

st.set_page_config(page_title="KYC Agent v2 | Wallet Health & RWA", page_icon="🔍", layout="wide")

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"
ETHERSCAN_API_KEY = st.secrets.get("ETHERSCAN_API_KEY", os.environ.get("ETHERSCAN_API_KEY",""))

TORNADO_CASH = {
    "0x722122df12d4e14e13ac3b6895a86e84145b6967",
    "0xdd4c48c0b24039969fc16d1cdf626eab821d3384",
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b",
    "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf",
    "0xa160cdab225685da1d56aa342ad8841c3b53f291",
    "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936",
    "0xbb93e510bbcd0b7beb5a853875f9ec60275cf498",
}

OFAC_ADDRESSES = {
    "0xd882cfc20f52f2599d84b8e8d58c7fb62cfe344b",
    "0x901bb9583b24d97e995513c6778dc6888ab6870e",
    "0xa7e5d5a720f06526557c513402f2e6b5fa20b008",
}

st.markdown("""
<style>
.header-box{background:linear-gradient(135deg,#0A2342,#1B4F8A);padding:20px 28px;border-radius:10px;margin-bottom:20px;color:white}
.header-box h1{font-size:20px;margin:0;font-weight:700}
.header-box p{font-size:13px;margin:4px 0 0;opacity:.8}
.badge{background:#1B4F8A;color:#FFD700;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;display:inline-block;margin-top:8px}
.risk-HEALTHY{background:#1E8449;color:white;padding:12px 24px;border-radius:8px;font-size:18px;font-weight:700;text-align:center}
.risk-MODERATE{background:#E67E22;color:white;padding:12px 24px;border-radius:8px;font-size:18px;font-weight:700;text-align:center}
.risk-HIGH{background:#C0392B;color:white;padding:12px 24px;border-radius:8px;font-size:18px;font-weight:700;text-align:center}
.flag-critical{border-left:4px solid #C0392B;background:#fff0f0;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
.flag-high{border-left:4px solid #E74C3C;background:#fff0f0;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
.flag-medium{border-left:4px solid #F39C12;background:#fff8e1;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
.flag-positive{border-left:4px solid #27AE60;background:#f0fff4;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
.flag-low{border-left:4px solid #27AE60;background:#f0fff4;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
.eligible-yes{background:#eafaf1;border:2px solid #27AE60;padding:12px 16px;border-radius:8px;color:#1E8449;font-weight:700;font-size:15px}
.eligible-no{background:#fde8e8;border:2px solid #C0392B;padding:12px 16px;border-radius:8px;color:#C0392B;font-weight:700;font-size:15px}
.pattern-box{background:#fff8e1;border-left:4px solid #E67E22;padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0;font-size:13px}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
  <h1>🔍 KYC Agent v2 — Wallet Health & RWA Eligibility</h1>
  <p>On-Chain Due Diligence | Multi-Wallet Relationship Analysis | RWA Screening</p>
  <span class="badge">Powered by Etherscan API | FATF / MAS / FSC Framework</span>
</div>
""", unsafe_allow_html=True)

# ── API Functions ─────────────────────────────────────────
def _get(action, address, extra={}):
    params = {"chainid":"1","module":"account","action":action,
              "address":address,"apikey":ETHERSCAN_API_KEY,**extra}
    try:
        r = requests.get(ETHERSCAN_BASE, params=params, timeout=15)
        result = r.json().get("result",[])
        return result if isinstance(result, list) else []
    except:
        return []

def _get_single(module, action, address, extra={}):
    params = {"chainid":"1","module":module,"action":action,
              "address":address,"apikey":ETHERSCAN_API_KEY,**extra}
    try:
        r = requests.get(ETHERSCAN_BASE, params=params, timeout=15)
        return r.json().get("result","0")
    except:
        return "0"

def get_eth_balance(address):
    try: return int(_get_single("account","balance",address)) / 1e18
    except: return 0.0

def get_token_balances(address):
    txs = _get("tokentx", address, {"page":"1","offset":"50","sort":"desc"})
    tokens = {}
    for tx in txs:
        c = tx.get("contractAddress","")
        if c and c not in tokens:
            tokens[c] = {"symbol":tx.get("tokenSymbol","?"),"name":tx.get("tokenName","Unknown"),"contract":c}
    return list(tokens.values())[:10]

def get_transactions(address):
    return _get("txlist", address, {"startblock":"0","endblock":"99999999","page":"1","offset":"100","sort":"desc"})

def get_nft_count(address):
    txs = _get("tokennfttx", address, {"page":"1","offset":"50","sort":"desc"})
    return len({tx.get("contractAddress","") for tx in txs})

def analyze_related(address, txs):
    address_lower = address.lower()
    cp_count = Counter()
    cp_volume = {}
    for tx in txs:
        frm = tx.get("from","").lower()
        to  = tx.get("to","").lower()
        val = int(tx.get("value",0)) / 1e18
        other = to if frm == address_lower else frm
        if other and other != address_lower:
            cp_count[other] += 1
            cp_volume[other] = cp_volume.get(other,0) + val
    top = []
    for addr, cnt in cp_count.most_common(10):
        is_risky = addr in TORNADO_CASH or addr in OFAC_ADDRESSES
        top.append({"address":addr,"tx_count":cnt,
                    "total_volume_eth":round(cp_volume.get(addr,0),4),
                    "is_risky":is_risky,
                    "risk_reason":"Tornado Cash" if addr in TORNADO_CASH else ("OFAC Sanctioned" if addr in OFAC_ADDRESSES else "Normal")})
    total_in  = sum(int(tx.get("value",0))/1e18 for tx in txs if tx.get("to","").lower()==address_lower)
    total_out = sum(int(tx.get("value",0))/1e18 for tx in txs if tx.get("from","").lower()==address_lower)
    patterns = []
    risky_cp = [c for c in top if c["is_risky"]]
    if risky_cp:
        patterns.append(f"Funds routed through {len(risky_cp)} high-risk address(es)")
    if top and top[0]["tx_count"] / max(len(txs),1) > 0.5:
        patterns.append("Over 50% of transactions with single counterparty — concentration risk")
    small_unique = len([a for a,v in cp_volume.items() if v < 0.01 and cp_count[a]==1])
    if small_unique > 10:
        patterns.append(f"{small_unique} one-time micro-transfers — possible smurfing pattern")
    return {"top_counterparties":top,"total_inflow_eth":round(total_in,4),
            "total_outflow_eth":round(total_out,4),"unique_counterparties":len(cp_count),
            "risky_counterparty_count":len(risky_cp),"suspicious_patterns":patterns}

def compute_health(address, txs, eth_balance, tokens):
    score = 100; flags = []; deductions = []
    if address.lower() in OFAC_ADDRESSES:
        score -= 60; flags.append("CRITICAL: Address on OFAC SDN sanctions list")
        deductions.append(("OFAC Direct Match",-60))
    interacted = {tx.get("to","").lower() for tx in txs if tx.get("input","0x")!="0x"}
    tc_hits = interacted & TORNADO_CASH
    if tc_hits:
        score -= 40; flags.append(f"HIGH: Direct interaction with Tornado Cash ({len(tc_hits)} contracts)")
        deductions.append(("Tornado Cash Interaction",-40))
    counterparties = {tx.get("from","").lower() for tx in txs} | {tx.get("to","").lower() for tx in txs}
    ofac_hop = counterparties & OFAC_ADDRESSES - {address.lower()}
    if ofac_hop:
        score -= 25; flags.append(f"HIGH: 1-hop exposure to {len(ofac_hop)} OFAC address(es)")
        deductions.append(("OFAC 1-Hop Exposure",-25))
    if len(txs) < 5:
        score -= 10; flags.append(f"MEDIUM: New wallet ({len(txs)} transactions)")
        deductions.append(("New Wallet",-10))
    if eth_balance < 0.001 and len(txs) > 10:
        score -= 5; flags.append("LOW: ETH balance critically low despite active history")
        deductions.append(("Low ETH Balance",-5))
    small_txs = [tx for tx in txs if 0 < int(tx.get("value",0)) < 1e15]
    if len(small_txs) > 30:
        score -= 10; flags.append(f"MEDIUM: {len(small_txs)} micro-transactions detected")
        deductions.append(("Micro-transaction Pattern",-10))
    if eth_balance > 1.0: flags.append("POSITIVE: Significant ETH holdings")
    if len(tokens) >= 3: flags.append("POSITIVE: Diversified token portfolio")
    if len(txs) > 50: flags.append("POSITIVE: Active transaction history")
    score = max(0, min(100, score))
    if score >= 80: level,color = "HEALTHY","GREEN"
    elif score >= 50: level,color = "MODERATE RISK","AMBER"
    else: level,color = "HIGH RISK","RED"
    return {"score":score,"level":level,"color":color,"flags":flags,"deductions":deductions}

def assess_rwa(health_score, eth_balance, txs, health_level, related):
    reasons = []; eligible = True
    if health_score < 50: eligible=False; reasons.append("Health score below minimum threshold (50)")
    if eth_balance < 0.01: eligible=False; reasons.append("Insufficient ETH balance for gas requirements")
    if len(txs) < 3: eligible=False; reasons.append("Insufficient transaction history")
    if health_level == "HIGH RISK": eligible=False; reasons.append("High-risk flags prevent RWA participation")
    if related["risky_counterparty_count"] > 0:
        eligible=False; reasons.append(f"Transactions with {related['risky_counterparty_count']} high-risk counterparty(ies)")
    for p in related["suspicious_patterns"]:
        eligible=False; reasons.append(f"Suspicious pattern: {p}")
    if eligible:
        tier = "Tier 1 — Standard" if health_score>=80 else "Tier 2 — Enhanced Review"
        reasons.append(f"Wallet meets baseline requirements: {tier}")
    else:
        tier = "Not Eligible"
    return {"eligible":eligible,"tier":tier,"reasons":reasons}

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧪 Quick Test Addresses")
    if st.button("⛔ High Risk (Tornado Cash)", use_container_width=True):
        st.session_state.test_addr = "0x722122dF12D4e14e13Ac3b6895a86e84145b6967"
    if st.button("✅ Low Risk (General Wallet)", use_container_width=True):
        st.session_state.test_addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    if st.button("🚨 OFAC Sanctioned (Demo)", use_container_width=True):
        st.session_state.test_addr = "0xd882cfc20f52f2599d84b8e8d58c7fb62cfe344b"
    st.divider()
    st.markdown("### This Agent Checks")
    for cap in ["✅ ETH balance & ERC-20 tokens","✅ NFT collections",
                "✅ Wallet health score (0-100)","✅ OFAC SDN sanctions",
                "✅ Tornado Cash interactions","✅ Fund flow analysis",
                "✅ Counterparty risk mapping","✅ RWA eligibility screening"]:
        st.markdown(cap)
    st.divider()
    st.caption("Framework: FATF / MAS / FSC / OFAC SDN")

# ── Main Input ────────────────────────────────────────────
default_addr = st.session_state.get("test_addr","")
address = st.text_input("Ethereum Address (0x...)", value=default_addr,
                        placeholder="0x722122dF12D4e14e13Ac3b6895a86e84145b6967")
run = st.button("🔍 Analyse Wallet", type="primary", use_container_width=True)

if run and address:
    if not re.match(r'^0x[0-9a-fA-F]{40}$', address.strip()):
        st.error("❌ Invalid Ethereum address format")
        st.stop()

    with st.status("Running KYC Analysis...", expanded=True) as status:
        st.write("**Step 1/5** — Fetching ETH balance")
        eth_balance = get_eth_balance(address.lower())
        st.write("**Step 2/5** — Fetching transactions (last 100)")
        txs = get_transactions(address.lower())
        time.sleep(0.3)
        st.write("**Step 3/5** — Fetching ERC-20 tokens & NFTs")
        tokens = get_token_balances(address.lower())
        nft_count = get_nft_count(address.lower())
        time.sleep(0.3)
        st.write("**Step 4/5** — Analyzing counterparty relationships")
        related = analyze_related(address.lower(), txs)
        st.write("**Step 5/5** — Computing health score & RWA eligibility")
        health = compute_health(address.lower(), txs, eth_balance, tokens)
        rwa = assess_rwa(health["score"], eth_balance, txs, health["level"], related)
        status.update(label="✅ Analysis complete", state="complete")

    st.session_state["result"] = {
        "address":address,"eth_balance":eth_balance,"txs":txs,
        "tokens":tokens,"nft_count":nft_count,"related":related,
        "health":health,"rwa":rwa
    }

if "result" in st.session_state:
    r = st.session_state["result"]
    health = r["health"]; related = r["related"]; rwa = r["rwa"]

    st.divider()

    # Risk banner
    level_class = {"HEALTHY":"risk-HEALTHY","MODERATE RISK":"risk-MODERATE","HIGH RISK":"risk-HIGH"}.get(health["level"],"risk-HIGH")
    icons = {"HEALTHY":"✅","MODERATE RISK":"⚠️","HIGH RISK":"⛔"}
    st.markdown(f'<div class="{level_class}">{icons.get(health["level"],"🔴")} {health["level"]} — Health Score: {health["score"]}/100</div>', unsafe_allow_html=True)
    st.markdown(f"**Address:** `{r['address']}`")
    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["💼 Wallet Snapshot","📊 Health Score","🔗 Counterparty Analysis","🏛️ RWA Eligibility","📄 Download PDF"])

    with tab1:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("ETH Balance", f"{r['eth_balance']:.4f} ETH")
        c2.metric("Transactions", len(r['txs']))
        c3.metric("ERC-20 Tokens", len(r['tokens']))
        c4.metric("NFT Collections", r['nft_count'])
        if r['tokens']:
            st.markdown("**ERC-20 Token Holdings:**")
            token_str = "  ".join([f"`{t['symbol']}` {t['name'][:20]}" for t in r['tokens']])
            st.markdown(token_str)

    with tab2:
        col_score, col_flags = st.columns([1,2])
        with col_score:
            color_map = {"GREEN":"#1E8449","AMBER":"#E67E22","RED":"#C0392B"}
            bg = color_map.get(health["color"],"#888")
            st.markdown(f'<div style="background:{bg};color:white;padding:20px;border-radius:10px;text-align:center;font-size:36px;font-weight:700">{health["score"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center;color:{bg};font-weight:600;margin-top:8px">{health["level"]}</div>', unsafe_allow_html=True)
        with col_flags:
            st.markdown("**Health Indicators:**")
            for flag in health["flags"]:
                level = flag.split(":")[0].lower()
                cls = {"critical":"flag-critical","high":"flag-high","medium":"flag-medium",
                       "low":"flag-low","positive":"flag-positive"}.get(level,"flag-low")
                st.markdown(f'<div class="{cls}">{flag}</div>', unsafe_allow_html=True)
        if health["deductions"]:
            st.markdown("**Score Deductions:**")
            import pandas as pd
            df = pd.DataFrame(health["deductions"], columns=["Risk Factor","Points"])
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Inflow", f"{related['total_inflow_eth']} ETH")
        c2.metric("Total Outflow", f"{related['total_outflow_eth']} ETH")
        c3.metric("Unique Counterparties", related['unique_counterparties'])
        if related["suspicious_patterns"]:
            st.markdown("**⚠️ Suspicious Patterns Detected:**")
            for p in related["suspicious_patterns"]:
                st.markdown(f'<div class="pattern-box">⚠ {p}</div>', unsafe_allow_html=True)
        st.markdown("**Top Counterparty Addresses:**")
        if related["top_counterparties"]:
            import pandas as pd
            df = pd.DataFrame(related["top_counterparties"])
            df["address"] = df["address"].apply(lambda x: x[:20]+"..."+x[-4:])
            df.columns = ["Address","Tx Count","Volume (ETH)","Is Risky","Risk"]
            df = df[["Address","Tx Count","Volume (ETH)","Risk"]]
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab4:
        if rwa["eligible"]:
            st.markdown(f'<div class="eligible-yes">✓ ELIGIBLE — {rwa["tier"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="eligible-no">✗ NOT ELIGIBLE — {rwa["tier"]}</div>', unsafe_allow_html=True)
        st.markdown("**Assessment Factors:**")
        for reason in rwa["reasons"]:
            st.markdown(f"• {reason}")

    with tab5:
        st.markdown("### 📄 Download PDF Report")
        st.info("Install WeasyPrint to enable PDF download. On Streamlit Cloud, add `weasyprint` and `jinja2` to requirements.txt.")
        st.markdown("**Report would include:**")
        for item in ["Cover page with risk level","Wallet asset snapshot","Health score breakdown",
                     "Risk rule evaluation","Counterparty analysis","RWA eligibility","Analyst sign-off"]:
            st.markdown(f"✅ {item}")

elif run and not address:
    st.warning("Please enter an Ethereum address")
