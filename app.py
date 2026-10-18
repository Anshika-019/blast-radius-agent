"""Streamlit demo: sawal poocho, answer pao, aur graph pe blast radius dekho."""
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from agent import run_agent
from graph_builder import build
from tools import full_graph, blast_radius, find_owners

DOWN, HIT, CALM, EDGE_HIT, EDGE = "#FF4B4B", "#F2A900", "#8A97A8", "#FF4B4B", "#3A4250"

st.set_page_config(page_title="Blast Radius Agent", layout="wide")
st.title("Blast Radius Agent")
st.caption("Poochiye kaunsi service fail hui hai. Agent graph traverse karke batayega kya tootega, kisko alert karna hai, aur kyun.")

with st.sidebar:
    st.subheader("Infrastructure")
    path = st.text_input("docker-compose path", "demo/docker-compose.yml")
    if st.button("Load into graph"):
        try:
            st.success(f"{build(path)} services loaded")
        except Exception as e:
            st.error(f"Graph load nahi hua: {e}. Kya FalkorDB port 6379 pe chal raha hai?")

def draw(down=None, affected=(), paths=()):
    nodes, edges = full_graph()
    hot_edges = {(p[i], p[i + 1]) for p in paths for i in range(len(p) - 1)}
    net = Network(height="560px", width="100%", directed=True,
                  bgcolor="#0E1117", font_color="#FAFAFA")
    net.barnes_hut(spring_length=180)
    for name, tier, team in nodes:
        color = DOWN if name == down else HIT if name in affected else CALM
        net.add_node(name, label=name, color=color, size=40 - 8 * (tier or 3),
                     font={"size": 22, "color": "#FAFAFA"},
                     title=f"team: {team} | tier {tier}")
    for a, b in edges:
        hot = (a, b) in hot_edges
        net.add_edge(a, b, color=EDGE_HIT if hot else EDGE, width=4 if hot else 1.5)
    components.html(net.generate_html(), height=580)

q = st.text_input("Kya hua hai?", "auth-service down ho gaya hai. Kya kya tootega aur kisko alert karun?")
if st.button("Analyze", type="primary"):
    try:
        with st.spinner("Graph traverse ho raha hai..."):
            answer, trace = run_agent(q)
    except Exception:
        st.warning("LLM abhi available nahi hai (quota ya network). Seedha graph se answer dikha rahe hain.")
        names = [n[0] for n in full_graph()[0]]
        down = next((n for n in names if n in q), None)
        if not down:
            st.error("Sawal mein service ka naam likho, jaise auth-service.")
            st.stop()
        br_out = blast_radius(down)
        aff = br_out["affected"]
        owners = find_owners([down] + [a["service"] for a in aff if a["tier"] == 1])
        trace = [{"tool": "blast_radius", "input": {"service": down}, "output": br_out},
                 {"tool": "find_owners", "input": {"services": [down]}, "output": owners}]
        lines = [f"**{down} down hai. {len(aff)} services affected:**"]
        lines += [f"- `{a['service']}` (tier {a['tier']}): {' -> '.join(a['path'])}" for a in aff]
        lines += ["", "**Kisko alert karein:**"]
        lines += [f"- `{o['service']}`: {o['team']} ({', '.join(o['people'])})" for o in owners]
        answer = "\n".join(lines)
    br = next((t for t in trace if t["tool"] == "blast_radius"), None)
    left, right = st.columns([3, 2])
    with left:
        if br:
            aff = br["output"].get("affected", [])
            draw(br["output"]["down"], {a["service"] for a in aff}, [a["path"] for a in aff])
        else:
            draw()
    with right:
        st.markdown(answer)
        with st.expander(f"Agent ka reasoning trace ({len(trace)} graph calls)"):
            for t in trace:
                st.code(f"{t['tool']}({t['input']})")
                st.json(t["output"], expanded=False)
else:
    try:
        draw()
    except Exception:
        st.info("Pehle sidebar se 'Load into graph' dabao.")
