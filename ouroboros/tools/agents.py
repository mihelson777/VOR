"""Tools: spawn_agents — multi-agent swarm for complex tasks."""

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.swarm import Swarm, format_swarm_result


def _spawn_agents(ctx: ToolContext, task: str) -> str:
    """
    Run a multi-agent pipeline (Planner → Researcher/Coder/Critic) for complex tasks.
    Use when the task requires: research + synthesis, code + review, or multi-step analysis.
    """
    agent = getattr(ctx, "agent", None)
    if not agent:
        return "ERROR: spawn_agents requires agent context (not available in this mode)."

    from ouroboros.llm import LLMClient
    llm_client = LLMClient()

    def llm_fn(messages: list, system: str) -> str:
        full = [{"role": "system", "content": system}] + messages
        msg, _ = llm_client.chat(messages=full, tools=None)
        return (msg.get("content") or "").strip()

    def tool_executor(tool_name: str, kwargs: dict) -> str:
        return str(agent.tools.execute(tool_name, kwargs))

    available_tools = list(agent.tools._entries.keys())
    emit_fn = getattr(ctx, "emit_progress_fn", None) or (lambda _: None)

    def emit(name: str, msg: str) -> None:
        try:
            emit_fn(name, msg)
        except TypeError:
            emit_fn(name)

    swarm = Swarm(
        llm_fn=llm_fn,
        tool_executor=tool_executor,
        available_tools=available_tools,
        emit_progress=emit,
    )
    result = swarm.run(task)
    return format_swarm_result(result)


def get_tools() -> list:
    return [
        ToolEntry("spawn_agents", {
            "name": "spawn_agents",
            "description": "Run multi-agent pipeline for complex tasks: Planner breaks task into subtasks, "
                           "Researcher/Coder/Critic execute them, VOR synthesizes. Use for: research + report, "
                           "code + review, multi-step analysis.",
            "parameters": {
                "type": "object",
                "properties": {"task": {"type": "string", "description": "The complex task to accomplish"}},
                "required": ["task"],
            },
        }, _spawn_agents),
    ]
