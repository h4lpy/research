"""Per-session and per-request derived facts, pulled straight from documented
fields (notes.md "Fields seen in 0.60.0" / "Interpretation notes"). No new
meanings are invented here - anything not in notes.md stays in `raw`.
"""

from __future__ import annotations

from typing import Any


def derive_session_facts(state: dict[str, Any]) -> dict[str, Any]:
    input_state = state.get("inputState") or {}
    selected_model = input_state.get("selectedModel") or {}
    metadata = selected_model.get("metadata") or {}
    auth = metadata.get("auth") or {}

    return {
        "session_id": state.get("sessionId"),
        "version": state.get("version"),
        "creation_date": state.get("creationDate"),
        "initial_location": state.get("initialLocation"),
        "responder_username": state.get("responderUsername"),
        "has_pending_edits": state.get("hasPendingEdits"),
        "custom_title": state.get("customTitle"),
        "account_label": auth.get("accountLabel"),
        "selected_model_identifier": selected_model.get("identifier"),
        "selected_model_family": metadata.get("family"),
        "selected_model_version": metadata.get("version"),
        "selected_model_is_auto_placeholder": selected_model.get("identifier") == "copilot/auto",
        "model_configuration": selected_model.get("modelConfiguration"),
        "input_mode": (input_state.get("mode") or {}).get("kind"),
        "permission_level": input_state.get("permissionLevel"),
        "pending_requests": state.get("pendingRequests") or [],
    }


def derive_request_facts(request: dict[str, Any]) -> dict[str, Any]:
    model_state = request.get("modelState") or {}
    result = request.get("result") or {}
    metadata = result.get("metadata") or {}
    timings = result.get("timings") or {}
    mode_info = request.get("modeInfo") or {}
    agent = request.get("agent") or {}
    message = request.get("message") or {}

    auto_mode_resolution = next(
        (
            item for item in (request.get("response") or [])
            if isinstance(item, dict) and item.get("kind") == "autoModeResolution"
        ),
        None,
    )

    is_incomplete = model_state.get("value") == 0 and "result" not in request

    return {
        "request_id": request.get("requestId"),
        "response_id": request.get("responseId"),
        "timestamp": request.get("timestamp"),
        "response_timestamp": request.get("responseTimestamp"),
        "time_spent_waiting": request.get("timeSpentWaiting"),
        "completed_at": model_state.get("completedAt"),
        "model_state_value": model_state.get("value"),
        "is_incomplete": is_incomplete,
        "elapsed_ms": request.get("elapsedMs"),
        "timings_first_progress": timings.get("firstProgress"),
        "timings_total_elapsed": timings.get("totalElapsed"),
        "model_id": request.get("modelId"),
        "resolved_model": metadata.get("resolvedModel"),
        "auto_mode_resolution": auto_mode_resolution,
        "mode_kind": mode_info.get("kind"),
        "permission_level": mode_info.get("permissionLevel"),
        "agent_id": agent.get("id"),
        "extension_version": agent.get("extensionVersion"),
        "prompt_tokens": request.get("promptTokens"),
        "completion_tokens": request.get("completionTokens"),
        "output_buffer": request.get("outputBuffer"),
        "prompt_token_details": request.get("promptTokenDetails"),
        "copilot_credits": request.get("copilotCredits"),
        "details_string": result.get("details"),
        "message_text": message.get("text"),
        "variables": (request.get("variableData") or {}).get("variables") or [],
        "edited_file_events": request.get("editedFileEvents") or [],
        "result_response_id": metadata.get("responseId"),
    }
