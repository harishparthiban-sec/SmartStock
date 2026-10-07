"""Unit tests for the SmartStock AI Copilot Agent module (src/inventory/agent.py)
and the FastAPI /api/copilot/chat endpoint.
"""
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.inventory.agent import (
    ask_copilot_agent,
    build_inventory_context_summary,
    find_referenced_products,
    generate_fallback_response,
)
from src.api.server import app


@pytest.fixture
def sample_inventory_df():
    """Provides a realistic sample inventory DataFrame for agent testing."""
    return pd.DataFrame([
        {
            "product_id": "P001",
            "name": "Organic Milk 1L",
            "category": "Dairy",
            "status": "ORDER NOW",
            "urgency": "CRITICAL",
            "current_inventory": 120.0,
            "days_of_stock_left": 2.2,
            "lead_time_days": 3,
            "order_qty": 450.0,
            "stockout_date": "2026-10-10",
            "order_by_date": "2026-10-07",
            "copilot_action": "Place emergency PO for 450 units",
            "copilot_reason": "Stockout in 2.2 days is within 3-day lead time.",
            "analog_growth_pct": 18.0,
            "excess_units": 0.0,
            "recommended_markdown_pct": 0.0,
        },
        {
            "product_id": "P002",
            "name": "Whole Wheat Bread",
            "category": "Bakery",
            "status": "OK",
            "urgency": "LOW",
            "current_inventory": 400.0,
            "days_of_stock_left": 12.0,
            "lead_time_days": 2,
            "order_qty": 0.0,
            "stockout_date": "2026-10-25",
            "order_by_date": "2026-10-23",
            "copilot_action": "Maintain monitoring; inventory healthy",
            "copilot_reason": "Stock covers 12.0 days.",
            "analog_growth_pct": None,
            "excess_units": 0.0,
            "recommended_markdown_pct": 0.0,
        },
        {
            "product_id": "P003",
            "name": "Greek Yogurt 500g",
            "category": "Dairy",
            "status": "OVERSTOCK",
            "urgency": "LOW",
            "current_inventory": 850.0,
            "days_of_stock_left": 38.0,
            "lead_time_days": 4,
            "order_qty": 0.0,
            "stockout_date": "2026-11-20",
            "order_by_date": "",
            "copilot_action": "Apply 15% markdown promotion to clear excess inventory",
            "copilot_reason": "Excess 350 units detected with 38.0 days of cover.",
            "analog_growth_pct": None,
            "excess_units": 350.0,
            "recommended_markdown_pct": 15.0,
        },
    ])


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

def test_find_referenced_products(sample_inventory_df):
    """Detects product IDs and product names accurately."""
    # By ID
    res1 = find_referenced_products("Why should I order P001 right now?", sample_inventory_df)
    assert res1 == ["P001"]

    # By name
    res2 = find_referenced_products("Tell me about Whole Wheat Bread please", sample_inventory_df)
    assert res2 == ["P002"]

    # Multiple products
    res3 = find_referenced_products("Compare P001 and P003", sample_inventory_df)
    assert set(res3) == {"P001", "P003"}

    # No match
    res4 = find_referenced_products("What is the weather today?", sample_inventory_df)
    assert res4 == []


def test_build_inventory_context_summary(sample_inventory_df):
    """Builds clean aggregated inventory context for LLM grounding."""
    summary = build_inventory_context_summary(sample_inventory_df)
    assert summary["total_products"] == 3
    assert summary["reorder_needed_count"] == 1
    assert summary["total_reorder_units"] == 450.0
    assert len(summary["critical_stockouts"]) == 1
    assert summary["critical_stockouts"][0]["product_id"] == "P001"
    assert len(summary["overstock_items"]) == 1
    assert summary["overstock_items"][0]["product_id"] == "P003"


def test_fallback_specific_product(sample_inventory_df):
    """Fallback generator provides rich details for a referenced product."""
    reply = generate_fallback_response("Why reorder P001?", sample_inventory_df, ["P001"])
    assert "P001" in reply
    assert "CRITICAL" in reply
    assert "450 units" in reply
    assert "18.0%" in reply


def test_fallback_stockout_alert(sample_inventory_df):
    """Fallback generator highlights urgent items for stockout questions."""
    reply = generate_fallback_response("Which products are at critical risk?", sample_inventory_df, [])
    assert "CRITICAL ALERT" in reply
    assert "P001" in reply


def test_fallback_overstock_markdown(sample_inventory_df):
    """Fallback generator recommends markdowns for overstock items."""
    reply = generate_fallback_response("What markdown discounts should we run?", sample_inventory_df, [])
    assert "DYNAMIC PRICING" in reply
    assert "P003" in reply
    assert "15%" in reply


def test_fallback_general_overview(sample_inventory_df):
    """Fallback generator provides overview when query is general."""
    reply = generate_fallback_response("Hello, what should I do?", sample_inventory_df, [])
    assert "SmartStock Inventory Overview" in reply
    assert "Total Catalog: 3" in reply


def test_fallback_order_today(sample_inventory_df):
    """Fallback generator provides explicit order recommendations for order today queries."""
    reply = generate_fallback_response("What should I order today?", sample_inventory_df, [])
    assert "Recommended Purchase Orders for Today" in reply
    assert "P001" in reply
    assert "450 units" in reply


# ---------------------------------------------------------------------------
# Integration tests for ask_copilot_agent
# ---------------------------------------------------------------------------

def test_ask_copilot_agent_offline_mode(sample_inventory_df):
    """When GEMINI_API_KEY is not set, agent seamlessly uses deterministic engine."""
    with patch("src.inventory.agent.get_api_key", return_value=None):
        res = ask_copilot_agent("Why order P001?", sample_inventory_df)
        assert res["status"] == "success"
        assert res["provider"] == "smartstock-fallback"
        assert "P001" in res["referenced_products"]
        assert "450 units" in res["reply"]


def test_ask_copilot_agent_with_gemini(sample_inventory_df):
    """When GEMINI_API_KEY is set, agent calls the Gemini SDK."""
    mock_resp = MagicMock()
    mock_resp.text = "Mocked Gemini: P001 needs urgent reorder of 450 units due to 3-day lead time."

    mock_chat = MagicMock()
    mock_chat.send_message.return_value = mock_resp

    mock_client = MagicMock()
    mock_client.chats.create.return_value = mock_chat

    with patch("src.inventory.agent.get_api_key", return_value="real-secret-key-12345"):
        with patch("src.inventory.agent._GENAI_SDK", "google-genai"):
            with patch("src.inventory.agent.genai.Client", return_value=mock_client):
                res = ask_copilot_agent("Why order P001?", sample_inventory_df)
                assert res["status"] == "success"
                assert res["provider"] == "google-gemini"
                assert "Mocked Gemini" in res["reply"]


def test_ask_copilot_agent_handles_api_exception(sample_inventory_df):
    """If Gemini API raises an exception (e.g. rate limit), falls back cleanly."""
    mock_client = MagicMock()
    mock_client.chats.create.side_effect = RuntimeError("Rate limit exceeded")

    with patch("src.inventory.agent.get_api_key", return_value="real-secret-key-12345"):
        with patch("src.inventory.agent._GENAI_SDK", "google-genai"):
            with patch("src.inventory.agent.genai.Client", return_value=mock_client):
                res = ask_copilot_agent("Why order P001?", sample_inventory_df)
                assert res["status"] == "fallback"
                assert res["provider"] == "smartstock-fallback"
                assert "Rate limit exceeded" in res["error_detail"]
                assert "P001" in res["reply"]


# ---------------------------------------------------------------------------
# FastAPI /api/copilot/chat endpoint tests
# ---------------------------------------------------------------------------

def test_api_copilot_chat_endpoint():
    """FastAPI POST /api/copilot/chat responds correctly to requests."""
    client = TestClient(app)
    response = client.post(
        "/api/copilot/chat",
        json={
            "message": "Why should I order P001?",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "status" in data
    assert "provider" in data
    assert len(data["reply"]) > 20
