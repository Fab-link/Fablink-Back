from __future__ import annotations

from typing import List, Dict, Any


def build_designer_steps_template() -> List[Dict[str, Any]]:
    """
    Build initial steps template matching designer_order_schema.json structure,
    keeping keys/arrays but leaving values empty. Dates/nums set to None, strings to ''.
    """
    return [
        {
            "index": 1,
            "name": "샘플 제작 업체 선정",
            "status": "",
            "factory_list": [],
        },
        {
            "index": 2,
            "name": "샘플 생산 현황",
            "status": "",
            "factory_name": "",
            "order_date": "",  # or None if preferred
            "factory_contact": "",
            "stage": [
                {"index": 1, "name": "1차 가봉", "status": "", "end_date": ""},
                {"index": 2, "name": "부자재 부착", "status": "", "end_date": ""},
                {"index": 3, "name": "마킹 및 재단", "status": "", "end_date": ""},
                {"index": 4, "name": "봉제", "status": "", "end_date": ""},
                {"index": 5, "name": "검사 및 다림질", "status": "", "end_date": ""},
                {"index": 6, "name": "배송", "status": "", "end_date": "", "delivery_code": ""},
            ],
        },
        {
            "index": 3,
            "name": "샘플 생산 배송 조회",
            "status": "",
            "product_name": "",
            "product_quantity": None,
            "factory_name": "",
            "factory_contact": "",
            "delivery_status": "",
            "delivery_code": "",
        },
        {
            "index": 4,
            "name": "샘플 피드백",
            "status": "",
            "feedback_history": [],
        },
        {
            "index": 5,
            "name": "본 생산 업체 선정",
            "status": "",
            "factory_list": [],
        },
        {
            "index": 6,
            "name": "본 생산 현황",
            "status": "",
            "stage": [
                {"name": "1차 가봉", "status": "", "end_date": ""},
                {"name": "부자재 부착", "status": "", "end_date": ""},
                {"name": "마킹 및 재단", "status": "", "end_date": ""},
                {"name": "봉제", "status": "", "end_date": ""},
                {"name": "검사 및 다림질", "status": "", "end_date": ""},
                {"name": "배송", "status": "", "end_date": ""},
            ],
        },
        {
            "index": 7,
            "name": "본 생산 배송 조회",
            "status": "",
            "product_name": "",
            "product_quantity": None,
            "factory_name": "",
            "factory_contact": "",
            "delivery_status": "",
            "delivery_code": "",
        },
    ]
