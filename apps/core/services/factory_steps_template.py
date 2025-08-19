from __future__ import annotations

from typing import List, Dict, Any


def build_factory_steps_template(phase: str) -> List[Dict[str, Any]]:
    """
    Build initial factory steps template by phase.
    Values are empty strings or None; structure preserved for UI.
    phase: 'sample' or 'main'
    """
    phase = (phase or '').lower()
    if phase not in ('sample', 'main'):
        phase = 'sample'

    if phase == 'sample':
        return [
            {"index": 1, "name": "견적/수주", "status": "", "end_date": ""},
            {"index": 2, "name": "자재수급", "status": "", "end_date": ""},
            {"index": 3, "name": "재단/봉제", "status": "", "end_date": ""},
            {"index": 4, "name": "QC", "status": "", "end_date": ""},
            {"index": 5, "name": "포장", "status": "", "end_date": ""},
            {"index": 6, "name": "출고", "status": "", "end_date": "", "delivery_code": ""},
        ]

    # main phase
    return [
        {"index": 1, "name": "생산계획", "status": "", "end_date": ""},
        {"index": 2, "name": "자재수급", "status": "", "end_date": ""},
        {"index": 3, "name": "재단", "status": "", "end_date": ""},
        {"index": 4, "name": "봉제", "status": "", "end_date": ""},
        {"index": 5, "name": "QC", "status": "", "end_date": ""},
        {"index": 6, "name": "포장", "status": "", "end_date": ""},
        {"index": 7, "name": "출고", "status": "", "end_date": "", "delivery_code": ""},
    ]
