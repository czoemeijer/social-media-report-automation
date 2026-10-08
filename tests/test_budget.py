from __future__ import annotations

import unittest
from decimal import Decimal

from social_report.budget import (
    BudgetFormatError,
    decimal_to_string,
    parse_budget_text,
    reconcile_budget,
)


class BudgetTest(unittest.TestCase):
    def test_csv_aliases_and_decimal_money(self):
        rows = parse_budget_text(
            "Publication Date,Platform,ID or Link,Planned Boost,Notes\n"
            "2026-01-01,Instagram,https://instagram.com/p/one/,10.25,synthetic\n"
        )
        self.assertEqual(rows[0]["planned_spend"], Decimal("10.25"))
        self.assertEqual(rows[0]["platform"], "Instagram")

    def test_tsv_and_configurable_alias(self):
        rows = parse_budget_text(
            "My Link\tBudget\nhttps://instagram.com/p/one\t1,50\n",
            delimiter="\t",
            aliases={"content_id_or_link": ("My Link",)},
        )
        self.assertEqual(rows[0]["planned_spend"], Decimal("1.50"))

    def test_european_and_english_grouped_money(self):
        european = parse_budget_text("Budget\n1.234,56\n", delimiter=";")
        english = parse_budget_text("Budget\n1,234.56\n", delimiter=";")
        self.assertEqual(european[0]["planned_spend"], Decimal("1234.56"))
        self.assertEqual(english[0]["planned_spend"], Decimal("1234.56"))

    def test_match_variance_and_no_double_count(self):
        plans = parse_budget_text(
            "ID or Link,Planned Spend\n"
            "https://instagram.com/p/one,10\n"
            "https://instagram.com/p/one,20\n"
        )
        actuals = [
            {
                "ad_id": "ad-1",
                "instagram_permalink_url": "https://instagram.com/p/one/",
                "spend": "12.50",
            }
        ]
        result = reconcile_budget(plans, actuals)
        self.assertEqual(result["items"][0]["reconciliation_status"], "matched")
        self.assertEqual(result["items"][0]["variance"], Decimal("2.50"))
        self.assertEqual(result["items"][1]["reconciliation_status"], "ambiguous")
        self.assertEqual(result["summary"]["actual_spend"], Decimal("12.50"))

    def test_ambiguous_unmatched_needs_review_and_identifier_match(self):
        plans = [
            {"planned_spend": Decimal("1"), "ad_id": "a"},
            {"planned_spend": Decimal("1"), "content_name": "title"},
            {"planned_spend": Decimal("1")},
        ]
        actuals = [{"ad_id": "a", "spend": "1"}, {"ad_id": "a", "spend": "2"}]
        result = reconcile_budget(plans, actuals)
        self.assertEqual(
            [item["reconciliation_status"] for item in result["items"]],
            ["ambiguous", "needs_review", "unmatched"],
        )

    def test_generic_id_column_matches_ad_id(self):
        plans = parse_budget_text("ID or Link,Planned Spend\nad-42,4.00\n")
        result = reconcile_budget(plans, [{"ad_id": "ad-42", "spend": "3.50"}])
        self.assertEqual(result["items"][0]["reconciliation_status"], "matched")
        self.assertEqual(result["items"][0]["match_method"], "ad_id")

    def test_bad_file_and_decimal_serialization(self):
        with self.assertRaises(BudgetFormatError):
            parse_budget_text("Only Name\nhello\n")
        self.assertEqual(decimal_to_string({"x": Decimal("1.20")}), {"x": "1.20"})


if __name__ == "__main__":
    unittest.main()
