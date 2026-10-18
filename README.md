# Blast Radius Agent

An SRE agent that answers "what breaks if this service goes down?" by traversing a
FalkorDB dependency graph, then tells you who to alert and shows the exact path behind
every claim. It remembers past analyses across sessions in the same graph.

## Run it

```bash
# 1. FalkorDB (Browser bhi milta hai: http://localhost:3000)
docker run -p 6379:6379 -p 3000:3000 -it --rm falkordb/falkordb:latest

# 2. Setup
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...

# 3. Graph load karo aur CLI test karo
python graph_builder.py demo/docker-compose.yml
python agent.py

# 4. UI
streamlit run app.py
```

## Graph schema

```
(:Person)-[:MEMBER_OF]->(:Team)-[:OWNS]->(:Service)-[:DEPENDS_ON]->(:Service)
(:Analysis {summary, ts})-[:ABOUT]->(:Service)
```

## Why a graph

Blast radius is a multi-hop question: frontend breaks because api-gateway depends on
order-service, which depends on payment-service, which depends on auth-service. The agent
gets this in one variable-length traversal instead of stitching records together.

## Demo questions

- auth-service down ho gaya hai. Kya kya tootega aur kisko alert karun?
- Hamare system ke sabse bade single points of failure kaunse hain?
- frontend se kafka tak dependency chain kya hai?
