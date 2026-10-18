import os
from falkordb import FalkorDB

GRAPH_NAME = os.getenv("GRAPH_NAME", "infra")

def get_graph():
    db = FalkorDB(host=os.getenv("FALKOR_HOST", "localhost"),
                  port=int(os.getenv("FALKOR_PORT", "6379")))
    return db.select_graph(GRAPH_NAME)
