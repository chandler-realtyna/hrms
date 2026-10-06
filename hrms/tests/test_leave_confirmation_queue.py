"""Desk card count and destination must retain unsubmitted HR decisions."""
import ast
from pathlib import Path
import unittest


class LeaveConfirmationQueueTest(unittest.TestCase):
	def test_count_and_destination_cover_unconfirmed_decisions_only(self):
		tree = ast.parse((Path(__file__).parents[1] / "api/admin_desk.py").read_text())
		counts = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "REVIEW_COUNTS" for target in node.targets))
		count_filter = ast.literal_eval(counts.value)["Leave Application"]
		routes = []
		for node in ast.walk(tree):
			if not isinstance(node, ast.Dict):
				continue
			values = {key.value: value for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant)}
			if isinstance(values.get("route"), ast.Constant) and values["route"].value == "/desk/leave-application":
				routes.append(ast.literal_eval(values["filters"]))
		self.assertEqual(routes, [count_filter])
		self.assertEqual(count_filter["docstatus"], 0)
		self.assertEqual(set(count_filter["status"][1]), {"Open", "Approved", "Rejected"})


if __name__ == "__main__":
	unittest.main()
