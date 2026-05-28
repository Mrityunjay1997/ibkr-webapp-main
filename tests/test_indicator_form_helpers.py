import sys
import json
import unittest

sys.path.insert(0, '.')

from scanner.ibkr_signal_engine import _compare_indicator_condition
from scanner.indicator_form_helpers import (
    merge_dynamic_with_legacy_form,
    build_legacy_form_from_dynamic,
    convert_form_to_indicator_config,
)


class TestIndicatorFormHelpers(unittest.TestCase):
    def test_merge_dynamic_with_legacy_form_preserves_percentage_mode(self):
        form_data = {}
        config = json.dumps([
            {
                'type': 'FastOBV',
                'window': 5,
                'comparison': 'greater',
                'percentage': 10,
                'usePercentage': True,
                'enabled': True
            }
        ])

        merged = merge_dynamic_with_legacy_form(form_data, config)

        self.assertEqual(merged.get('FastOBV'), 5)
        self.assertEqual(merged.get('ComparisonFastOBV'), 'greater')
        self.assertEqual(merged.get('PercentageFastOBV'), 10)
        self.assertEqual(merged.get('FastOBVBool'), 'percentage')

    def test_build_legacy_form_from_dynamic_includes_percentage_mode(self):
        indicators = [
            {
                'type': 'MediumOBV',
                'window': 10,
                'comparison': 'lower',
                'percentage': 7.5,
                'usePercentage': False,
                'enabled': True
            }
        ]

        legacy = build_legacy_form_from_dynamic(indicators)

        self.assertEqual(legacy.get('MediumOBV'), 10)
        self.assertEqual(legacy.get('ComparisonMediumOBV'), 'lower')
        self.assertEqual(legacy.get('PercentageMediumOBV'), 7.5)
        self.assertEqual(legacy.get('MediumOBVBool'), 'value')

    def test_compare_indicator_condition_respects_obv_percentage_mode(self):
        data = {
            'obv': 100.0,
            'close': 111.0,
        }
        form = {
            'ComparisonOBV': 'greater',
            'PercentageOBV': 10,
            'OBVBool': 'percentage',
        }

        condition = _compare_indicator_condition(
            data,
            form,
            data_key='obv',
            comparison_key='ComparisonOBV',
            threshold_key='PercentageOBV',
            mode_key='OBVBool',
        )

        self.assertTrue(condition)

    def test_convert_form_to_indicator_config_preserves_use_percentage(self):
        form_data = {
            'FastOBV': 5,
            'ComparisonFastOBV': 'greater',
            'PercentageFastOBV': 10,
            'FastOBVBool': 'percentage',
        }

        config_json = convert_form_to_indicator_config(form_data, indicators_to_include=['FastOBV'])
        config = json.loads(config_json)

        self.assertEqual(len(config), 1)
        self.assertTrue(config[0]['usePercentage'])


if __name__ == '__main__':
    unittest.main()
