"""
ouroboros/swarm.py — Multi-Agent Swarm for VOR

Architecture:
  VOR (orchestrator) → Planner → [Researcher, Coder, Critic, Custom...] → Critic → Result

Pipeline flow:
  1. Planner breaks task into subtasks
  2. VOR spawns specialized sub-agents per subtask
  3. Each sub-agent executes with its own tools + prompt
  4. Critic reviews all results
  5. VOR synthesizes final answer

Sub-agent types:
  - planner   : breaks complex tasks into steps
  - researcher: web search + fetch, returns findings
  - coder     : writes/edits code, returns code + explanation
  - critic    : reviews output, returns verdict + suggestions
  - custom    : VOR defines role + tools dynamically

Usage:
  from ouroboros.swarm import Swarm
  swarm = Swarm(llm_client, tools_registry)
  result = swarm.run("Build a web scraper for HackerNews")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("vor.swarm")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubTask:
    id: str
    agent_type: str          # planner | researcher | coder | critic | custom
    role: str                # human-readable role description
    instruction: str         # what this sub-agent must do
    tools: list[str]         # tool names this agent can use
    depends_on: list[str] = field(default_factory=list)  # task IDs
    result: str = ""
    status: str = "pending"  # pending | running | done | failed
    duration: float = 0.0


@dataclass
class SwarmResult:
    task: str
    subtasks: list[SubTask]
    final: str
    total_duration: float
    success: bool


# ---------------------------------------------------------------------------
# Sub-agent tool sets
# ---------------------------------------------------------------------------

AGENT_TOOLS: dict[str, list[str]] = {
    "planner":    [],  # planner only reasons, no tools
    "researcher": ["web_search", "fetch_url", "extract_links", "data_write"],
    "coder":      ["repo_read", "repo_list", "repo_edit", "repo_commit",
                   "repo_status", "shell_exec", "data_write"],
    "critic":     ["repo_read", "data_read"],
    "custom":     [],  # set dynamically
}

# ---------------------------------------------------------------------------
# Sub-agent system prompts
# ---------------------------------------------------------------------------

AGENT_PROMPTS: dict[str, str] = {
    "planner": """You are the Planner sub-agent of VOR.
Your ONLY job: break the given task into clear, sequential subtasks.

Output ONLY valid JSON — no markdown, no explanation outside the JSON:
{
  "subtasks": [
    {
      "id": "t1",
      "agent_type": "researcher|coder|critic|custom",
      "role": "short role description",
      "instruction": "detailed instruction for this sub-agent",
      "tools": ["tool1", "tool2"],
      "depends_on": []
    }
  ]
}

Rules:
- Use researcher for web search / information gathering
- Use coder for writing, editing, or running code
- Use critic as the LAST step to review everything
- Use custom for specialized one-off roles (specify role clearly)
- Keep subtasks focused — one responsibility each
- depends_on lists task IDs that must complete first
""",

    "researcher": """You are the Researcher sub-agent of VOR.
Your job: find information using web tools and return clear findings.

Available tools: web_search, fetch_url, extract_links, data_write

Workflow:
1. Search for relevant information
2. Fetch the most promising sources
3. Extract and organize key findings
4. Return a structured summary

Be thorough but concise. Cite sources (URLs). Save important findings with data_write if needed.
Return your findings as plain text — the orchestrator will use them.
""",

    "coder": """You are the Coder sub-agent of VOR.
Your job: write, edit, or execute code to accomplish the given task.

Available tools: repo_read, repo_list, repo_edit, repo_commit, repo_status, shell_exec, data_write

Workflow:
1. Read existing code if relevant (repo_read)
2. Write or modify code
3. Test if possible (shell_exec)
4. Commit if changes are complete (repo_commit)
5. Return: what you did, what the code does, any issues found

Be precise. Explain your changes. If something doesn't work, say so honestly.
""",

    "critic": """You are the Critic sub-agent of VOR.
Your job: review the work done by other sub-agents and provide honest assessment.

Available tools: repo_read, data_read

Review criteria:
- Correctness: does it do what was asked?
- Quality: is it well-done?
- Completeness: is anything missing?
- Risks: any potential issues?

Return structured feedback:
VERDICT: PASS | PARTIAL | FAIL
STRENGTHS: [what's good]
ISSUES: [what's wrong or missing]
SUGGESTIONS: [specific improvements]
CONFIDENCE: [0-100]%
""",

    "custom": """You are a specialized sub-agent of VOR.
Your role: {role}

Complete your assigned task using available tools.
Be focused, thorough, and return clear results.
""",
}


# ---------------------------------------------------------------------------
# Swarm
# ---------------------------------------------------------------------------

class Swarm:
    """
    Multi-agent pipeline orchestrator for VOR.

    VOR acts as orchestrator — it calls Planner, spawns sub-agents,
    runs them sequentially, and synthesizes the final result.
    """

    def __init__(
        self,
        llm_fn: Callable[[list[dict], str], str],
        tool_executor: Callable[[str, dict], Any],
        available_tools: list[str],
        emit_progress: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        Args:
            llm_fn:          fn(messages, system_prompt) -> str
            tool_executor:   fn(tool_name, kwargs) -> result
            available_tools: list of tool names registered in this agent
            emit_progress:   optional callback for real-time UI updates
        """
        self.llm         = llm_fn
        self.execute     = tool_executor
        self.all_tools   = set(available_tools)
        self.emit        = emit_progress or (lambda name, msg: None)

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self, task: str) -> SwarmResult:
        """Run the full multi-agent pipeline for a task."""
        t0 = time.time()
        log.info("Swarm starting: %s", task[:80])
        self.emit("swarm", "Starting multi-agent pipeline...")

        # Step 1: Plan
        subtasks = self._plan(task)
        if not subtasks:
            return SwarmResult(
                task=task, subtasks=[], final="Planner failed to generate subtasks.",
                total_duration=time.time()-t0, success=False
            )

        log.info("Plan: %d subtasks", len(subtasks))
        self.emit("planner", f"Plan ready: {len(subtasks)} subtasks")

        # Step 2: Execute pipeline
        context: dict[str, str] = {}  # task_id -> result

        for st in subtasks:
            # Check dependencies
            for dep in st.depends_on:
                if dep not in context:
                    log.warning("Dependency %s not resolved for %s", dep, st.id)

            t1 = time.time()
            st.status = "running"
            self.emit(st.agent_type, f"[{st.id}] {st.role}: starting...")
            log.info("Running subtask %s (%s): %s", st.id, st.agent_type, st.instruction[:60])

            try:
                # Build context summary for this agent
                dep_context = "\n\n".join(
                    f"### Result of {dep}:\n{context[dep]}"
                    for dep in st.depends_on
                    if dep in context
                )

                result = self._run_subtask(st, task, dep_context)
                st.result = result
                st.status = "done"
                context[st.id] = result
                st.duration = time.time() - t1
                self.emit(st.agent_type, f"[{st.id}] done ({st.duration:.1f}s)")
                log.info("Subtask %s done in %.1fs", st.id, st.duration)

            except Exception as exc:  # noqa: BLE001
                st.result = f"ERROR: {exc}"
                st.status = "failed"
                st.duration = time.time() - t1
                self.emit(st.agent_type, f"[{st.id}] FAILED: {exc}")
                log.error("Subtask %s failed: %s", st.id, exc)

        # Step 3: Synthesize
        final = self._synthesize(task, subtasks)
        total = time.time() - t0
        success = any(st.status == "done" for st in subtasks)

        self.emit("swarm", f"Pipeline complete in {total:.1f}s")
        log.info("Swarm done in %.1fs", total)

        return SwarmResult(
            task=task,
            subtasks=subtasks,
            final=final,
            total_duration=total,
            success=success,
        )

    # -----------------------------------------------------------------------
    # Planning
    # -----------------------------------------------------------------------

    def _plan(self, task: str) -> list[SubTask]:
        """Ask Planner to break task into subtasks."""
        self.emit("planner", "Analyzing task...")

        messages = [{"role": "user", "content": f"Task to plan:\n\n{task}"}]
        system   = AGENT_PROMPTS["planner"]

        try:
            raw = self.llm(messages, system)
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)
            subtasks = []
            for item in data.get("subtasks", []):
                # Filter tools to only available ones
                requested_tools = item.get("tools", [])
                valid_tools = [t for t in requested_tools if t in self.all_tools]

                st = SubTask(
                    id           = item["id"],
                    agent_type   = item.get("agent_type", "custom"),
                    role         = item.get("role", "Agent"),
                    instruction  = item["instruction"],
                    tools        = valid_tools,
                    depends_on   = item.get("depends_on", []),
                )
                subtasks.append(st)
            return subtasks

        except Exception as exc:  # noqa: BLE001
            log.error("Planner failed: %s", exc)
            # Fallback: single researcher + critic
            return [
                SubTask(
                    id="t1", agent_type="researcher", role="Researcher",
                    instruction=task,
                    tools=[t for t in ["web_search", "fetch_url"] if t in self.all_tools],
                ),
                SubTask(
                    id="t2", agent_type="critic", role="Critic",
                    instruction="Review the research results",
                    tools=[], depends_on=["t1"]
                ),
            ]

    # -----------------------------------------------------------------------
    # Sub-agent execution
    # -----------------------------------------------------------------------

    def _run_subtask(self, st: SubTask, original_task: str, dep_context: str) -> str:
        """Run a single sub-agent. Uses simple ReAct loop with tool calls."""

        system = self._build_system(st)

        user_content = f"""Original task: {original_task}

Your specific instruction: {st.instruction}
"""
        if dep_context:
            user_content += f"\n\nContext from previous agents:\n{dep_context}"

        messages = [{"role": "user", "content": user_content}]

        # Simple tool loop (max 8 iterations)
        for _ in range(8):
            reply = self.llm(messages, system)
            messages.append({"role": "assistant", "content": reply})

            # Check for tool call
            tool_call = self._parse_tool_call(reply)
            if not tool_call:
                return reply  # Final answer

            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("args", {})

            # Validate tool is allowed for this agent
            if tool_name not in st.tools:
                tool_result = f"Tool '{tool_name}' is not available for this agent."
            else:
                try:
                    tool_result = str(self.execute(tool_name, tool_args))
                    self.emit(tool_name, f"-> {str(tool_result)[:100]}")
                except Exception as exc:  # noqa: BLE001
                    tool_result = f"Tool error: {exc}"

            messages.append({
                "role": "user",
                "content": f"[Tool result: {tool_name}]\n{tool_result}"
            })

        return messages[-2]["content"] if len(messages) >= 2 else "No result."

    def _build_system(self, st: SubTask) -> str:
        """Build system prompt for a sub-agent."""
        base = AGENT_PROMPTS.get(st.agent_type, AGENT_PROMPTS["custom"])
        if st.agent_type == "custom":
            base = base.format(role=st.role)

        tool_list = "\n".join(f"  - {t}" for t in st.tools) if st.tools else "  (none)"
        return f"""{base}

Available tools for this task:
{tool_list}

To use a tool, output EXACTLY this format (nothing else on that line):
TOOL: {{"tool": "tool_name", "args": {{"arg1": "value1"}}}}

When done, output your final result without any TOOL: prefix.
"""

    def _parse_tool_call(self, text: str) -> dict | None:
        """Extract tool call from agent output if present."""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("TOOL:"):
                try:
                    payload = line[5:].strip()
                    return json.loads(payload)
                except Exception:  # noqa: BLE001
                    pass
        return None

    # -----------------------------------------------------------------------
    # Synthesis
    # -----------------------------------------------------------------------

    def _synthesize(self, task: str, subtasks: list[SubTask]) -> str:
        """VOR synthesizes all sub-agent results into a final answer."""
        results_text = "\n\n".join(
            f"### [{st.id}] {st.role} ({st.status}):\n{st.result}"
            for st in subtasks
        )

        system = """You are VOR — the orchestrating intelligence.
Sub-agents have completed their work. Synthesize their results into a clear,
complete final answer for the user.

Be direct. Integrate all findings. Do not just list what each agent said —
produce a unified, actionable response.
"""
        messages = [{
            "role": "user",
            "content": f"Original task: {task}\n\nSub-agent results:\n\n{results_text}\n\nProvide the final synthesized answer."
        }]

        try:
            return self.llm(messages, system)
        except Exception as exc:  # noqa: BLE001
            log.error("Synthesis failed: %s", exc)
            return results_text


# ---------------------------------------------------------------------------
# Helper: format swarm result for display
# ---------------------------------------------------------------------------

def format_swarm_result(result: SwarmResult) -> str:
    """Format SwarmResult as readable text for chat output."""
    lines = [
        f"**Multi-agent pipeline complete** ({result.total_duration:.1f}s)\n",
        f"**Task:** {result.task}\n",
        f"**Subtasks:** {len(result.subtasks)}",
    ]

    for st in result.subtasks:
        icon = "✅" if st.status == "done" else "❌"
        lines.append(f"  {icon} [{st.id}] {st.role} ({st.duration:.1f}s)")

    lines.append(f"\n**Result:**\n{result.final}")
    return "\n".join(lines)
