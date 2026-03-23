from django.test import TestCase

from apps.filtering.engine import (
    validate_phone,
    apply_filter_rule,
    apply_filter_group,
    apply_scoring,
    filter_and_score_rows,
    get_phone_country,
)


class ValidatePhoneTest(TestCase):
    def test_valid_french_phone(self):
        valid, normalized = validate_phone('0612345678', 'FR')
        self.assertTrue(valid)
        self.assertIn('33', normalized)

    def test_valid_international(self):
        valid, _ = validate_phone('+33612345678', 'FR')
        self.assertTrue(valid)

    def test_invalid_phone(self):
        valid, _ = validate_phone('invalid', 'FR')
        self.assertFalse(valid)

    def test_empty_phone(self):
        valid, normalized = validate_phone('', 'FR')
        self.assertFalse(valid)
        self.assertEqual(normalized, '')


class FilterRuleTest(TestCase):
    def test_equals(self):
        self.assertTrue(apply_filter_rule({'city': 'Paris'}, {'field': 'city', 'operator': 'equals', 'value': 'Paris'}))
        self.assertFalse(apply_filter_rule({'city': 'Lyon'}, {'field': 'city', 'operator': 'equals', 'value': 'Paris'}))

    def test_contains(self):
        self.assertTrue(apply_filter_rule({'city': 'Paris 15'}, {'field': 'city', 'operator': 'contains', 'value': 'Paris'}))

    def test_startswith(self):
        self.assertTrue(apply_filter_rule({'postal_code': '75001'}, {'field': 'postal_code', 'operator': 'startswith', 'value': '75'}))

    def test_in_list(self):
        self.assertTrue(apply_filter_rule({'city': 'Paris'}, {'field': 'city', 'operator': 'in_list', 'value': 'Paris, Lyon'}))
        self.assertTrue(apply_filter_rule({'city': 'Lyon'}, {'field': 'city', 'operator': 'in_list', 'value': 'Paris, Lyon'}))
        self.assertFalse(apply_filter_rule({'city': 'Marseille'}, {'field': 'city', 'operator': 'in_list', 'value': 'Paris, Lyon'}))

    def test_is_empty(self):
        self.assertTrue(apply_filter_rule({'email': ''}, {'field': 'email', 'operator': 'is_empty', 'value': ''}))
        self.assertFalse(apply_filter_rule({'email': 'x@x.com'}, {'field': 'email', 'operator': 'is_empty', 'value': ''}))

    def test_missing_field_in_row_evaluates_as_empty(self):
        # Row sans le champ -> valeur vide, equals 'y' = False
        self.assertFalse(apply_filter_rule({}, {'field': 'x', 'operator': 'equals', 'value': 'y'}))


class FilterGroupTest(TestCase):
    def test_and_logic(self):
        row = {'city': 'Paris', 'postal_code': '75001'}
        group = {'logic': 'AND', 'rules': [
            {'field': 'city', 'operator': 'equals', 'value': 'Paris'},
            {'field': 'postal_code', 'operator': 'startswith', 'value': '75'},
        ]}
        self.assertTrue(apply_filter_group(row, group))

    def test_or_logic(self):
        row = {'city': 'Lyon'}
        group = {'logic': 'OR', 'rules': [
            {'field': 'city', 'operator': 'equals', 'value': 'Paris'},
            {'field': 'city', 'operator': 'equals', 'value': 'Lyon'},
        ]}
        self.assertTrue(apply_filter_group(row, group))

    def test_empty_rules_passes(self):
        self.assertTrue(apply_filter_group({'x': 1}, {'logic': 'AND', 'rules': []}))


class FilterAndScoreTest(TestCase):
    def test_filter_and_score_no_filters(self):
        rows = [
            {'phone': '0612345678', 'city': 'Paris'},
            {'phone': 'invalid', 'city': 'Lyon'},
        ]
        filtered, valid_count, _ = filter_and_score_rows(rows, {}, [])
        self.assertEqual(len(filtered), 2)
        self.assertIn('phone_valid', filtered[0])
        self.assertIn('phone_normalized', filtered[0])

    def test_filter_by_city(self):
        rows = [
            {'phone': '0612345678', 'city': 'Paris'},
            {'phone': '0698765432', 'city': 'Lyon'},
        ]
        filters = {'logic': 'AND', 'rules': [{'field': 'city', 'operator': 'equals', 'value': 'Paris'}]}
        filtered, _, _ = filter_and_score_rows(rows, filters, [])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['city'], 'Paris')
