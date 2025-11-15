"""
Address verification utilities using pypostal
"""
from typing import Dict, Optional

# Try to import pypostal, but make it optional
try:
    import postal.parser
    import postal.expand
    PYPOSTAL_AVAILABLE = True
except ImportError:
    PYPOSTAL_AVAILABLE = False


def verify_address(address: str) -> Dict[str, any]:
    """
    Verify and parse an address using pypostal.

    Args:
        address: The address string to verify

    Returns:
        Dict with 'is_valid', 'parsed_components', 'normalized_address', 'issues'
    """
    if not address or not address.strip():
        return {
            'is_valid': False,
            'parsed_components': {},
            'normalized_address': '',
            'issues': ['Address is empty']
        }

    if not PYPOSTAL_AVAILABLE:
        # Basic validation without pypostal
        issues = []
        lines = [line.strip() for line in address.split('\n') if line.strip()]

        if len(lines) < 2:
            issues.append("Address seems incomplete - typically needs name, street, city/country")

        return {
            'is_valid': len(issues) == 0,
            'parsed_components': {},
            'normalized_address': address,
            'issues': issues
        }

    try:
        # Parse the address into components
        parsed = postal.parser.parse_address(address)
        parsed_dict = dict(parsed)

        # Expand/normalize the address
        expanded = postal.expand.expand_address(address)
        normalized = expanded[0] if expanded else address

        # Check for common issues
        issues = []

        found_components = set(parsed_dict.keys())

        # Check if we have basic address components
        has_house_number = 'house_number' in found_components
        has_road = 'road' in found_components
        has_city = 'city' in found_components
        has_postcode = 'postcode' in found_components
        has_country = 'country' in found_components

        if not has_house_number and not has_road:
            issues.append("Missing street address (house number and street name)")

        if not has_city:
            issues.append("Missing city")

        if not has_postcode:
            issues.append("Missing postal code")

        if not has_country:
            issues.append("Missing country")

        # Check for potential formatting issues
        if ',' in address and len(address.split(',')) < 3:
            issues.append("Address might be missing proper formatting (name, street, city/country)")

        # Check if address seems too short
        if len(address.strip().split('\n')) < 3:
            issues.append("Address seems incomplete - typically needs name, street, city/country")

        is_valid = len(issues) == 0

        return {
            'is_valid': is_valid,
            'parsed_components': parsed_dict,
            'normalized_address': normalized,
            'issues': issues
        }

    except Exception as e:
        return {
            'is_valid': False,
            'parsed_components': {},
            'normalized_address': address,
            'issues': [f'Error parsing address: {str(e)}']
        }


def get_address_hint(address: str) -> Optional[str]:
    """
    Get a user-friendly hint about potential address issues.

    Args:
        address: The address to check

    Returns:
        A hint string if there are issues, None if address looks good
    """
    verification = verify_address(address)

    if verification['is_valid']:
        return None

    issues = verification['issues']
    if not issues:
        return None

    # Return the most important issue as a hint
    return issues[0]