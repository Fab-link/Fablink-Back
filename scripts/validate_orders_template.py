#!/usr/bin/env python3
"""
Validate that apps/core/services/orders_steps_template.build_orders_steps_template()
matches the structure of Fablink-Back/order_schema.json for the 'steps' field.

Exit code:
  0 = match
  1 = mismatch or error
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def project_root() -> str:
	# scripts/validate_orders_template.py → go up two levels to repo root
	return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def load_schema_steps(schema_path: str) -> List[Dict[str, Any]]:
	with open(schema_path, 'r', encoding='utf-8') as f:
		data = json.load(f)
	steps = data.get('steps')
	if not isinstance(steps, list):
		raise ValueError('order_schema.json: steps must be a list')
	return steps


def load_template_steps() -> List[Dict[str, Any]]:
	root = project_root()
	sys.path.insert(0, root)
	try:
		from apps.core.services.orders_steps_template import build_orders_steps_template  # type: ignore
	except Exception as e:
		print(f"ERROR: failed to import build_orders_steps_template: {e}")
		raise
	steps = build_orders_steps_template()
	if not isinstance(steps, list):
		raise ValueError('build_orders_steps_template() must return a list')
	return steps


def shape(obj: Any) -> Any:
	"""Return a shape descriptor replacing concrete values with their structural representation.
	For dicts: map keys to recursively computed shapes
	For lists: return a list with a single element representing the element shape (if available)
	For scalars: return type name placeholder
	"""
	if isinstance(obj, dict):
		return {k: shape(v) for k, v in obj.items()}
	if isinstance(obj, list):
		if obj:
			return [shape(obj[0])]
		return []
	# scalars → just placeholders to avoid strict type coupling
	return '<scalar>'


def compare_shapes(a: Any, b: Any, path: str = 'steps') -> List[str]:
	errors: List[str] = []
	if isinstance(a, dict) and isinstance(b, dict):
		a_keys = set(a.keys())
		b_keys = set(b.keys())
		for k in sorted(a_keys - b_keys):
			errors.append(f"{path}: extra key in template: {k}")
		for k in sorted(b_keys - a_keys):
			errors.append(f"{path}: missing key in template: {k}")
		for k in sorted(a_keys & b_keys):
			errors.extend(compare_shapes(a[k], b[k], f"{path}.{k}"))
		return errors
	if isinstance(a, list) and isinstance(b, list):
		# compare only element shape
		a_el = a[0] if a else None
		b_el = b[0] if b else None
		if a_el is None and b_el is None:
			return errors
		if (a_el is None) != (b_el is None):
			errors.append(f"{path}: list element presence mismatch")
			return errors
		errors.extend(compare_shapes(a_el, b_el, f"{path}[0]"))
		return errors
	# both scalars → consider equal regardless of concrete type/value
	return errors


def main() -> int:
	try:
		root = project_root()
		schema_path = os.path.join(root, 'order_schema.json')
		schema_steps = load_schema_steps(schema_path)
		template_steps = load_template_steps()

		a = shape(template_steps)
		b = shape(schema_steps)
		diffs = compare_shapes(a, b)
		if diffs:
			print('Template validation FAILED:')
			for d in diffs:
				print(' -', d)
			return 1
		print('Template validation PASSED: orders template matches order_schema.json steps structure.')
		return 0
	except Exception as e:
		print('ERROR:', e)
		return 1


if __name__ == '__main__':
	raise SystemExit(main())

