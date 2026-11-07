"""Shared look for both apps: an iOS 26-style "liquid glass" theme for Streamlit.

Everything visual lives here so the page files stay about behaviour.
All text that comes from students or the model is HTML-escaped before it is put into markup.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from grievance_agent.taxonomy import HUMAN_REVIEW_AMBIGUOUS, SGRC_PRIORITY, SGRC_STANDARD, URGENT_ALERT

esc = html.escape

# iOS system colours (light appearance)
BLUE, GREEN, ORANGE, RED, PURPLE, INDIGO, TEAL, GRAY = (
    "#007AFF", "#34C759", "#FF9500", "#FF3B30", "#AF52DE", "#5856D6", "#30B0C7", "#8E8E93")

ROUTE_STYLE = {  # colour, short label, SF-style symbol
    URGENT_ALERT: (RED, "Urgent", "emergency"),
    HUMAN_REVIEW_AMBIGUOUS: (ORANGE, "Human review", "help"),
    SGRC_PRIORITY: (PURPLE, "Priority", "priority_high"),
    SGRC_STANDARD: (BLUE, "Standard", "inbox"),
}
STATUS_STYLE = {
    "intake": (GRAY, "In progress"), "crisis": (RED, "Staff alerted"), "submitted": (BLUE, "Received"),
    "in_review": (INDIGO, "In review"), "closed": (GREEN, "Closed"),
}


_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,1,0&display=swap');

:root {
  --accent: __ACCENT__;
  --accent2: __ACCENT2__;
  --ink: #1d1d1f;
  --ink2: rgba(60,60,67,.72);
  --ink3: rgba(60,60,67,.45);
  --glass: rgba(255,255,255,.58);
  --glass-strong: rgba(255,255,255,.78);
  --stroke: rgba(255,255,255,.75);
  --hair: rgba(60,60,67,.12);
  --shadow: 0 1px 1px rgba(0,0,0,.03), 0 10px 30px -8px rgba(31,38,135,.18);
  --r-xl: 30px; --r-lg: 22px; --r-md: 16px;
  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", Inter, "Segoe UI", Roboto, sans-serif;
}

/* ---------- canvas ---------- */
html, body, .stApp, [class*="css"], .stMarkdown, button, input, textarea, select { font-family: var(--font) !important; }
.stApp {
  color: var(--ink);
  background:
    radial-gradient(1200px 700px at 8% -10%, __BG1__ 0%, transparent 60%),
    radial-gradient(900px 700px at 100% 0%, __BG2__ 0%, transparent 55%),
    radial-gradient(1000px 800px at 50% 110%, __BG3__ 0%, transparent 60%),
    #f2f2f7;
  background-attachment: fixed;
}
.stApp::before, .stApp::after {
  content: ""; position: fixed; z-index: 0; pointer-events: none; border-radius: 50%;
  filter: blur(70px); opacity: .55; animation: drift 26s ease-in-out infinite alternate;
}
.stApp::before { width: 520px; height: 520px; left: -120px; top: 30%; background: __BLOB1__; }
.stApp::after  { width: 600px; height: 600px; right: -160px; top: 8%; background: __BLOB2__; animation-delay: -9s; }
@keyframes drift { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(60px,-40px) scale(1.08); } 100% { transform: translate(-30px,50px) scale(.95); } }
@media (prefers-reduced-motion: reduce) { .stApp::before, .stApp::after { animation: none; } }
[data-testid="stMain"], [data-testid="stSidebar"], header { position: relative; z-index: 1; }

.block-container { padding-top: 4.6rem !important; padding-bottom: 6rem !important; max-width: __MAXW__ !important; }
#MainMenu, footer, [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stDecoration"], [data-testid="InputInstructions"] { display: none !important; }

/* ---------- top bar & nav (floating glass capsule) ---------- */
header[data-testid="stHeader"] {
  background: rgba(242,242,247,.55) !important;
  backdrop-filter: blur(24px) saturate(180%); -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-bottom: .5px solid var(--hair);
}
[data-testid="stTopNavLinkContainer"], [data-testid="stNavSectionHeader"] { gap: 4px; }
header a[data-testid="stTopNavLink"], header [data-testid="stTopNavLink"] {
  border-radius: 999px !important; padding: 6px 14px !important; font-weight: 600 !important; color: var(--ink2) !important;
  transition: all .2s ease;
}
header a[data-testid="stTopNavLink"]:hover { background: rgba(255,255,255,.7) !important; color: var(--ink) !important; }
header a[data-testid="stTopNavLink"][aria-current="page"], header [data-testid="stTopNavLink"][aria-selected="true"] {
  background: var(--glass-strong) !important; color: var(--accent) !important;
  box-shadow: 0 2px 10px -2px rgba(0,0,0,.12), inset 0 0 0 .5px var(--stroke);
}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: rgba(255,255,255,.45) !important; border-right: .5px solid var(--hair);
  backdrop-filter: blur(30px) saturate(180%); -webkit-backdrop-filter: blur(30px) saturate(180%);
}

/* ---------- glass containers: any st.container(key="glass…") ---------- */
[class*="st-key-glass"] {
  background: var(--glass); border-radius: var(--r-xl); padding: 22px 24px 20px;
  border: 1px solid var(--stroke); box-shadow: var(--shadow);
  backdrop-filter: blur(28px) saturate(190%); -webkit-backdrop-filter: blur(28px) saturate(190%);
}
[class*="st-key-glasstight"] { padding: 14px 16px; border-radius: var(--r-lg); }
[class*="st-key-glassalert"] { background: linear-gradient(135deg, rgba(255,59,48,.16), rgba(255,149,0,.10)), var(--glass); border-color: rgba(255,59,48,.35); }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { border-radius: var(--r-lg); }

/* ---------- type ---------- */
h1, h2, h3, h4 { font-family: var(--font) !important; color: var(--ink) !important; letter-spacing: -.02em; }
h1 { font-weight: 800 !important; }
h3 { font-size: 1.15rem !important; font-weight: 700 !important; }
p, li, label, .stMarkdown { color: var(--ink); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--ink2) !important; }
.ms { font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1; vertical-align: -0.18em;
      font-size: 1.15em; display: inline-block; -webkit-font-smoothing: antialiased; }

/* ---------- buttons: pills ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  border-radius: 999px !important; padding: .55rem 1.2rem !important; font-weight: 600 !important; min-height: 44px;
  transition: transform .15s ease, box-shadow .2s ease, background .2s ease;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: rgba(255,255,255,.72) !important; color: var(--ink) !important;
  border: .5px solid rgba(0,0,0,.08) !important; box-shadow: 0 1px 2px rgba(0,0,0,.05), inset 0 0 0 .5px var(--stroke);
  backdrop-filter: blur(20px);
}
[data-testid="stBaseButton-secondary"]:hover { background: #fff !important; transform: translateY(-1px); }
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: linear-gradient(180deg, var(--accent2), var(--accent)) !important; color: #fff !important; border: none !important;
  box-shadow: 0 8px 20px -6px var(--accent), inset 0 1px 0 rgba(255,255,255,.35) !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover { transform: translateY(-1px) scale(1.01); filter: brightness(1.05); }
button:active { transform: scale(.97) !important; }
button:disabled { opacity: .45 !important; box-shadow: none !important; transform: none !important; }
[class*="st-key-danger"] button, [class*="st-key-danger"] button p { color: #FF3B30 !important; }

[data-testid="stPageLink"] a { justify-content: center; border-radius: 999px; min-height: 44px; background: rgba(255,255,255,.72);
  border: .5px solid rgba(0,0,0,.08); box-shadow: 0 1px 2px rgba(0,0,0,.05); }
[data-testid="stPageLink"] a:hover { background: #fff; }
[data-testid="stPageLink"] a p { font-weight: 600; }

/* ---------- inputs ---------- */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, .stTextArea textarea {
  border-radius: 14px !important; background: rgba(255,255,255,.75) !important; border-color: rgba(0,0,0,.06) !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within { box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 22%, transparent) !important; border-color: var(--accent) !important; }
[data-testid="stChatInput"] {
  border-radius: 999px !important; background: rgba(255,255,255,.8) !important; border: 1px solid var(--stroke) !important;
  box-shadow: 0 12px 34px -10px rgba(31,38,135,.28) !important; backdrop-filter: blur(24px);
}
[data-testid="stChatInput"] textarea { background: transparent !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--accent) !important; border-radius: 999px !important; color: #fff !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }

/* toggle = iOS switch */
[data-testid="stCheckbox"]:has(input[role="switch"]) label { align-items: center; gap: 4px; }
[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type {
  width: 51px !important; height: 31px !important; flex: 0 0 51px; border-radius: 999px !important; background: rgba(120,120,128,.18) !important;
  position: relative; padding: 0 !important; margin-right: 8px; transition: background .25s ease; border: none !important; }
[data-testid="stCheckbox"][data-selected="true"]:has(input[role="switch"]) label > div:first-of-type { background: #34C759 !important; }
[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type > div {
  position: absolute !important; top: 2px; left: 2px; width: 27px !important; height: 27px !important; border-radius: 50% !important;
  background: #fff !important; margin: 0 !important; transform: none !important;
  box-shadow: 0 3px 8px rgba(0,0,0,.15), 0 3px 1px rgba(0,0,0,.06); transition: left .28s cubic-bezier(.3,1.35,.6,1); }
[data-testid="stCheckbox"][data-selected="true"]:has(input[role="switch"]) label > div:first-of-type > div { left: 22px; }
[data-testid="stCheckbox"] p { font-weight: 550; }

/* segmented control & tabs as iOS segmented pickers */
[data-testid="stButtonGroup"] > div, [data-testid="stTabs"] [role="tablist"] {
  background: rgba(118,118,128,.12); padding: 3px; border-radius: 12px; gap: 2px !important; width: fit-content; border: none;
}
[data-testid="stButtonGroup"] button { border: none !important; border-radius: 9px !important; background: transparent !important; font-weight: 600 !important; min-height: 32px; }
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: #fff !important; box-shadow: 0 3px 8px rgba(0,0,0,.12), 0 1px 1px rgba(0,0,0,.04) !important; color: var(--ink) !important;
}
[data-testid="stTabs"] [role="tablist"] { border-bottom: none !important; margin-bottom: 14px; }
[data-testid="stTab"] { border-radius: 9px !important; padding: 6px 16px !important; height: auto !important; margin: 0 !important; }
[data-testid="stTab"] p { font-weight: 600 !important; font-size: .9rem !important; }
[data-testid="stTab"][aria-selected="true"] { background: #fff !important; box-shadow: 0 3px 8px rgba(0,0,0,.12), 0 1px 1px rgba(0,0,0,.04); }
[data-testid="stTab"][aria-selected="true"] p { color: var(--ink) !important; }
[data-testid="stTabs"] .react-aria-SelectionIndicator { display: none !important; }
[data-testid="stTabs"] [role="tablist"]::after, [data-testid="stTabs"] [role="tablist"]::before { display: none !important; }

/* radio as an iOS inset grouped list (used for the case inbox) */
.st-key-inbox [role="radiogroup"] { gap: 8px !important; }
.st-key-inbox [role="radiogroup"] > div {
  background: rgba(255,255,255,.62); border: 1px solid var(--stroke); border-radius: 18px; padding: 11px 14px; margin: 0 !important;
  width: 100%; box-shadow: 0 1px 2px rgba(0,0,0,.04); transition: all .18s ease; cursor: pointer;
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
.st-key-inbox [role="radiogroup"] > div:hover { background: rgba(255,255,255,.92); transform: translateX(2px); }
.st-key-inbox [role="radiogroup"] > div[data-selected="true"] { background: #fff; box-shadow: 0 0 0 2px var(--accent), 0 12px 26px -12px var(--accent); }
.st-key-inbox [data-testid="stRadioOption"] { width: 100%; }
.st-key-inbox [data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
.st-key-inbox [data-testid="stRadioOption"] p { font-weight: 650; font-size: .95rem; }
.st-key-inbox [data-testid="stRadioCaption"] { padding-left: 0 !important; margin-left: 0 !important; }
.st-key-inbox [data-testid="stRadioCaption"] p { font-size: .8rem; color: var(--ink3) !important; }

/* alerts */
[data-testid="stAlert"] > div { border-radius: 18px !important; border: 1px solid var(--stroke); backdrop-filter: blur(20px); }
/* metrics, dataframes, expanders */
[data-testid="stMetric"] { background: var(--glass); border: 1px solid var(--stroke); border-radius: var(--r-lg); padding: 14px 18px; box-shadow: var(--shadow); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 18px; overflow: hidden; border: 1px solid var(--stroke); box-shadow: var(--shadow); }
[data-testid="stExpander"] details { border-radius: 18px !important; background: var(--glass); border: 1px solid var(--stroke) !important; }
[data-testid="stProgress"] > div > div { border-radius: 999px; }
[data-testid="stProgress"] [role="progressbar"] > div > div > div { background: linear-gradient(90deg, var(--accent2), var(--accent)) !important; }
[data-testid="stSlider"] [role="slider"] { background: #fff !important; box-shadow: 0 2px 8px rgba(0,0,0,.25); border: none; width: 22px; height: 22px; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; }

/* ---------- custom HTML pieces ---------- */
.hero { text-align: __HERO_ALIGN__; margin: 4px 0 26px; animation: rise .5s cubic-bezier(.2,.8,.2,1) both; }
.hero .eyebrow { display: inline-flex; align-items: center; gap: 6px; font-size: .78rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: var(--accent); background: rgba(255,255,255,.7); padding: 5px 12px; border-radius: 999px;
  border: 1px solid var(--stroke); box-shadow: 0 2px 10px -4px rgba(0,0,0,.12); }
.hero h1 { font-size: clamp(2rem, 5vw, 3.1rem); line-height: 1.05; margin: 14px 0 8px; padding: 0;
  background: linear-gradient(135deg, #1d1d1f 30%, var(--accent) 120%); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.hero p { color: var(--ink2); font-size: 1.07rem; margin: __HERO_PM__; max-width: 560px; }
@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

.steps { display: flex; gap: 6px; justify-content: center; margin: -8px 0 22px; flex-wrap: wrap; }
.steps .s { display: flex; align-items: center; gap: 6px; padding: 6px 12px 6px 6px; border-radius: 999px; font-size: .82rem; font-weight: 600;
  color: var(--ink3); background: rgba(255,255,255,.45); border: 1px solid rgba(255,255,255,.6); }
.steps .s i { font-style: normal; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: .75rem;
  background: rgba(118,118,128,.16); color: var(--ink2); }
.steps .s.on { color: var(--ink); background: rgba(255,255,255,.85); box-shadow: 0 4px 14px -6px rgba(0,0,0,.2); }
.steps .s.on i { background: var(--accent); color: #fff; }
.steps .s.done i { background: #34C759; color: #fff; }

.row { display: flex; gap: 14px; align-items: flex-start; padding: 12px 0; border-bottom: .5px solid var(--hair); }
.row:last-child { border-bottom: none; }
.row .ic { flex: 0 0 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: #fff; font-size: 19px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.35); }
.row .tx > b { display: block; font-weight: 650; margin-bottom: 2px; }
.row .tx > span { color: var(--ink2); font-size: .93rem; line-height: 1.4; }

.pill { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 999px; font-size: .76rem; font-weight: 700;
  letter-spacing: .01em; white-space: nowrap; }
.pill .ms { font-size: 14px; }
.dot { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%; display: inline-block; }

.bubbles { display: flex; flex-direction: column; gap: 8px; padding: 4px 2px; }
.b { max-width: 82%; padding: 10px 15px; border-radius: 22px; line-height: 1.42; font-size: .99rem; animation: pop .28s cubic-bezier(.2,.9,.3,1.2) both;
  white-space: pre-wrap; word-wrap: break-word; }
.b.me { align-self: flex-end; color: #fff; background: linear-gradient(180deg, #2E9BFF, #007AFF); border-bottom-right-radius: 7px;
  box-shadow: 0 6px 16px -8px #007AFF; }
.b.ai { align-self: flex-start; background: rgba(255,255,255,.85); color: var(--ink); border-bottom-left-radius: 7px;
  border: 1px solid var(--stroke); box-shadow: 0 4px 14px -8px rgba(0,0,0,.18); }
.b.sys { align-self: center; background: transparent; color: var(--ink3); font-size: .78rem; padding: 2px 8px; }
.who { font-size: .72rem; color: var(--ink3); font-weight: 600; margin: 4px 8px -4px; }
.who.r { align-self: flex-end; }
@keyframes pop { from { opacity: 0; transform: translateY(6px) scale(.97); } to { opacity: 1; transform: none; } }

.quote { position: relative; padding: 12px 16px 12px 18px; margin: 8px 0; border-radius: 16px; background: rgba(255,255,255,.7);
  border: 1px solid var(--stroke); font-size: .98rem; line-height: 1.45; }
.quote::before { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 4px; border-radius: 4px; background: var(--qc, var(--accent)); }
.quote .meta { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 4px 0 18px; }
.kpi { background: var(--glass); border: 1px solid var(--stroke); border-radius: 22px; padding: 14px 16px; box-shadow: var(--shadow);
  backdrop-filter: blur(24px) saturate(180%); -webkit-backdrop-filter: blur(24px) saturate(180%); position: relative; overflow: hidden; }
.kpi .l { display: flex; align-items: center; gap: 6px; font-size: .8rem; font-weight: 600; color: var(--ink2); }
.kpi .l .ms { color: var(--c); font-size: 18px; }
.kpi .v { font-size: 2rem; font-weight: 800; letter-spacing: -.03em; margin-top: 6px; color: var(--ink); font-variant-numeric: tabular-nums; }
.kpi .s { font-size: .78rem; color: var(--ink3); margin-top: 2px; }
.kpi::after { content: ""; position: absolute; right: -30px; top: -30px; width: 90px; height: 90px; border-radius: 50%; background: var(--c); opacity: .12; }

.sec { display: flex; align-items: center; gap: 10px; margin: 6px 0 12px; }
.sec .n { width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center; color: #fff; font-weight: 800; font-size: .85rem; background: var(--accent); }
.sec h3 { margin: 0 !important; padding: 0 !important; }
.sec .sub { color: var(--ink2); font-size: .88rem; margin-left: auto; }

.lockcard { text-align: center; padding: 30px 10px; color: var(--ink2); }
.lockcard .ms { font-size: 44px; color: var(--ink3); display: block; margin-bottom: 8px; }

.banner { display: flex; gap: 10px; align-items: center; padding: 10px 14px; border-radius: 16px; font-size: .9rem; font-weight: 550;
  background: rgba(255,149,0,.14); border: 1px solid rgba(255,149,0,.35); color: #8a4b00; margin-bottom: 14px; }

.helpgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.help { display: flex; gap: 10px; align-items: center; padding: 12px 14px; border-radius: 18px; background: rgba(255,255,255,.7); border: 1px solid var(--stroke); }
.help .ic { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; color: #fff; background: #34C759; font-size: 20px; flex: 0 0 36px; }
.help b { display: block; font-size: .93rem; }
.help span { font-size: .8rem; color: var(--ink2); }

.crisis { text-align: center; padding: 26px 18px; border-radius: 30px; color: #fff;
  background: linear-gradient(160deg, #FF5E57 0%, #FF3B30 45%, #C7202A 100%); box-shadow: 0 24px 50px -18px rgba(255,59,48,.65); margin: 10px 0 16px; }
.crisis .ms { font-size: 46px; }
.crisis h2 { color: #fff !important; margin: 6px 0 4px; font-size: 1.5rem; }
.crisis p { color: rgba(255,255,255,.92); margin: 4px 0; }
.crisis .call { display: inline-flex; align-items: center; gap: 8px; margin: 12px 6px 0; padding: 10px 20px; border-radius: 999px;
  background: rgba(255,255,255,.95); color: #C7202A; font-weight: 800; font-size: 1.05rem; text-decoration: none; }

.success { text-align: center; padding: 10px 6px 4px; }
.success .check { width: 84px; height: 84px; margin: 0 auto 10px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-size: 48px;
  background: linear-gradient(180deg, #4CD964, #34C759); box-shadow: 0 18px 36px -12px #34C759; animation: pop .45s cubic-bezier(.2,.9,.3,1.4) both; }
.ref { display: inline-block; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 1.25rem; letter-spacing: .12em; font-weight: 700;
  padding: 10px 18px; border-radius: 14px; background: rgba(118,118,128,.12); margin: 8px 0; }

.timeline { position: relative; margin: 6px 0 0 6px; padding-left: 22px; }
.timeline::before { content: ""; position: absolute; left: 6px; top: 6px; bottom: 6px; width: 2px; background: rgba(118,118,128,.2); border-radius: 2px; }
.tl { position: relative; padding: 4px 0 14px; }
.tl::before { content: ""; position: absolute; left: -21px; top: 7px; width: 12px; height: 12px; border-radius: 50%; background: #d1d1d6; border: 2px solid #fff; }
.tl.on::before { background: var(--accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 25%, transparent); }
.tl.done::before { background: #34C759; }
.tl > b { display: block; } .tl > span { color: var(--ink2); font-size: .9rem; }

.signin { text-align: center; margin-bottom: 8px; }
.signin .appicon { width: 76px; height: 76px; border-radius: 20px; margin: 0 auto 12px; display: grid; place-items: center; color: #fff; font-size: 40px;
  background: linear-gradient(160deg, var(--accent2), var(--accent)); box-shadow: 0 16px 30px -12px var(--accent), inset 0 1px 0 rgba(255,255,255,.4); }
.profile { display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 18px; background: rgba(255,255,255,.65); border: 1px solid var(--stroke); }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 800;
  background: linear-gradient(160deg, var(--accent2), var(--accent)); }
.mini { font-size: .78rem; color: var(--ink3); }
.status-row { display: grid; grid-template-columns: 14px minmax(120px, 160px) 1fr; align-items: center; gap: 10px; padding: 11px 2px; border-bottom: .5px solid var(--hair); }
.status-row:last-child { border-bottom: none; }
.status-row b { font-weight: 650; }
.status-row span.mono { color: var(--ink2); font-size: .82rem; word-break: break-word; }
.mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .85rem; }
</style>
"""

THEMES = {
    # student app: calm blue/teal
    "student": dict(ACCENT="#007AFF", ACCENT2="#3BA0FF", BG1="#c9e3ff", BG2="#e3dcff", BG3="#d4f5ee",
                    BLOB1="#7cc4ff", BLOB2="#c4b5fd", MAXW="760px", HERO_ALIGN="center", HERO_PM="0 auto"),
    # staff portal: indigo, wider
    "staff": dict(ACCENT="#5856D6", ACCENT2="#7D7AFF", BG1="#dcdcff", BG2="#ffe0ef", BG3="#d6ecff",
                  BLOB1="#a5b4fc", BLOB2="#f9a8d4", MAXW="1320px", HERO_ALIGN="left", HERO_PM="0"),
}


def inject_theme(kind: str = "student") -> None:
    css = _CSS
    for k, v in THEMES[kind].items():
        css = css.replace(f"__{k}__", v)
    st.markdown(css, unsafe_allow_html=True)


def ms(name: str) -> str:
    """A Material Symbols Rounded icon (closest free match to SF Symbols)."""
    return f'<span class="ms">{name}</span>'


def html_block(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", eyebrow: str = "", icon: str = "") -> None:
    eb = f'<span class="eyebrow">{ms(icon) if icon else ""}{esc(eyebrow)}</span>' if eyebrow else ""
    html_block(f'<div class="hero">{eb}<h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>')


def steps(labels: list[str], current: int) -> None:
    parts = []
    for i, lab in enumerate(labels):
        cls = "on" if i == current else ("done" if i < current else "")
        mark = "✓" if i < current else str(i + 1)
        parts.append(f'<div class="s {cls}"><i>{mark}</i>{esc(lab)}</div>')
    html_block(f'<div class="steps">{"".join(parts)}</div>')


def row(icon: str, color: str, title: str, text: str) -> str:
    return (f'<div class="row"><div class="ic" style="background:{color}">{ms(icon)}</div>'
            f'<div class="tx"><b>{esc(title)}</b><span>{text}</span></div></div>')


def pill(text: str, color: str, icon: str = "", solid: bool = False) -> str:
    style = f"background:{color};color:#fff" if solid else f"background:{color}1f;color:{color}"
    return f'<span class="pill" style="{style}">{ms(icon) if icon else ""}{esc(text)}</span>'


def route_pill(route: str | None, solid: bool = False) -> str:
    if not route:
        return pill("Intake", GRAY)
    color, label, icon = ROUTE_STYLE.get(route, (GRAY, route, "inbox"))
    return pill(label, color, icon, solid)


def status_pill(status: str) -> str:
    color, label = STATUS_STYLE.get(status, (GRAY, status))
    return pill(label, color)


def urgency_pill(level: str) -> str:
    color = {"high": RED, "sensitive": ORANGE}.get(level, GREEN)
    return pill(level.capitalize(), color)


def bubbles(turns: list[tuple[str, str]], me_label: str = "You", ai_label: str = "Intake assistant") -> str:
    """turns: (role, text) with role in student/assistant/system. Text is escaped here."""
    out, last = [], None
    for role, text in turns:
        if role == "student":
            if last != "student":
                out.append(f'<div class="who r">{esc(me_label)}</div>')
            out.append(f'<div class="b me">{esc(text)}</div>')
        elif role == "assistant":
            if last != "assistant":
                out.append(f'<div class="who">{esc(ai_label)}</div>')
            out.append(f'<div class="b ai">{esc(text)}</div>')
        else:
            out.append(f'<div class="b sys">{esc(text)}</div>')
        last = role
    return f'<div class="bubbles">{"".join(out)}</div>'


def quote(text: str, meta: str = "", color: str = "") -> str:
    style = f' style="--qc:{color}"' if color else ""
    m = f'<div class="meta">{meta}</div>' if meta else ""
    return f'<div class="quote"{style}>“{esc(text)}”{m}</div>'


def kpis(items: list[tuple[str, str, str, str, str]]) -> None:
    """items: (icon, colour, label, value, sub)."""
    cells = "".join(f'<div class="kpi" style="--c:{c}"><div class="l">{ms(i)}{esc(lab)}</div>'
                    f'<div class="v">{esc(str(v))}</div><div class="s">{esc(sub)}</div></div>' for i, c, lab, v, sub in items)
    html_block(f'<div class="kpis">{cells}</div>')


def section(num: str, title: str, sub: str = "", color: str = "") -> None:
    st_ = f' style="background:{color}"' if color else ""
    badge = f'<div class="n"{st_}>{esc(num)}</div>' if num else ""
    html_block(f'<div class="sec">{badge}<h3>{esc(title)}</h3>'
               f'<span class="sub">{esc(sub)}</span></div>')


def help_contacts(contacts: str) -> str:
    cells = []
    for part in [p.strip() for p in contacts.split("|") if p.strip()]:
        name, _, number = part.partition(":")
        cells.append(f'<div class="help"><div class="ic">{ms("call")}</div><div><b>{esc(number.strip() or name)}</b>'
                     f'<span>{esc(name.strip() if number else "Support")}</span></div></div>')
    return f'<div class="helpgrid">{"".join(cells)}</div>'


def ago(when: datetime) -> str:
    from grievance_agent.store import utcnow
    now = utcnow()
    if when.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    s = max(0, int((now - when).total_seconds()))
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    return when.strftime("%d %b")


def mock_banner(settings) -> None:
    if settings.llm_backend == "mock":
        html_block(f'<div class="banner">{ms("science")} Demo mode: replies come from a test stand-in, not Qwen. '
                   'Use the normal launcher for real results.</div>')
