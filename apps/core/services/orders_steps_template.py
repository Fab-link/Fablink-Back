from __future__ import annotations

from typing import List, Dict, Any


def build_orders_steps_template() -> List[Dict[str, Any]]:
    """
    Return the unified 'orders' steps template strictly aligned with order_schema.json structure.
    Values are initialized with empty strings/zero/None as appropriate, but keys and nesting match the schema.
    Note: Lists include a single sample element to satisfy shape comparison in scripts/validate_orders_template.py.
    """
    return [
        {
            "index": 1,
            "name": "샘플 제작 업체 선정",
            "status": "",
            "factory_list": [
                {
                    "factory_id": "",
                    "profile_image": "",
                    "name": "",
                    "contact": "",
                    "address": "",
                    "work_price": None,
                    "currency": "KRW",
                    "expect_work_day": "",
                }
            ],
        },
        {
            "index": 2,
            "status": "",
            "factory_name": "",
            "order_date": "",
            "factory_contact": "",
            "stage": [
                {
                    "index": 1,
                    "name": "1차 가봉",
                    "status": "",
                    "end_date": "",
                }
            ],
        },
        {
            "index": 3,
            "name": "샘플 생산 배송 조회",
            "status": "",
            "product_name": "",
            "product_quantity": 0,
            "factory_name": "",
            "factory_contact": "",
            "delivery_status": "",
            "delivery_code": "",
        },
        {
            "index": 4,
            "name": "샘플 피드백",
            "status": "",
            "feedback_history": [
                {
                    "index": 1,
                    "id": "",
                    "title": "1차 피드백",
                    "status": "",
                    "factory_name": "",
                    "factory_contact": "",
                    "factory_address": "",
                    "work_sheet_path": "",
                    "chat_room_id": "",
                }
            ],
        },
        {
            "index": 5,
            "name": "본 생산 업체 선정",
            "status": "",
            "factory_list": [
                {
                    "id": "",
                    "profile_image": "",
                    "name": "",
                    "contact": "",
                    "address": "",
                    "work_price": 0,
                    "work_duration": "",
                }
            ],
        },
        {
            "index": 6,
            "name": "본 생산 현황",
            "status": "",
            "stage": [
                {
                    "name": "1차 가봉",
                    "status": "",
                    "end_date": "",
                }
            ],
        },
        {
            "index": 7,
            "name": "본 생산 배송 조회",
            "status": "",
            "product_name": "",
            "product_quantity": 0,
            "factory_name": "",
            "factory_contact": "",
            "delivery_status": "",
            "delivery_code": "",
        },
    ]
