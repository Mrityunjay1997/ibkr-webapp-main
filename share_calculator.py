"""
Share Calculator for Unified Order System

Calculates share quantities based on multiple methods:
1. Fixed quantity - directly specify number of shares
2. From dollar amount - calculate shares based on $ amount and current price
3. From risk percent - calculate shares based on % risk of account

Used by all three order modes (off-book, automated, manual).
"""

import logging
from typing import Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger("share_calculator")


class ShareCalculator:
    """Calculates share quantities for orders"""
    
    @staticmethod
    def calculate_from_fixed_quantity(quantity: int) -> Tuple[int, str]:
        """
        Use fixed quantity directly.
        
        Args:
            quantity: Number of shares
        
        Returns:
            (shares, error_message)
        """
        if quantity <= 0:
            return 0, "Quantity must be positive"
        
        return quantity, ""
    
    @staticmethod
    def calculate_from_amount(
        amount_dollars: float,
        current_price: float,
        round_method: str = 'down',
    ) -> Tuple[int, str]:
        """
        Calculate shares from dollar amount.
        
        Args:
            amount_dollars: Dollar amount to use
            current_price: Current price of the stock
            round_method: 'down', 'up', or 'round' (banker's rounding)
        
        Returns:
            (shares, error_message)
        
        Examples:
            $1000 / $50.00 = 20 shares
            $1000 / $50.25 = 19.9004... shares → 19 shares (round down)
        """
        if amount_dollars <= 0:
            return 0, "Amount must be positive"
        
        if current_price <= 0:
            return 0, "Current price must be positive"
        
        try:
            # Use Decimal for precise calculation
            amount = Decimal(str(amount_dollars))
            price = Decimal(str(current_price))
            
            shares_decimal = amount / price
            
            # Round based on method
            if round_method == 'down':
                shares = int(shares_decimal)
            elif round_method == 'up':
                shares = int(shares_decimal) if shares_decimal == int(shares_decimal) else int(shares_decimal) + 1
            elif round_method == 'round':
                shares = int(shares_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                shares = int(shares_decimal)
            
            if shares <= 0:
                return 0, f"Amount ${amount_dollars} is too small for price ${current_price}"
            
            logger.info(f"Calculated {shares} shares from ${amount_dollars} at ${current_price}")
            return shares, ""
        
        except Exception as e:
            return 0, f"Error calculating shares: {str(e)}"
    
    @staticmethod
    def calculate_from_percent_risk(
        account_size: float,
        risk_percent: float,
        entry_price: float,
        stop_price: float,
        round_method: str = 'down',
    ) -> Tuple[int, str]:
        """
        Calculate shares based on risk management.
        
        Risk = account_size × risk_percent / (entry_price - stop_price)
        
        Args:
            account_size: Total account size in dollars
            risk_percent: Percent of account to risk per trade (e.g., 1.0 = 1%)
            entry_price: Entry price
            stop_price: Stop-loss price
            round_method: 'down', 'up', or 'round'
        
        Returns:
            (shares, error_message)
        
        Examples:
            Account: $100,000
            Risk: 1% = $1,000
            Entry: $50, Stop: $49
            Risk per share: $1
            Shares: $1,000 / $1 = 1,000 shares
        """
        if account_size <= 0:
            return 0, "Account size must be positive"
        
        if risk_percent <= 0 or risk_percent > 100:
            return 0, "Risk percent must be between 0 and 100"
        
        if entry_price <= 0:
            return 0, "Entry price must be positive"
        
        if stop_price is None:
            return 0, "Stop price required for risk-based calculation"
        
        # Calculate risk in dollars
        risk_dollars = (account_size * risk_percent) / 100.0
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_price)
        
        if risk_per_share <= 0:
            return 0, "Entry price and stop price must be different"
        
        try:
            # Calculate shares
            account_dec = Decimal(str(account_size))
            risk_pct_dec = Decimal(str(risk_percent))
            entry_dec = Decimal(str(entry_price))
            stop_dec = Decimal(str(stop_price))
            
            risk_dollars_dec = (account_dec * risk_pct_dec) / 100
            risk_per_share_dec = abs(entry_dec - stop_dec)
            
            shares_decimal = risk_dollars_dec / risk_per_share_dec
            
            # Round based on method
            if round_method == 'down':
                shares = int(shares_decimal)
            elif round_method == 'up':
                shares = int(shares_decimal) if shares_decimal == int(shares_decimal) else int(shares_decimal) + 1
            elif round_method == 'round':
                shares = int(shares_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            else:
                shares = int(shares_decimal)
            
            if shares <= 0:
                return 0, f"Calculated shares is zero or negative"
            
            actual_risk = shares * risk_per_share
            logger.info(
                f"Calculated {shares} shares from risk (${account_size} account, "
                f"{risk_percent}% risk, ${risk_per_share} risk/share) = ${actual_risk:.2f} risk"
            )
            
            return shares, ""
        
        except Exception as e:
            return 0, f"Error calculating risk-based shares: {str(e)}"
    
    @staticmethod
    def calculate_partial_position_shares(
        total_position_shares: int,
        percent_of_position: float,
    ) -> Tuple[int, str]:
        """
        Calculate shares to exit for a partial position exit.
        
        Used for multi-level exit targets. Ensures allocations add up properly.
        
        Args:
            total_position_shares: Total shares in position
            percent_of_position: Percent to exit (0-100)
        
        Returns:
            (shares_to_exit, error_message)
        
        Examples:
            Position: 100 shares
            Exit at Fib 61.8%: 50% → 50 shares
            Exit at +30%: 30% → 30 shares
            Exit on trailing stop: 20% → 20 shares
        """
        if total_position_shares <= 0:
            return 0, "Total position must be positive"
        
        if percent_of_position <= 0 or percent_of_position > 100:
            return 0, "Percent of position must be 0-100"
        
        try:
            shares_dec = Decimal(str(total_position_shares))
            percent_dec = Decimal(str(percent_of_position))
            
            exit_shares_decimal = (shares_dec * percent_dec) / 100
            exit_shares = int(exit_shares_decimal)
            
            if exit_shares <= 0:
                return 0, f"Calculated exit shares is zero"
            
            if exit_shares > total_position_shares:
                return total_position_shares, f"Capped exit to total position ({total_position_shares})"
            
            return exit_shares, ""
        
        except Exception as e:
            return 0, f"Error calculating partial exit: {str(e)}"


# =============================================================================
# STANDALONE CONVENIENCE FUNCTIONS
# =============================================================================

def calculate_shares_fixed(quantity: int) -> Tuple[int, str]:
    """Calculate using fixed quantity"""
    return ShareCalculator.calculate_from_fixed_quantity(quantity)


def calculate_shares_from_amount(
    amount_dollars: float,
    current_price: float,
) -> Tuple[int, str]:
    """Calculate shares from dollar amount"""
    return ShareCalculator.calculate_from_amount(amount_dollars, current_price)


def calculate_shares_from_risk(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
) -> Tuple[int, str]:
    """Calculate shares from risk percent"""
    return ShareCalculator.calculate_from_percent_risk(
        account_size, risk_percent, entry_price, stop_price
    )


def calculate_position_exit(
    total_shares: int,
    exit_percent: float,
) -> Tuple[int, str]:
    """Calculate partial position exit"""
    return ShareCalculator.calculate_partial_position_shares(total_shares, exit_percent)
