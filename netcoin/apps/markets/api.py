"""Thin API schema helpers for prediction markets."""

from __future__ import annotations

MARKET_API_ENDPOINTS = [
    "GET /markets/{id}/orderbook",
    "GET /markets/{id}/ticker",
    "GET /markets/{id}/trades",
    "GET /markets/{id}/positions",
    "GET /markets/{id}/depth",
    "GET /markets/{id}/candles",
    "GET /markets/{id}/open-interest",
    "POST /markets/{id}/batch-orders",
    "POST /markets/{id}/cancel-all",
    "POST /markets/{id}/pause",
    "POST /markets/{id}/resume",
]
