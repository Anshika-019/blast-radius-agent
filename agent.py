import json
import os
from tools import TOOL_FUNCS

SYSTEM = """You are an SRE incident agent. The infrastructure is stored in a FalkorDB graph.
Never guess dependencies: always call graph tools and base every claim on their results.
For outage questions: 1) check past_analyses, 2) call blast_radius, 3) call find_owners
for the affected tier-1 services, 4) give a prioritized action plan, 5) call
remember_analysis with a one-line summary. Cite the dependency path for each affected
service, like: frontend -> api-gateway -> auth-service. Reply in the user's language.
If past_analyses returns notes, start your answer with a short "Memory" section that says
how many times this service failed before and what was learned, with dates."""

TOOLS = [
    {"name": "blast_radius", "description": "Services that break (directly or transitively) if the given service goes down, with hop count and path.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}},
    {"name": "find_owners", "description": "Owning team and people for a list of services.",
     "input_schema": {"type": "object", "properties": {"services": {"type": "array", "items": {"type": "string"}}}, "required": ["services"]}},
    {"name": "dependency_path", "description": "Shortest dependency chain from source service to target service.",
     "input_schema": {"type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"}}, "required": ["source", "target"]}},
    {"name": "most_critical", "description": "Services with the most transitive dependents (single points of failure).",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "remember_analysis", "description": "Save a one-line analysis summary about a service to long-term graph memory.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}, "summary": {"type": "string"}}, "required": ["service", "summary"]}},
    {"name": "past_analyses", "description": "Notes from previous sessions about a service.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}},
]

def _call_tool(name, args, trace):
    try:
        out = TOOL_FUNCS[name](**(args or {}))
    except Exception as e:
        out = {"error": str(e)}
    out = json.loads(json.dumps(out, default=str))
    trace.append({"tool": name, "input": args or {}, "output": out})
    return out

def _upper_types(schema):
    if isinstance(schema, dict):
        return {k: (v.upper() if k == "type" else _upper_types(v)) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_upper_types(x) for x in schema]
    return schema

def _run_gemini(question, max_turns):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                       parameters=_upper_types(t["input_schema"])) for t in TOOLS]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    model = os.getenv("MODEL", "gemini-2.5-flash")
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]
    trace = []
    for _ in range(max_turns):
        resp = client.models.generate_content(model=model, contents=contents, config=config)
        calls = resp.function_calls
        if not calls:
            return resp.text or "", trace
        contents.append(resp.candidates[0].content)
        parts = [types.Part.from_function_response(
                    name=fc.name, response={"result": _call_tool(fc.name, dict(fc.args or {}), trace)})
                 for fc in calls]
        contents.append(types.Content(role="user", parts=parts))
    return "Agent max turns tak pahunch gaya, sawal thoda specific karo.", trace

def _run_claude(question, max_turns):
    import anthropic

    client = anthropic.Anthropic()
    model = os.getenv("MODEL", "claude-sonnet-5-5")
    messages = [{"role": "user", "content": question}]
    trace = []
    for _ in range(max_turns):
        resp = client.messages.create(model=model, max_tokens=2000, system=SYSTEM,
                                      tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text"), trace
        results = [{"type": "tool_result", "tool_use_id": b.id,
                    "content": json.dumps(_call_tool(b.name, b.input, trace))}
                   for b in resp.content if b.type == "tool_use"]
        messages.append({"role": "user", "content": results})
    return "Agent max turns tak pahunch gaya, sawal thoda specific karo.", trace

def run_agent(question: str, max_turns: int = 10):
    if os.getenv("GEMINI_API_KEY"):
        return _run_gemini(question, max_turns)
    if os.getenv("ANTHROPIC_API_KEY"):
        return _run_claude(question, max_turns)
    raise RuntimeError("API key nahi mili. GEMINI_API_KEY ya ANTHROPIC_API_KEY set karo.")

if __name__ == "__main__":
    answer, trace = run_agent("auth-service down ho gaya hai. Kya kya tootega aur kisko alert karun?")
    for t in trace:
        print(f"[tool] {t['tool']}({t['input']})")
    print("\n" + answer)