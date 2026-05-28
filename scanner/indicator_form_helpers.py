"""
Helper utilities for form data handling with dynamic indicators.

This module provides utilities for parsing, validating, and converting
form data between the old hardcoded system and the new dynamic system.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def merge_dynamic_with_legacy_form(form_data: Dict[str, Any], indicator_config_json: str = None) -> Dict[str, Any]:
    """
    Merge dynamic indicator configuration with legacy form fields.
    
    This allows the system to work with both:
    - Old hardcoded indicators (FastSMA, MediumSMA, etc.)
    - New dynamic indicators (from indicatorConfig JSON)
    
    Args:
        form_data: Dictionary of form fields
        indicator_config_json: JSON string with dynamic indicator config
    
    Returns:
        Merged form data with both legacy and dynamic indicators
    """
    merged = form_data.copy()
    
    if indicator_config_json:
        try:
            indicators = json.loads(indicator_config_json)
            # Legacy code can read from merged dict
            # Example: if indicator_config has FastSMA, set merged['FastSMA'] = window value
            for ind in indicators:
                if ind.get('enabled') and ind.get('comparison') != 'disabled':
                    ind_type = ind['type']
                    window = ind.get('window', 0)
                    
                    # Set window value (legacy field name)
                    if ind_type not in merged or not merged[ind_type]:
                        merged[ind_type] = window
                    
                    # Set comparison (legacy field name)
                    comp_key = f'Comparison{ind_type}'
                    if comp_key not in merged or merged.get(comp_key) == "":
                        merged[comp_key] = ind.get('comparison', 'disabled')
                    
                    # Set percentage (legacy field name)
                    pct_key = f'Percentage{ind_type}'
                    if pct_key not in merged or merged.get(pct_key) == "":
                        merged[pct_key] = ind.get('percentage', 0)

                    # Set percentage/value mode for legacy boolean fields
                    bool_key = f'{ind_type}Bool'
                    if bool_key not in merged or merged.get(bool_key) == "":
                        merged[bool_key] = 'percentage' if ind.get('usePercentage') else 'value'
        
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Error merging dynamic indicators: {e}")
    
    return merged


def extract_dynamic_indicators_from_form(form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract dynamic indicator configuration from form data.
    
    Looks for the 'indicatorConfig' field which contains JSON configuration.
    
    Args:
        form_data: Dictionary of form fields
    
    Returns:
        List of indicator configurations
    """
    config_json = form_data.get('indicatorConfig', '[]')
    
    try:
        return json.loads(config_json)
    except (json.JSONDecodeError, TypeError):
        return []


def build_legacy_form_from_dynamic(indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build legacy form field dictionary from dynamic indicator list.
    
    Useful for backward compatibility when converting from new to old system.
    
    Args:
        indicators: List of indicator configurations
    
    Returns:
        Dictionary with legacy field names and values
    """
    form_fields = {}
    
    # Track which types we've seen (to handle multiple instances)
    seen_types = {}
    
    for indicator in indicators:
        if indicator.get('enabled') and indicator.get('comparison') != 'disabled':
            ind_type = indicator['type']
            window = indicator.get('window', 0)
            comparison = indicator.get('comparison', 'disabled')
            percentage = indicator.get('percentage', 0)
            
            # Count how many of this type we've seen
            count = seen_types.get(ind_type, 0)
            seen_types[ind_type] = count + 1
            
            # For the first instance, use the standard field name
            # For subsequent instances, append the count
            suffix = '' if count == 0 else count
            
            form_fields[f'{ind_type}{suffix}'] = window
            form_fields[f'Comparison{ind_type}{suffix}'] = comparison
            form_fields[f'Percentage{ind_type}{suffix}'] = percentage
            form_fields[f'{ind_type}Bool{suffix}'] = 'percentage' if indicator.get('usePercentage') else 'value'
    
    return form_fields


def validate_indicator_config(config_json: str) -> tuple[bool, str]:
    """
    Validate indicator configuration JSON.
    
    Args:
        config_json: JSON string to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        data = json.loads(config_json)
        
        if not isinstance(data, list):
            return False, "Configuration must be a JSON array"
        
        valid_types = {
            'FastSMA', 'MediumSMA', 'SlowSMA', 'SMA1', 'SMA2', 'SMA3',
            'FastEMA', 'SlowEMA', 'EMA1', 'EMA2',
            'RSI', 'VWAP', 'OBV', 'FastOBV', 'MediumOBV', 'SlowOBV',
            'ATR', 'Candlestick1', 'Candlestick2', 'Candlestick3', 'Candlestick4',
            'PrevClose', 'PctChange', 'LowOfDay', 'HighOfDay'
        }
        
        valid_comparisons = {
            'greater', 'greaterEqual', 'lower', 'lowerEqual', 'equal', 'between',
            'withinPercentAbove', 'withinPercentBelow', 'withinPercentEither', 'disabled'
        }
        
        for i, indicator in enumerate(data):
            if not isinstance(indicator, dict):
                return False, f"Indicator {i} must be an object"
            
            # Check required fields
            if 'type' not in indicator:
                return False, f"Indicator {i} missing 'type' field"
            if indicator['type'] not in valid_types:
                return False, f"Indicator {i} invalid type: {indicator['type']}"
            
            if 'comparison' not in indicator:
                return False, f"Indicator {i} missing 'comparison' field"
            if indicator['comparison'] not in valid_comparisons:
                return False, f"Indicator {i} invalid comparison: {indicator['comparison']}"
            
            # Validate numeric fields
            for field in ['window', 'percentage']:
                if field in indicator:
                    try:
                        float(indicator[field])
                    except (ValueError, TypeError):
                        return False, f"Indicator {i} invalid {field}: must be numeric"
        
        return True, ""
    
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"


def get_enabled_indicator_types(config_json: str) -> List[str]:
    """
    Get list of enabled indicator types from configuration.
    
    Args:
        config_json: JSON configuration string
    
    Returns:
        List of enabled indicator type strings
    """
    try:
        data = json.loads(config_json)
        types = []
        
        for indicator in data:
            if indicator.get('enabled', True) and indicator.get('comparison') != 'disabled':
                indicator_type = indicator.get('type')
                if indicator_type:
                    types.append(indicator_type)
        
        return types
    
    except (json.JSONDecodeError, TypeError):
        return []


def get_indicator_count(config_json: str) -> int:
    """
    Get count of enabled indicators in configuration.
    
    Args:
        config_json: JSON configuration string
    
    Returns:
        Number of enabled indicators
    """
    try:
        data = json.loads(config_json)
        count = 0
        
        for indicator in data:
            if indicator.get('enabled', True) and indicator.get('comparison') != 'disabled':
                count += 1
        
        return count
    
    except (json.JSONDecodeError, TypeError):
        return 0


def convert_form_to_indicator_config(
    form_data: Dict[str, Any],
    indicators_to_include: List[str] = None
) -> str:
    """
    Convert legacy form fields to dynamic indicator configuration JSON.
    
    Useful when migrating from old hardcoded system to new dynamic system.
    
    Args:
        form_data: Dictionary of form fields
        indicators_to_include: List of indicator types to include (default: all)
    
    Returns:
        JSON string with indicator configuration
    """
    indicators = []
    indicator_id = 0
    
    legacy_indicators = [
        'FastSMA', 'MediumSMA', 'SlowSMA', 'SMA1', 'SMA2', 'SMA3',
        'FastEMA', 'SlowEMA', 'EMA1', 'EMA2',
        'RSI', 'VWAP', 'OBV', 'FastOBV', 'MediumOBV', 'SlowOBV',
        'ATR', 'Candlestick1', 'Candlestick2', 'Candlestick3', 'Candlestick4',
        'PrevClose', 'PctChange', 'LowOfDay', 'HighOfDay'
    ]
    
    for ind_type in legacy_indicators:
        if indicators_to_include and ind_type not in indicators_to_include:
            continue
        
        comparison = form_data.get(f'Comparison{ind_type}', 'disabled')
        
        # Skip if disabled
        if comparison == 'disabled' or comparison == 'Not used':
            continue
        
        # Get other fields
        window = form_data.get(ind_type, 0)
        percentage = form_data.get(f'Percentage{ind_type}', 0)
        timeframe = form_data.get(f'{ind_type}_tf', '1 day')
        
        try:
            window = int(window) if window else 0
            percentage = float(percentage) if percentage else 0
        except (ValueError, TypeError):
            continue
        
        use_percentage_mode = form_data.get(f'{ind_type}Bool', 'value') == 'percentage'
        indicator = {
            'id': indicator_id,
            'type': ind_type,
            'window': window,
            'comparison': comparison,
            'percentage': percentage,
            'timeframe': timeframe,
            'usePercentage': use_percentage_mode,
            'enabled': True
        }
        
        indicators.append(indicator)
        indicator_id += 1
    
    return json.dumps(indicators)


# Example usage
if __name__ == '__main__':
    # Example configuration
    sample_config = json.dumps([
        {
            'id': 0,
            'type': 'FastSMA',
            'window': 5,
            'comparison': 'greater',
            'percentage': 50,
            'timeframe': '1 day',
            'usePercentage': False,
            'enabled': True
        },
        {
            'id': 1,
            'type': 'RSI',
            'window': 14,
            'comparison': 'lower',
            'percentage': 30,
            'timeframe': '1 day',
            'usePercentage': False,
            'enabled': True
        }
    ])
    
    # Test validation
    is_valid, error = validate_indicator_config(sample_config)
    print(f"Valid: {is_valid}, Error: {error}")
    
    # Test enabled types
    types = get_enabled_indicator_types(sample_config)
    print(f"Enabled types: {types}")
    
    # Test count
    count = get_indicator_count(sample_config)
    print(f"Indicator count: {count}")
