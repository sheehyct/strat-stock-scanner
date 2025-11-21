"""
STRAT analysis tools for MCP server
Wrapper for existing mcp_tools functions
"""

from typing import List
from mcp_tools import (
    get_stock_quote as _get_stock_quote,
    analyze_strat_patterns as _analyze_strat_patterns,
    scan_sector_for_strat as _scan_sector_for_strat,
    scan_etf_holdings_strat as _scan_etf_holdings_strat,
    get_multiple_quotes as _get_multiple_quotes
)

# Re-export the tool functions for MCP server
get_stock_quote = _get_stock_quote
analyze_strat_patterns = _analyze_strat_patterns
scan_sector_for_strat = _scan_sector_for_strat
scan_etf_holdings_strat = _scan_etf_holdings_strat
get_multiple_quotes = _get_multiple_quotes
