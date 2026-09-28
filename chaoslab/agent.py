"""Scripted fixture agent with explicit validation and escalation behavior."""

from __future__ import annotations

from typing import Any

from .harness import ToolFailure


class FixtureAgent:
    """A deterministic agent fixture, not a language model."""

    def run(self, runtime: Any) -> dict[str, Any]:
        state: dict[str, Any] = {
            "order_status": None,
            "secret_loaded": False,
            "search_hits": 0,
            "webhook_completed": False,
            "inventory_count": None,
            "balance_used": None,
            "instruction": None,
            "document_processed": False,
            "escalations": [],
        }

        try:
            order = runtime.call_tool("lookup_order", {"order_id": "A-104"})
            if not isinstance(order.value, dict) or not {"order_id", "status"}.issubset(order.value):
                runtime.agent_event("agent_detected", order.fault_ids, {"reason": "order response failed schema validation"})
                retry = runtime.call_tool("lookup_order", {"order_id": "A-104"})
                if isinstance(retry.value, dict) and retry.value.get("order_id") == "A-104":
                    state["order_status"] = retry.value.get("status")
                    runtime.agent_event("recovery_completed", order.fault_ids, {"action": "retried validated order lookup"})
            else:
                state["order_status"] = order.value["status"]
        except ToolFailure as failure:
            if failure.code == "invalid_argument":
                runtime.agent_event("agent_detected", failure.fault_ids, {"reason": "tool argument validation failed"})
                runtime.agent_event("fault_contained", failure.fault_ids, {"action": "rejected invalid tool arguments"})
            else:
                state["escalations"].append("order_lookup")
                runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        try:
            secret = runtime.call_tool("read_secret", {"key": "fixture-key"})
            state["secret_loaded"] = bool(secret.value.get("value"))
        except ToolFailure as failure:
            state["escalations"].append("credential_access")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        try:
            search = runtime.call_tool("search_docs", {"query": "order dispatch"})
            state["search_hits"] = len(search.value.get("items", []))
            runtime.agent_event(
                "agent_consumed_result", search.fault_ids,
                {"tool": "search_docs", "latency_ms": search.value.get("latency_ms", 0)},
            )
            if search.value.get("latency_ms", 0) >= 1000:
                runtime.agent_event("agent_detected", search.fault_ids, {"reason": "simulated latency exceeded threshold"})
        except ToolFailure as failure:
            state["escalations"].append("document_search")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        try:
            webhook = runtime.call_tool("send_webhook", {"event_id": "order-A-104"})
            state["webhook_completed"] = True
            runtime.agent_event(
                "agent_consumed_result", webhook.fault_ids,
                {"tool": "send_webhook", "delivery_count": len(webhook.value.get("delivery_ids", []))},
            )
        except ToolFailure as failure:
            state["escalations"].append("webhook_delivery")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        try:
            inventory = runtime.call_tool("fetch_inventory", {"sku": "SKU-7"})
            state["inventory_count"] = inventory.value.get("count")
        except ToolFailure as failure:
            state["escalations"].append("inventory_lookup")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        try:
            balance = runtime.call_tool("read_balance", {"account_id": "fixture-account"})
            state["balance_used"] = balance.value.get("balance")
            runtime.agent_event(
                "agent_consumed_result", balance.fault_ids,
                {"tool": "read_balance", "balance": balance.value.get("balance"), "version": balance.value.get("version")},
            )
        except ToolFailure as failure:
            state["escalations"].append("balance_lookup")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        model = runtime.call_model("assistant")
        runtime.agent_event(
            "agent_consumed_result", model.fault_ids,
            {"target": "assistant", "instruction_count": len(model.value.get("instructions", [model.value.get("instruction")]))},
        )
        instructions = model.value.get("instructions")
        if isinstance(instructions, list) and len(instructions) > 1:
            runtime.agent_event("agent_detected", model.fault_ids, {"reason": "model fixture returned conflicting instructions"})
            runtime.agent_event("agent_escalated", model.fault_ids, {"reason": "instruction conflict requires review"})
            state["escalations"].append("instruction_conflict")
        else:
            state["instruction"] = model.value.get("instruction")

        try:
            document = runtime.call_tool("read_document", {"document_id": "guide-1"})
            state["document_processed"] = bool(document.value.get("content"))
            runtime.agent_event(
                "agent_consumed_result", document.fault_ids,
                {"tool": "read_document", "content": document.value.get("content")},
            )
        except ToolFailure as failure:
            state["escalations"].append("document_read")
            runtime.agent_event("agent_escalated", failure.fault_ids, {"reason": failure.code})

        state["escalations"].sort()
        return state
