# app/exceptions.py
"""Custom exceptions for the Tactizen application."""


class TactizenException(Exception):
    """Base exception for all application-specific exceptions."""
    pass


# --- User/Account Exceptions ---

class InsufficientFundsError(TactizenException):
    """Raised when user doesn't have enough currency/gold."""
    pass


class InsufficientWellnessError(TactizenException):
    """Raised when user doesn't have enough wellness."""
    pass


class InsufficientExperienceError(TactizenException):
    """Raised when user doesn't have enough experience."""
    pass


class DailyCooldownError(TactizenException):
    """Raised when trying to perform action that's on cooldown."""
    pass


# --- Inventory Exceptions ---

class InsufficientInventoryError(TactizenException):
    """Raised when user doesn't have enough items in inventory."""
    pass


class InventoryFullError(TactizenException):
    """Raised when inventory has reached maximum capacity."""
    pass


class InvalidResourceError(TactizenException):
    """Raised when resource doesn't exist or is invalid."""
    pass


# --- Market Exceptions ---

class MarketTransactionError(TactizenException):
    """Base exception for market transaction errors."""
    pass


class InsufficientMarketVolumeError(MarketTransactionError):
    """Raised when trying to buy/sell more than available at current price level."""
    pass


class MarketNotFoundError(MarketTransactionError):
    """Raised when market item doesn't exist."""
    pass


# --- Location Exceptions ---

class InvalidLocationError(TactizenException):
    """Raised when region/country doesn't exist or is invalid."""
    pass


class AlreadyAtLocationError(TactizenException):
    """Raised when trying to travel to current location."""
    pass


# --- Validation Exceptions ---

class InvalidAmountError(TactizenException):
    """Raised when amount is negative, zero, or invalid."""
    pass


class InvalidSkillTypeError(TactizenException):
    """Raised when skill type is not recognized."""
    pass


# --- Transaction Exceptions ---

class TransactionFailedError(TactizenException):
    """Raised when a transaction fails to complete."""
    pass


class ConcurrentTransactionError(TactizenException):
    """Raised when a concurrent transaction conflict occurs."""
    pass
