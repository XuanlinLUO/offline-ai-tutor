import unittest
from scripts.export_reviewed import export


class DatasetTests(unittest.TestCase):
    def row(self, question, accepted=True):
        return {"instruction": question, "input": "", "output": "问题分析\n解题步骤\n最终答案\n知识点讲解", "accepted": accepted}

    def test_review_filter_dedup_and_repeatable_split(self):
        rows = [self.row("a"), self.row("a"), self.row("b"), self.row("c", False)]
        first = export(rows)
        self.assertEqual(first, export(rows))
        self.assertEqual(sum(map(len, first)), 2)
        self.assertEqual({x["instruction"] for group in first for x in group}, {"a", "b"})

    def test_unreviewed_data_not_exported(self):
        with self.assertRaises(ValueError): export([self.row("a", False), self.row("b", False)])

    def test_incomplete_format_rejected(self):
        row = self.row("a"); row["output"] = "only an answer"
        with self.assertRaises(ValueError): export([row, self.row("b")])


if __name__ == "__main__": unittest.main()
