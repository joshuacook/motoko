"""Major worker - processes pending messages from the file-based queue.

Runs as a separate process alongside the API server in the same pod.
Polls .chelle/pending/ for messages, processes them with MajorAgent,
and the SDK writes results to JSONL session files.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from .agent import MajorAgent
from .config import MajorConfig
from .sessions import session_manager

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.0  # seconds


def git_commit(workspace: Path, message: str) -> bool:
    """Commit changes to git repository."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            return True
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=workspace,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=workspace,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git commit failed: {e}")
        return False


async def process_message(
    agent: MajorAgent,
    workspace_path: str,
    pending: dict,
) -> None:
    """Process a single pending message with the agent."""
    session_id = pending["session_id"]
    message = pending["message"]
    context = pending.get("context")
    user_id = pending.get("user_id")
    org_id = pending.get("org_id")

    # Determine SDK session ID — if JSONL file exists, resume it
    sdk_sessions_dir = session_manager._get_sdk_sessions_dir(workspace_path)
    sdk_session_id = None
    session_file = sdk_sessions_dir / f"{session_id}.jsonl"
    if session_file.exists():
        sdk_session_id = session_id

    # Build source constraint from context
    source_constraint = None
    if context and context.get("sourceIds"):
        from .librarian import LibraryIndex

        lib_index = LibraryIndex(workspace_path)
        source_constraint = []
        total_chars = 0
        max_budget = 60000
        for sid in context["sourceIds"]:
            if sid == "*":
                docs = lib_index.list_documents()
            elif lib_index.get_topic(sid):
                docs = lib_index.list_documents(topic_filter=[sid])
            else:
                doc = lib_index.get_document(sid)
                docs = [doc] if doc else []

            for doc in docs:
                if total_chars >= max_budget:
                    break
                content = lib_index.get_document_content(doc.id)
                if content:
                    truncated = content[: min(15000, max_budget - total_chars)]
                    source_constraint.append(
                        {"title": doc.title, "content": truncated}
                    )
                    total_chars += len(truncated)
            if total_chars >= max_budget:
                break

        # Store source_ids in session metadata
        session_manager.update_session(
            workspace_path, session_id, source_ids=context["sourceIds"]
        )

    # Build attached_entities from page context
    attached_entities = None
    if context and context.get("currentEntity"):
        entity_info = context["currentEntity"]
        entity_type = entity_info.get("type")
        entity_id = entity_info.get("id")
        entity_title = entity_info.get("title", "Untitled")

        if entity_type and entity_id:
            entity_path = Path(workspace_path) / entity_type / f"{entity_id}.md"
            entity_content = ""
            if entity_path.exists():
                entity_content = entity_path.read_text()
            attached_entities = [
                {
                    "type": entity_type,
                    "id": entity_id,
                    "title": entity_title,
                    "content": entity_content,
                }
            ]
    elif context and context.get("currentView"):
        view = context["currentView"]
        attached_entities = [
            {
                "type": "navigation",
                "id": view,
                "title": f"User is currently viewing: {view}",
                "content": "",
            }
        ]

    # Process with agent — SDK writes to JSONL automatically
    sessions_dir = Path(workspace_path) / ".chelle" / "sessions"
    async for event in agent.send_message(
        message=message,
        workspace_path=workspace_path,
        session_id=sdk_session_id,
        attached_entities=attached_entities,
        source_constraint=source_constraint,
    ):
        event_type = type(event).__name__

        if event_type == "ResultMessage":
            if hasattr(event, "session_id") and event.session_id:
                actual_sdk_id = event.session_id

                if actual_sdk_id == session_id:
                    # SDK used our session ID — register metadata
                    session_manager.create_session(
                        workspace_path,
                        actual_sdk_id,
                        user_id=user_id,
                        org_id=org_id,
                    )
                else:
                    # SDK created a new ID — symlink ours to it
                    sdk_file = sessions_dir / f"{actual_sdk_id}.jsonl"
                    our_file = sessions_dir / f"{session_id}.jsonl"
                    if sdk_file.exists() and not our_file.exists():
                        try:
                            our_file.symlink_to(sdk_file.name)
                        except Exception:
                            pass

    # Commit session to git
    git_commit(Path(workspace_path), f"Chat: {session_id}")


async def worker_loop() -> None:
    """Main worker loop — polls for pending messages and processes them."""
    workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")
    config = MajorConfig()
    agent = MajorAgent(config=config)

    logger.info(f"Major worker started, watching {workspace_path}/.chelle/pending/")

    while True:
        pending = session_manager.get_next_pending(workspace_path)
        if pending is None:
            await asyncio.sleep(POLL_INTERVAL)
            continue

        msg_id = pending.get("id", "unknown")
        session_id = pending.get("session_id", "unknown")
        filename = pending["_filename"]

        logger.info(f"Processing {msg_id} for session {session_id}")

        try:
            await process_message(agent, workspace_path, pending)
            logger.info(f"Completed {msg_id}")
        except Exception:
            logger.exception(f"Failed to process {msg_id}")

        # Always remove pending file (even on error) to prevent infinite retry
        session_manager.remove_pending(workspace_path, filename)


def main():
    """Entry point for major-worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [worker] %(levelname)s %(message)s",
    )
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
