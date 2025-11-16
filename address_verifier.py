"""
Address verification utilities using postal server API
"""
import os
from typing import Dict, Optional

import requests

# Get postal server URL from environment
POSTAL_URL = os.getenv('POSTAL_URL', 'http://localhost:8000')
POSTAL_AVAILABLE = False

# Check if postal service is available
try:
    response = requests.get(f"{POSTAL_URL}/health", timeout=5)
    if response.status_code == 200 and response.json().get('status') == 'ok':
        POSTAL_AVAILABLE = True
except Exception:
    POSTAL_AVAILABLE = False


def _validate_address_locally(address: str) -> Dict[str, any]:
    """
    Local address validation and parsing without postal service.
    
    Args:
        address: The address string to validate
        
    Returns:
        Dict with validation results
    """
    import re
    
    if not address or not address.strip():
        return {
            'is_valid': False,
            'parsed_components': {},
            'normalized_address': '',
            'issues': ['Address is empty']
        }
    
    lines = [line.strip() for line in address.split('\n') if line.strip()]
    issues = []
    parsed_components = {}
    
    if len(lines) < 3:
        issues.append("Address seems incomplete - typically needs name, street, city/country")
    
    if len(lines) >= 1:
        # First line is usually the name
        parsed_components['house'] = lines[0].title()
    
    if len(lines) >= 2:
        # Second line is usually street and house number
        street_line = lines[1]
        
        # Try to extract house number from the end
        # Look for number at the end of the line
        house_number_match = re.search(r'(\d+)\s*$', street_line)
        if house_number_match:
            parsed_components['house_number'] = house_number_match.group(1)
            # Remove the house number from street
            street = street_line[:house_number_match.start()].strip()
            if street:
                parsed_components['road'] = street.title()
        else:
            # No house number found, treat whole line as road
            parsed_components['road'] = street_line.title()
    
    if len(lines) >= 3:
        # Third line is usually city and postcode
        city_line = lines[2]
        
        # Try to extract postcode (German format: 5 digits)
        postcode_match = re.search(r'\b(\d{5})\b', city_line)
        if postcode_match:
            parsed_components['postcode'] = postcode_match.group(1)
            # Remove postcode from city line
            city = re.sub(r'\b\d{5}\b', '', city_line).strip()
            if city:
                parsed_components['city'] = city.title()
        else:
            # No postcode found, treat as city
            parsed_components['city'] = city_line.title()
    
    if len(lines) >= 4:
        # Fourth line is usually country
        parsed_components['country'] = lines[3].title()
    
    # Check for required components
    found_components = set(parsed_components.keys())
    
    has_road = 'road' in found_components
    has_city = 'city' in found_components
    has_postcode = 'postcode' in found_components
    has_country = 'country' in found_components
    
    if not has_road:
        issues.append("Missing street address")
    
    if not has_city:
        issues.append("Missing city")
    
    if not has_postcode:
        issues.append("Missing postal code")
    
    if not has_country:
        issues.append("Missing country")
    
    # Additional checks
    if has_postcode and not re.match(r'^\d{5}$', parsed_components.get('postcode', '')):
        issues.append("Postal code should be 5 digits")
    
    is_valid = len(issues) == 0
    
    return {
        'is_valid': is_valid,
        'parsed_components': parsed_components,
        'normalized_address': address,  # Keep original for now
        'issues': issues
    }


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

    if not POSTAL_AVAILABLE:
        # Local validation without postal service
        return _validate_address_locally(address)

    try:
        # Parse the address using the API
        parse_response = requests.get(f"{POSTAL_URL}/parse", params={'address': address}, timeout=10)
        if parse_response.status_code != 200:
            raise Exception(f"Parse API returned {parse_response.status_code}")
        
        parsed = parse_response.json()
        parsed_dict = {item['label']: item['value'] for item in parsed}

        # Apply title case to parsed components for better display
        parsed_dict = {label: value.title() for label, value in parsed_dict.items()}

        # Expand/normalize the address
        expand_response = requests.get(f"{POSTAL_URL}/expand", params={'address': address}, timeout=10)
        if expand_response.status_code == 200:
            expanded = expand_response.json()
            normalized = expanded[0] if expanded else address
        else:
            normalized = address

        # Check for common issues
        issues = []

        found_components = set(parsed_dict.keys())

        # Check if we have basic address components
        has_house_number = 'house_number' in found_components
        has_road = 'road' in found_components
        has_city = 'city' in found_components or 'city_district' in found_components
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