"""AI Copilot Agent for SmartStock.

Provides conversational AI assistance for supermarket inventory managers using
Google Gemini API (via modern google-genai SDK), grounded directly in the
deterministic inventory engine and Demand Time Machine analog calculation outputs.

Features:
- Live Gemini API integration with modern google-genai SDK (defaults to gemini-2.5-flash).
- Deep context grounding with stockout risks, ROP, supplier lead times, and
  Demand Time Machine analog consensus growth & conflict signals.
- Graceful deterministic fallback mode: if GEMINI_API_KEY is not set or network
  is unreachable, provides structured data-grounded insights so live pitches
  and demos NEVER fail on stage.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
import pandas as pd

# Try modern google-genai first, then legacy google.generativeai
_GENAI_SDK: Optional[str] = None
try:
    from google import genai
    from google.genai import types
    _GENAI_SDK = "google-genai"
except ImportError:
    try:
        import google.generativeai as legacy_genai
        _GENAI_SDK = "legacy-genai"
    except ImportError:
        _GENAI_SDK = None


def get_api_key() -> Optional[str]:
    """Retrieves Google Gemini API key from environment variables or .env file.

    Ignores dummy placeholders like 'your-gemini-api-key'.
    """
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    # If not in environment, check local .env file
    if not key and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass

    if not key:
        return None
    cleaned = key.strip().strip('"\'')
    if cleaned.lower() in ["your-gemini-api-key", "your_gemini_api_key", "none", "", "placeholder", "fake"]:
        return None
    if cleaned.startswith("your-") or "gemini-api-key" in cleaned.lower():
        return None
    return cleaned


def build_inventory_context_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Extracts high-level inventory statistics and product highlights for grounding."""
    if df is None or df.empty:
        return {
            "total_products": 0,
            "critical_stockouts": [],
            "high_urgency": [],
            "overstock_items": [],
            "reorder_needed_count": 0,
        }

    critical_items = []
    high_items = []
    overstock_items = []
    total_reorder_qty = 0.0

    for _, row in df.iterrows():
        p_id = str(row.get("product_id", ""))
        name = str(row.get("name", p_id))
        urgency = str(row.get("urgency", "LOW"))
        status = str(row.get("status", "OK"))
        qty = float(row.get("order_qty", 0.0))
        days_left = float(row.get("days_of_stock_left", 999.0))
        lead_time = int(row.get("lead_time_days", 1))
        stockout_date = str(row.get("stockout_date", "") or "N/A")
        order_by_date = str(row.get("order_by_date", "") or "N/A")
        analog_growth = row.get("analog_growth_pct")

        total_reorder_qty += qty

        item_summary = {
            "product_id": p_id,
            "name": name,
            "status": status,
            "urgency": urgency,
            "days_of_stock_left": round(days_left, 1),
            "lead_time_days": lead_time,
            "order_qty": round(qty, 1),
            "stockout_date": stockout_date,
            "order_by_date": order_by_date,
            "copilot_reason": str(row.get("copilot_reason", "")),
            "analog_growth_pct": float(analog_growth) if pd.notna(analog_growth) else None,
        }

        if urgency == "CRITICAL":
            critical_items.append(item_summary)
        elif urgency == "HIGH":
            high_items.append(item_summary)

        if status == "OVERSTOCK":
            overstock_items.append({
                "product_id": p_id,
                "name": name,
                "current_stock": float(row.get("current_inventory", 0)),
                "excess_units": float(row.get("excess_units", 0)),
                "markdown_pct": float(row.get("recommended_markdown_pct", 0)),
                "copilot_action": str(row.get("copilot_action", "")),
            })

    return {
        "total_products": len(df),
        "reorder_needed_count": len(critical_items) + len(high_items),
        "total_reorder_units": round(total_reorder_qty, 1),
        "critical_stockouts": critical_items,
        "high_urgency": high_items,
        "overstock_items": overstock_items,
    }


def find_referenced_products(query: str, df: pd.DataFrame) -> List[str]:
    """Detects product IDs or product names mentioned in the user query."""
    if df is None or df.empty:
        return []

    referenced = []
    query_upper = query.upper()

    for _, row in df.iterrows():
        p_id = str(row.get("product_id", "")).upper()
        p_name = str(row.get("name", "")).upper()
        if p_id and re.search(rf"\b{re.escape(p_id)}\b", query_upper):
            referenced.append(row["product_id"])
        elif p_name and p_name in query_upper:
            referenced.append(row["product_id"])

    return list(dict.fromkeys(referenced))


def generate_fallback_response(
    query: str,
    df: pd.DataFrame,
    referenced_products: List[str],
) -> str:
    """Provides structured, intelligent answers when Gemini API key is absent or offline.

    Ensures that live demo pitches never fail if network drops or API keys expire.
    """
    if df is None or df.empty:
        return (
            "I'm the SmartStock AI Reorder Copilot. No inventory data is currently loaded. "
            "Please run the inventory engine or ensure data/products.csv is present."
        )

    query_lower = query.lower()

    # Case 1: Question about specific product(s)
    if referenced_products:
        p_id = referenced_products[0]
        prod_matches = df[df["product_id"] == p_id]
        if not prod_matches.empty:
            row = prod_matches.iloc[0]
            name = row.get("name", p_id)
            urgency = row.get("urgency", "LOW")
            status = row.get("status", "OK")
            current_stock = row.get("current_inventory", 0)
            days_left = row.get("days_of_stock_left", 0)
            lead_time = row.get("lead_time_days", 0)
            order_qty = row.get("order_qty", 0)
            stockout_date = row.get("stockout_date", "None")
            order_by_date = row.get("order_by_date", "None")
            copilot_action = row.get("copilot_action", "")
            copilot_reason = row.get("copilot_reason", "")
            analog_growth = row.get("analog_growth_pct")
            markdown_pct = row.get("recommended_markdown_pct")

            lines = [
                f"### AI Copilot Insight for **{name} ({p_id})**",
                f"- **Status**: `{status}` (Urgency: **{urgency}**)",
                f"- **Current Stock**: {current_stock:,.0f} units ({days_left:.1f} days remaining)",
                f"- **Supplier Lead Time**: {lead_time} days",
            ]

            if status in ["ORDER NOW", "ORDER SOON"]:
                lines.extend([
                    f"- **Recommended Reorder**: **{order_qty:,.0f} units**",
                    f"- **Order By Deadline**: `{order_by_date}` (Projected stockout: `{stockout_date}`)",
                    f"- **Recommended Action**: {copilot_action}",
                    f"- **Decision Rationale**: {copilot_reason}",
                ])
                if pd.notna(analog_growth):
                    lines.append(
                        f"- **Demand Time Machine Signal**: Historical analog growth of "
                        f"**{analog_growth:+.1f}%** factored into safety buffer."
                    )
            elif status == "OVERSTOCK":
                lines.extend([
                    f"- **Excess Holding**: {row.get('excess_units', 0):,.0f} units",
                    f"- **Markdown Recommendation**: Apply **{markdown_pct:.0f}% promotional discount**.",
                    f"- **Recommended Action**: {copilot_action}",
                    f"- **Decision Rationale**: {copilot_reason}",
                ])
            else:
                lines.append("- **Inventory Health**: Healthy stock balance. No reorder required.")

            return "\n".join(lines)

    # Case 2: Stockout / Urgent / Run-out-first query
    stockout_keywords = [
        "critical", "urgent", "stockout", "risk", "warning",
        "out of stock", "run out", "first", "soonest", "empty",
        "deplete", "exhaust", "shortage", "lead time",
    ]
    if any(k in query_lower for k in stockout_keywords):
        # Sort products by days_of_stock_left ascending
        sorted_df = df.sort_values(by="days_of_stock_left", ascending=True)
        critical_df = df[df["urgency"].isin(["CRITICAL", "HIGH"])]

        # Specific "which runs out first" inquiry
        if any(w in query_lower for w in ["first", "soonest", "run out", "deplet"]):
            lines = [
                "Here is the timeline of items running out of stock soonest, in priority order:\n"
            ]
            for idx, (_, row) in enumerate(sorted_df.iterrows(), 1):
                p_name = row.get("name", row["product_id"])
                p_id = row["product_id"]
                days_left = float(row.get("days_of_stock_left", 0))
                urgency = str(row.get("urgency", "LOW")).upper()
                lead_time = int(row.get("lead_time_days", 1))
                order_qty = float(row.get("order_qty", 0))
                order_date = str(row.get("order_by_date", "ASAP"))

                # Icon based on urgency
                icon = "[CRITICAL]" if urgency == "CRITICAL" else "[SOON]" if urgency in ["HIGH", "MEDIUM"] else "[OK]"

                # Human-friendly explanation
                lead_note = "within lead time - order urgently!" if days_left <= lead_time else f"lead time is {lead_time} days"

                entry = (
                    f"{idx}. {icon} {p_name} ({p_id})\n"
                    f"   - Stock Left: {days_left:.1f} days ({lead_note})\n"
                    f"   - Recommended Action: Order {order_qty:,.0f} units by {order_date}\n"
                )
                lines.append(entry)

            # Executive summary at bottom
            critical_names = [r.get("name", r["product_id"]) for _, r in sorted_df.iterrows() if float(r.get("days_of_stock_left", 0)) <= int(r.get("lead_time_days", 1))]
            if critical_names:
                lines.append(
                    f"Summary: Prioritize {', '.join(critical_names[:2])} first, as remaining stock is less than supplier lead time."
                )
            else:
                lines.append("Summary: All lead times are currently covered, but place orders as indicated to maintain safety stock.")

            return "\n".join(lines)

        if critical_df.empty:
            return (
                "**Stockout Assessment**: All products currently have healthy stock levels above their "
                "reorder points. No immediate critical stockout risks detected."
            )

        lines = [
            f"**[CRITICAL ALERT] Urgent Stockout Warning ({len(critical_df)} items need immediate attention):**\n"
        ]
        for _, row in critical_df.iterrows():
            lines.append(
                f"- **{row.get('name', row['product_id'])} ({row['product_id']})**: "
                f"**{row.get('urgency')}** urgency. Only **{row.get('days_of_stock_left', 0):.1f} days** of stock left "
                f"(Lead time: {row.get('lead_time_days')} days). "
                f"Recommended order: **{row.get('order_qty', 0):.0f} units** by `{row.get('order_by_date')}`."
            )
        lines.append("\n*Recommendation*: Approve these purchase orders immediately to avoid shelf stockouts.")
        return "\n".join(lines)

    # Case 3: Overstock / Markdown / Promotion query
    if any(k in query_lower for k in ["overstock", "markdown", "discount", "promo", "excess"]):
        overstock_df = df[df["status"] == "OVERSTOCK"]
        if overstock_df.empty:
            return "No overstocked products detected. All current inventory is within optimal holding bounds."

        lines = [
            f"**[DYNAMIC PRICING] Overstock & Markdown Recommendations ({len(overstock_df)} items):**\n"
        ]
        for _, row in overstock_df.iterrows():
            lines.append(
                f"- **{row.get('name', row['product_id'])} ({row['product_id']})**: "
                f"Holding ~{row.get('days_of_stock_left', 0):.0f} days of cover "
                f"(Excess: {row.get('excess_units', 0):.0f} units). "
                f"Recommended action: **{row.get('recommended_markdown_pct', 0):.0f}% promotional markdown** "
                f"to recover working capital."
            )
        return "\n".join(lines)

    # Case 4: General overview
    reorder_df = df[df["order_qty"] > 0]
    total_reorder = reorder_df["order_qty"].sum() if not reorder_df.empty else 0
    return (
        f"**SmartStock Inventory Overview**:\n\n"
        f"- **Total Catalog**: {len(df)} products monitored\n"
        f"- **Products Requiring Reorder**: {len(reorder_df)} products ({total_reorder:,.0f} total units)\n"
        f"- **Critical Stockout Risks**: {len(df[df['urgency'] == 'CRITICAL'])} products\n"
        f"- **Overstocked Items**: {len(df[df['status'] == 'OVERSTOCK'])} products\n\n"
        f"You can ask me questions like:\n"
        f"- *'Why should I order P001 now?'*\n"
        f"- *'Which products are at critical stockout risk?'*\n"
        f"- *'What markdown promotions should we run for overstocked items?'*"
    )


def ask_copilot_agent(
    message: str,
    df: pd.DataFrame,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model_name: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """Interacts with the SmartStock AI Copilot Agent.

    Uses Google Gemini API if GEMINI_API_KEY is configured. Otherwise
    falls back cleanly to the deterministic copilot engine.
    """
    referenced = find_referenced_products(message, df)
    api_key = get_api_key()

    # Determine cards to display in frontend UI
    referenced_for_cards = list(referenced)
    if not referenced_for_cards and any(w in message.lower() for w in ["run out", "first", "soonest", "stockout", "critical", "risk", "deplet"]):
        sorted_df = df.sort_values(by="days_of_stock_left", ascending=True)
        referenced_for_cards = list(sorted_df["product_id"].head(3))

    # If no key or no SDK installed, use deterministic fallback
    if not api_key or not _GENAI_SDK:
        reply = generate_fallback_response(message, df, referenced)
        return {
            "reply": reply,
            "model": "copilot-deterministic-engine",
            "referenced_products": referenced_for_cards,
            "status": "success",
            "provider": "smartstock-fallback",
        }

    try:
        # Build prompt and context grounding
        context_data = build_inventory_context_summary(df)

        referenced_details = []
        if referenced:
            for p_id in referenced:
                rows = df[df["product_id"] == p_id]
                if not rows.empty:
                    referenced_details.append(rows.iloc[0].to_dict())

        system_instruction = (
            "You are the SmartStock AI Reorder Copilot, an expert supply chain and inventory "
            "intelligence assistant for retail supermarket operations.\n"
            "You help inventory managers make confident, data-backed reorder and stock management decisions.\n\n"
            "CURRENT INVENTORY ENGINE SNAPSHOT:\n"
            f"{json.dumps(context_data, default=str, indent=2)}\n\n"
        )
        if referenced_details:
            system_instruction += (
                "DETAILS OF SPECIFIC PRODUCTS IN USER QUERY:\n"
                f"{json.dumps(referenced_details, default=str, indent=2)}\n\n"
            )

        system_instruction += (
            "GUIDELINES:\n"
            "1. Ground your answers strictly in the provided inventory numbers, lead times, safety stocks, "
            "and Demand Time Machine analog signals.\n"
            "2. Always state the urgency level (CRITICAL, HIGH, MEDIUM, LOW) and the exact supplier lead time.\n"
            "3. If historical Demand Time Machine analogs detected demand uplift or conflicts, explain how that "
            "protects against stockouts or avoids over-ordering.\n"
            "4. For overstocked items, explain the markdown discount recommendation.\n"
            "5. Keep responses concise, professional, and directly actionable for store managers.\n"
            "6. Use clean Markdown formatting with bullet points and bold highlights.\n"
        )

        reply_text = ""

        # Path A: Modern google-genai SDK using recommended chats.create
        if _GENAI_SDK == "google-genai":
            client = genai.Client(api_key=api_key)
            chat_history_contents = []
            if conversation_history:
                for turn in conversation_history[-6:]:
                    role = "user" if turn.get("role") == "user" else "model"
                    chat_history_contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=turn.get("content", ""))],
                        )
                    )

            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                ),
                history=chat_history_contents,
            )
            response = chat.send_message(message)
            reply_text = response.text or ""

        # Path B: Legacy google.generativeai SDK
        elif _GENAI_SDK == "legacy-genai":
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction,
            )
            chat = model.start_chat(history=[])
            resp = chat.send_message(message)
            reply_text = resp.text or ""

        if not reply_text:
            reply_text = generate_fallback_response(message, df, referenced)

        return {
            "reply": reply_text,
            "model": model_name,
            "referenced_products": referenced,
            "status": "success",
            "provider": "google-gemini",
        }

    except Exception as exc:
        # Fall back smoothly on any API error (network timeout, rate limit, invalid key)
        fallback_reply = generate_fallback_response(message, df, referenced)
        return {
            "reply": fallback_reply,
            "model": "copilot-deterministic-engine",
            "referenced_products": referenced,
            "status": "fallback",
            "error_detail": str(exc),
            "provider": "smartstock-fallback",
        }


if __name__ == "__main__":
    import sys
    from src.inventory.engine import compute_reorder, get_copilot_recommendations

    # Load data
    prod_path = "data/products.csv" if os.path.exists("data/products.csv") else "tests/fixtures/products_stub.csv"
    fc_path = "data/forecast.csv" if os.path.exists("data/forecast.csv") else "tests/fixtures/forecast_stub.csv"
    err_path = "data/forecast_error.csv" if os.path.exists("data/forecast_error.csv") else "tests/fixtures/error_stub.csv"

    p_df = pd.read_csv(prod_path)
    f_df = pd.read_csv(fc_path)
    e_df = pd.read_csv(err_path) if os.path.exists(err_path) else None

    orders = compute_reorder(p_df, f_df, e_df)
    copilot_df = get_copilot_recommendations(orders, f_df)

    has_key = bool(get_api_key())
    provider_str = "Google Gemini" if has_key else "Deterministic Engine (Fallback)"

    # Case A: User passed question as command-line arguments:
    # Example: python -m src.inventory.agent "Why should I order P001?"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        res = ask_copilot_agent(query, copilot_df)
        print(f"\n[AI Copilot | {res['provider']} | {res['model']}]")
        print(res["reply"])
        sys.exit(0)

    # Case B: Interactive chat mode
    print("=" * 65)
    print(" SmartStock AI Copilot Interactive Assistant")
    print(f" Provider: {provider_str} | Products Monitored: {len(copilot_df)}")
    print(" Type your question below (or type 'exit' / 'quit' to leave):")
    print("=" * 65)

    history = []
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting AI Copilot. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q", "bye"]:
            print("Exiting AI Copilot. Goodbye!")
            break

        res = ask_copilot_agent(user_input, copilot_df, conversation_history=history)
        reply = res["reply"]

        print(f"\nCopilot [{res['provider']}]:")
        print(reply)

        # Track conversation history for multi-turn context
        history.append({"role": "user", "content": user_input})
        history.append({"role": "model", "content": reply})
