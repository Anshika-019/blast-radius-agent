"""docker-compose.yml ko FalkorDB graph mein convert karta hai.

Schema:
  (:Service {name, tier, image})-[:DEPENDS_ON]->(:Service)
  (:Team)-[:OWNS]->(:Service)
  (:Person)-[:MEMBER_OF]->(:Team)
  (:Analysis {summary, ts})-[:ABOUT]->(:Service)   # agent ki memory
"""
import sys
import yaml
from db import get_graph

# Demo ke liye team members. Real project mein CODEOWNERS file se parse karo.
TEAMS = {
    "platform": ["Aarav", "Meera"],
    "identity": ["Kabir", "Sana"],
    "payments": ["Rohan", "Ishita"],
    "checkout": ["Vikram"],
    "catalog": ["Neha"],
    "growth": ["Arjun"],
    "web": ["Priya", "Dev"],
}

def _labels(spec):
    raw = spec.get("labels") or {}
    if isinstance(raw, list):  # "key=value" format
        raw = dict(item.split("=", 1) for item in raw if "=" in item)
    return raw

def _deps(spec):
    deps = spec.get("depends_on") or []
    return list(deps.keys()) if isinstance(deps, dict) else deps

def build(compose_path, reset=True):
    g = get_graph()
    if reset:
        try:
            g.delete()
        except Exception:
            pass  # graph abhi exist nahi karta
        g = get_graph()

    services = yaml.safe_load(open(compose_path))["services"]

    for name, spec in services.items():
        lb = _labels(spec)
        g.query("MERGE (s:Service {name: $name}) SET s.tier = $tier, s.image = $image",
                {"name": name, "tier": int(lb.get("tier", 3)), "image": spec.get("image", "")})
        if lb.get("team"):
            g.query("MERGE (t:Team {name: $team}) WITH t "
                    "MATCH (s:Service {name: $name}) MERGE (t)-[:OWNS]->(s)",
                    {"team": lb["team"], "name": name})

    for name, spec in services.items():
        for dep in _deps(spec):
            g.query("MATCH (a:Service {name: $a}), (b:Service {name: $b}) "
                    "MERGE (a)-[:DEPENDS_ON]->(b)", {"a": name, "b": dep})

    for team, members in TEAMS.items():
        for person in members:
            g.query("MATCH (t:Team {name: $team}) MERGE (p:Person {name: $p}) "
                    "MERGE (p)-[:MEMBER_OF]->(t)", {"team": team, "p": person})

    count = g.query("MATCH (s:Service) RETURN count(s)").result_set[0][0]
    return count

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "demo/docker-compose.yml"
    print(f"Graph ready: {build(path)} services loaded")
