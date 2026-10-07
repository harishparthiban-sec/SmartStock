"""Interactive CLI entrypoint for the SmartStock AI Copilot Agent.

Usage:
    Interactive mode:
        python chat.py

    Direct question mode:
        python chat.py "Why should I order P001 now?"
        python chat.py "Which products are at critical risk?"
"""
import sys
import runpy

if __name__ == "__main__":
    runpy.run_module("src.inventory.agent", run_name="__main__")
