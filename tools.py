"""Graph queries jo agent tools ki tarah call karta hai.
Har tool plain Python data return karta hai taaki UI path highlight kar sake."""
import time
from datetime import datetime
from db import get_graph

def blast_radius(service: str, max_hops: int = 8):
    """Agar `service` down ho jaye toh kaun kaun si services tootengi (transitively)."""
    rows = get_graph().query(
        f"MATCH p = (s:Service)-[:DEPENDS_ON*1..{int(max_hops)}]->(t:Service {{name: $name}}) "
        "RETURN s.name, s.tier, length(p), [n IN nodes(p) | n.name] ORDER BY length(p)",
        {"name": service}).result_set
    best = {}
    for name, tier, hops, path in rows:  # har service ka sabse chhota path rakho
        if name not in best:
            best[name] = {"service": name, "tier": tier, "hops": hops, "path": path}
    return {"down": service, "affected": list(best.values())}

def find_owners(services: list):
    """Services ki owning team aur unke members."""
    rows = get_graph().query(
        "MATCH (t:Team)-[:OWNS]->(s:Service) WHERE s.name IN $names "
        "OPTIONAL MATCH (p:Person)-[:MEMBER_OF]->(t) "
        "RETURN s.name, t.name, collect(p.name)", {"names": services}).result_set
    return [{"service": s, "team": t, "people": p} for s, t, p in rows]

def dependency_path(source: str, target: str):
    """Do services ke beech sabse chhota dependency chain."""
    rows = get_graph().query(
        "MATCH (a:Service {name: $a}), (b:Service {name: $b}) "
        "WITH shortestPath((a)-[:DEPENDS_ON*]->(b)) AS p "
        "RETURN [n IN nodes(p) | n.name]", {"a": source, "b": target}).result_set
    return {"path": rows[0][0] if rows and rows[0][0] else []}

def most_critical(limit: int = 5):
    """Wo services jinpe sabse zyada services depend karti hain (single points of failure)."""
    rows = get_graph().query(
        "MATCH (s:Service)-[:DEPENDS_ON*1..8]->(t:Service) "
        "RETURN t.name, t.tier, count(DISTINCT s) AS deps ORDER BY deps DESC LIMIT $lim",
        {"lim": int(limit)}).result_set
    return [{"service": n, "tier": tier, "dependents": d} for n, tier, d in rows]

def remember_analysis(service: str, summary: str):
    """Analysis ko graph memory mein save karo, taaki agla session use yaad rakhe."""
    get_graph().query(
        "MATCH (s:Service {name: $name}) "
        "CREATE (:Analysis {summary: $summary, ts: $ts, date: $date})-[:ABOUT]->(s)",
        {"name": service, "summary": summary, "ts": int(time.time()),
         "date": datetime.now().strftime("%d %b %Y, %I:%M %p")})
    return {"saved": True}

def past_analyses(service: str):
    """Is service ke baare mein pichle sessions ke notes."""
    rows = get_graph().query(
        "MATCH (a:Analysis)-[:ABOUT]->(s:Service {name: $name}) "
        "RETURN a.summary, a.date ORDER BY a.ts DESC LIMIT 5", {"name": service}).result_set
    return [{"summary": s, "date": d} for s, d in rows]

def full_graph():
    """UI visualization ke liye saari services aur edges."""
    g = get_graph()
    nodes = g.query("MATCH (s:Service) OPTIONAL MATCH (t:Team)-[:OWNS]->(s) "
                    "RETURN s.name, s.tier, t.name").result_set
    edges = g.query("MATCH (a:Service)-[:DEPENDS_ON]->(b:Service) "
                    "RETURN a.name, b.name").result_set
    return nodes, edges

TOOL_FUNCS = {f.__name__: f for f in
              [blast_radius, find_owners, dependency_path, most_critical,
               remember_analysis, past_analyses]}
