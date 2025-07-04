import os
from typing import Any
import numpy as np
from langchain_community.graphs import Neo4jGraph


def _get_current_branches() -> list[str]:
    """Fetch a list of current branch names from a Neo4j database."""
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
    )

    current_branches = graph.query(
        """
        MATCH (h:Branch)
        RETURN h.name AS branch_name
        """
    )
    print("Messi",current_branches)
    current_branches = [d["branch_name"].lower() for d in current_branches]
    print (current_branches)
    return current_branches


def _get_current_wait_time_minutes(branch: str) -> int:
    """Get the current wait time at a branch in minutes."""

    current_branches = _get_current_branches()

    if branch.lower() not in current_branches:
        return -1

    return np.random.randint(low=0, high=600)


def get_current_wait_times(branch: str) -> str:
    """Get the current wait time at a branch formatted as a string."""

    wait_time_in_minutes = _get_current_wait_time_minutes(branch)

    if wait_time_in_minutes == -1:
        return f"Branch '{branch}' does not exist."

    hours, minutes = divmod(wait_time_in_minutes, 60)

    if hours > 0:
        formatted_wait_time = f"{hours} hours {minutes} minutes"
    else:
        formatted_wait_time = f"{minutes} minutes"

    return formatted_wait_time


def get_most_available_branch(tmp: Any) -> dict[str, float]:
    """Find the branch with the shortest wait time."""

    current_branches = _get_current_branches()

    current_wait_times = [_get_current_wait_time_minutes(h) for h in current_branches]

    best_time_idx = np.argmin(current_wait_times)
    best_branch = current_branches[best_time_idx]
    best_wait_time = current_wait_times[best_time_idx]

    return {best_branch: best_wait_time}
