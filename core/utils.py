"""
Utility functions for the Coffee XRPL Platform
"""

from datetime import datetime
from typing import Optional


def generate_user_id(full_name: str, xrpl_address: str) -> str:
    """
    Generate a unique user ID from name and XRPL address.
    
    Format: [Initials][First 3 chars of XRPL][Last 3 chars of XRPL]
    Example: "Juan Pérez" + "rN7n7otQDd6FczFgLdlqtyMVrn3e5PcjXd" -> "JPrN7Xd"
    
    Args:
        full_name: User's full name
        xrpl_address: XRPL address
        
    Returns:
        Generated user ID
    """
    # Get initials (first letter of each word)
    words = full_name.strip().split()
    initials = ''.join([word[0].upper() for word in words if word])
    
    # Get XRPL fragments (skip the 'r' prefix)
    xrpl_clean = xrpl_address[1:] if xrpl_address.startswith('r') else xrpl_address
    first_three = xrpl_clean[:3]
    last_three = xrpl_clean[-3:]
    
    return f"{initials}{first_three}{last_three}"


def format_currency(amount: float, currency: str = "MXN") -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Numeric amount
        currency: Currency code
        
    Returns:
        Formatted string
    """
    if currency == "MXN":
        return f"${amount:,.2f} MXN"
    elif currency == "XRP":
        return f"{amount:.6f} XRP"
    else:
        return f"{amount:.2f} {currency}"


def format_datetime_display(dt: datetime, include_time: bool = True) -> str:
    """
    Format datetime for display in UI.
    
    Args:
        dt: Datetime object
        include_time: Whether to include time
        
    Returns:
        Formatted string
    """
    if include_time:
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    else:
        return dt.strftime("%d/%m/%Y")


def validate_rfc(rfc: str) -> bool:
    """
    Basic RFC (Mexico tax ID) validation.
    
    Args:
        rfc: RFC string
        
    Returns:
        True if format appears valid
    """
    # RFC can be 12 (moral person) or 13 (physical person) characters
    rfc = rfc.strip().upper()
    return len(rfc) in [12, 13] and rfc.isalnum()


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate text with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def calculate_payment_total(weight_kg: float, price_per_kg: float) -> float:
    """
    Calculate total payment amount.
    
    Args:
        weight_kg: Weight in kilograms
        price_per_kg: Price per kilogram
        
    Returns:
        Total amount
    """
    return round(weight_kg * price_per_kg, 2)
