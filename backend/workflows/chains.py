"""
workflows/chains.py — Modular workflow primitives.

Implements all five workflow patterns:
  1. Prompt Chaining     — sequential LLM calls where output feeds next input
  2. Routing             — classify then dispatch to specialist handler
  3. Parallelization     — run N tasks concurrently, aggregate results
  4. Reflection          — self-critique and iterative improvement loop
  5. Orchestrator-Worker — planner decomposes task, workers execute in parallel

These are standalone async functions that can be composed freely.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

import anthropic

from config import get_settings
from utils.logger import logger

settings = get_settings()
claude = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# ── 1. Prompt Chaining ────────────────────────────────────────────────────
#
#  Step A → Step B → Step C
#  Each step receives the output of the previous step as its input.
#  Useful for: research → summarize → format

async def prompt_chain(
    steps: List[Dict[str, str]],   # [{"system": "...", "user_template": "..."}]
    initial_input: str,
    model: str = None,
) -> List[str]:
    """
    Run a sequential chain of LLM calls.

    Each step's `user_template` may contain `{input}` which is replaced
    by the previous step's output.

    Returns a list of outputs (one per step).
    """
    model = model or settings.CLAUDE_MODEL
    outputs: List[str] = []
    current_input = initial_input

    for i, step in enumerate(steps):
        user_msg = step["user_template"].replace("{input}", current_input)
        logger.info(f"[Chain] Step {i+1}/{len(steps)}")

        response = await claude.messages.create(
            model=model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=step.get("system", "You are a helpful assistant."),
            messages=[{"role": "user", "content": user_msg}],
        )
        output = "".join(b.text for b in response.content if b.type == "text")
        outputs.append(output)
        current_input = output

    return outputs


# ── 2. Routing ────────────────────────────────────────────────────────────
#
#  query → classifier → route_A | route_B | route_C
#  The classifier LLM call is cheap; the routed handler does the heavy work.

ROUTE_HANDLERS: Dict[str, Callable] = {}   # populated by register_route()


def register_route(name: str):
    """Decorator to register a coroutine as a named route handler."""
    def decorator(fn):
        ROUTE_HANDLERS[name] = fn
        return fn
    return decorator


async def route(
    query: str,
    routes: List[str],
    route_descriptions: Dict[str, str],
    default_route: str,
) -> Tuple[str, Any]:
    """
    Classify the query into one of `routes`, then execute its handler.

    Args:
        query:               The user's query
        routes:              List of valid route names
        route_descriptions:  {route_name: description} for the classifier
        default_route:       Fallback if classification fails

    Returns:
        (chosen_route, handler_result)
    """
    descriptions = "\n".join(
        f"- {name}: {desc}" for name, desc in route_descriptions.items()
    )
    classifier_prompt = (
        f"Classify this query into exactly one category.\n\n"
        f"Categories:\n{descriptions}\n\n"
        f"Query: {query}\n\n"
        f"Reply with ONLY the category name."
    )

    response = await claude.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=32,
        system="You are a query classifier. Reply with only the category name.",
        messages=[{"role": "user", "content": classifier_prompt}],
    )
    chosen = "".join(b.text for b in response.content if b.type == "text").strip().lower()

    if chosen not in routes:
        logger.warning(f"[Router] Unknown route '{chosen}', using default '{default_route}'")
        chosen = default_route

    logger.info(f"[Router] Query routed to: {chosen}")

    handler = ROUTE_HANDLERS.get(chosen)
    if handler:
        result = await handler(query)
    else:
        result = {"route": chosen, "query": query}

    return chosen, result


# ── 3. Parallelization ────────────────────────────────────────────────────
#
#  [task_1, task_2, task_3] → concurrent execution → aggregated result

async def parallelize(
    tasks: List[Coroutine],
    return_exceptions: bool = True,
) -> List[Any]:
    """
    Run an arbitrary list of coroutines concurrently.
    Failed tasks return their exception object (not raised) by default.
    """
    logger.info(f"[Parallel] Running {len(tasks)} tasks concurrently")
    results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        logger.warning(f"[Parallel] {len(errors)}/{len(tasks)} tasks failed")
    return results


async def voting_aggregation(
    query: str,
    candidate_answers: List[str],
    model: str = None,
) -> str:
    """
    Parallelization variant: run N LLM calls and ask a meta-LLM to pick
    the best answer (majority-vote style).

    Useful for: fact checking, answer validation, reducing hallucinations.
    """
    model = model or settings.CLAUDE_MODEL
    candidates_text = "\n\n".join(
        f"Candidate {i+1}:\n{ans}" for i, ans in enumerate(candidate_answers)
    )

    response = await claude.messages.create(
        model=model,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=(
            "You are an expert judge. Select the best answer from the candidates "
            "or synthesise a superior answer combining their strengths. "
            "Cite the best elements from each. Be concise."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {query}\n\n"
                    f"{candidates_text}\n\n"
                    "Select or synthesise the best answer:"
                ),
            }
        ],
    )
    return "".join(b.text for b in response.content if b.type == "text")


# ── 4. Reflection (self-correction loop) ─────────────────────────────────
#
#  initial_answer → critique → improved_answer → (repeat if needed)

async def reflection_loop(
    query: str,
    initial_answer: str,
    max_iterations: int = 2,
    model: str = None,
) -> Dict[str, Any]:
    """
    Iteratively improve an answer through self-critique.

    Returns:
        {"answer": str, "iterations": int, "improved": bool}
    """
    model = model or settings.CLAUDE_MODEL
    current_answer = initial_answer
    improved = False

    for iteration in range(max_iterations):
        logger.info(f"[Reflection] Iteration {iteration + 1}/{max_iterations}")

        critique_response = await claude.messages.create(
            model=model,
            max_tokens=1024,
            system=(
                "You are a critical reviewer. Evaluate the answer strictly.\n"
                "If the answer is already excellent, output exactly: PASS\n"
                "Otherwise list specific flaws (missing info, wrong facts, "
                "poor citations, unclear language) on separate lines."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nAnswer:\n{current_answer}",
                }
            ],
        )
        critique = "".join(b.text for b in critique_response.content if b.type == "text").strip()

        if critique.upper() == "PASS":
            logger.info(f"[Reflection] Passed on iteration {iteration + 1}")
            break

        logger.info(f"[Reflection] Critique: {critique[:120]}…")

        # Improve based on critique
        improve_response = await claude.messages.create(
            model=model,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system="You are an expert writer. Revise the answer to address all critique points.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Original query: {query}\n\n"
                        f"Current answer:\n{current_answer}\n\n"
                        f"Critique:\n{critique}\n\n"
                        "Write an improved answer that addresses every critique point:"
                    ),
                }
            ],
        )
        current_answer = "".join(
            b.text for b in improve_response.content if b.type == "text"
        )
        improved = True

    return {
        "answer": current_answer,
        "iterations": iteration + 1,
        "improved": improved,
    }


# ── 5. Orchestrator-Worker ────────────────────────────────────────────────
#
#  Planner (LLM) → [Worker_1, Worker_2, Worker_3] → Validator → final

async def orchestrator_worker(
    task: str,
    worker_fn: Callable[[str], Coroutine],
    max_subtasks: int = 4,
    model: str = None,
) -> Dict[str, Any]:
    """
    Planner breaks `task` into subtasks.
    Workers execute all subtasks in parallel.
    Validator synthesises the results.

    Args:
        task:         High-level task description
        worker_fn:    Async function(subtask: str) → result
        max_subtasks: Cap on subtask count

    Returns:
        {"plan": [...], "results": [...], "synthesis": str}
    """
    model = model or settings.CLAUDE_MODEL

    # ── Step 1: Plan ──────────────────────────────────────────────────────
    plan_response = await claude.messages.create(
        model=model,
        max_tokens=512,
        system=(
            f"You are a task planner. Break the task into {max_subtasks} or fewer "
            "independent subtasks that can run in parallel. "
            "Output ONLY a JSON array of strings."
        ),
        messages=[{"role": "user", "content": f"Task: {task}"}],
    )
    plan_text = "".join(b.text for b in plan_response.content if b.type == "text").strip()

    try:
        if "```" in plan_text:
            plan_text = plan_text.split("```")[1]
            if plan_text.startswith("json"):
                plan_text = plan_text[4:].strip()
        subtasks: List[str] = json.loads(plan_text)[:max_subtasks]
    except Exception:
        subtasks = [task]

    logger.info(f"[Orchestrator] Plan: {subtasks}")

    # ── Step 2: Execute workers in parallel ───────────────────────────────
    worker_results = await parallelize([worker_fn(st) for st in subtasks])

    # Filter out exceptions
    valid_results = [
        r for r in worker_results if not isinstance(r, Exception)
    ]

    # ── Step 3: Validate / synthesise ─────────────────────────────────────
    synthesis_context = "\n\n".join(
        f"Subtask: {st}\nResult: {json.dumps(r) if not isinstance(r, str) else r}"
        for st, r in zip(subtasks, valid_results)
    )

    synthesis_response = await claude.messages.create(
        model=model,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system="You are a synthesis expert. Combine worker results into a coherent final answer.",
        messages=[
            {
                "role": "user",
                "content": (
                    f"Original task: {task}\n\n"
                    f"Worker results:\n{synthesis_context}\n\n"
                    "Synthesise into the best possible final answer:"
                ),
            }
        ],
    )
    synthesis = "".join(b.text for b in synthesis_response.content if b.type == "text")

    return {
        "plan": subtasks,
        "results": valid_results,
        "synthesis": synthesis,
    }
