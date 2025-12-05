# tactizen/app/models/__init__.py

from app.extensions import db

# Import models and association tables/enums from their respective files
# Ensure you import from the consolidated 'location.py'
from .location import Country, Region, MilitaryInventory, RegionalConstruction, RegionalResource, country_regions, region_neighbors
from .resource import Resource, ResourceCategory, InventoryItem, CountryMarketItem, ActiveResidence
from .user import User
# Import GoldMarket from its file
from .currency_market import GoldMarket, CurrencyPriceHistory
# Import ZEN market models
from .zen_market import ZenMarket, ZenPriceHistory, ZenTransaction
# Import currency models
from .currency import UserCurrency, FinancialTransaction, log_transaction
# Import activity tracking models
from .activity import ActivityLog, ActivityType, UserSession
# Import party models
from .party import PoliticalParty, PartyMembership, PartyElection, PartyCandidate, PartyVote, ElectionStatus
# Import referral models
from .referral import Referral, ReferralStatus
# Import messaging models
from .messaging import Message, Alert, BlockedUser, AlertType, AlertPriority
# Import company models
from .company import (
    Company, CompanyType, JobOffer, Employment, CompanyInventory,
    CompanyTransaction, CompanyTransactionType, ExportLicense,
    CompanyProductionProgress
)
# Import time allocation models
from .time_allocation import TimeAllocation, WorkSession
# Import newspaper models
from .newspaper import Newspaper, Article, ArticleVote, NewspaperSubscription, ArticleComment
# Import friendship models
from .friendship import Friendship, FriendshipStatus
# Import achievement models
from .achievement import Achievement, UserAchievement, AchievementProgress, AchievementCategory
# Import security log models
from .security_log import SecurityLog, SecurityEventType, SecurityLogSeverity, log_security_event, get_request_info
# Import API token models
from .api_token import APIToken, APITokenScope
# Import government/election models
from .government import (
    GovernmentElection, ElectionCandidate, ElectionVote,
    CountryPresident, CongressMember, Minister, Law, LawVote,
    War, PeaceVote, Embargo,
    ElectionType, GovernmentElectionStatus, CandidateStatus,
    MinistryType, LawType, LawStatus, WarStatus, WarType
)
# Import NFT models
from .nft import (
    NFTInventory, PlayerNFTSlots, CompanyNFTSlots,
    NFTBurnHistory, NFTDropHistory, NFTMarketplace, NFTTradeHistory
)
# Import military rank models
from .military_rank import MilitaryRank
# Import battle models
from .battle import (
    MutualProtectionPact, Battle, BattleRound, BattleParticipation,
    BattleDamage, BattleHero, BattleStatus, RoundStatus, WallType
)
# Import support/ticketing models
from .support import (
    SupportTicket, TicketResponse, TicketAuditLog, CannedResponse,
    Report, UserMute, TicketCategory, TicketStatus, TicketPriority,
    ReportType, ReportReason, ReportStatus, ReportAction, AuditActionType
)
# Import alliance models
from .alliance import (
    Alliance, AllianceMembership, AllianceInvitation, AllianceKick,
    AllianceLeave, AllianceDissolution, AllianceInvitationStatus, AllianceKickStatus
)
# Import military unit models
from .military_unit import (
    MilitaryUnit, MilitaryUnitMember, MilitaryUnitApplication,
    MilitaryUnitInventory, MilitaryUnitTransaction, MilitaryUnitMessage,
    BountyContract, BountyContractApplication, MilitaryUnitAchievement,
    MilitaryUnitRank, BountyContractStatus
)
# Import game update models
from .game_update import GameUpdate, UpdateCategory
# Import mission models
from .mission import Mission, UserMission, MissionType, MissionCategory

# Define __all__ to specify what gets imported with 'from app.models import *'
__all__ = [
    'db',
    'User',
    'Country',        # Imported from location.py
    'Region',         # Imported from location.py
    'country_regions',# Imported from location.py
    'region_neighbors',# Imported from location.py
    'MilitaryInventory', # Imported from location.py
    'RegionalConstruction', # Imported from location.py
    'RegionalResource',  # Imported from location.py
    'Resource',
    'ResourceCategory',
    'InventoryItem',
    'CountryMarketItem',
    'ActiveResidence',
    'GoldMarket',     # Imported from currency_market.py
    'CurrencyPriceHistory', # Imported from currency_market.py
    'ZenMarket',      # Imported from zen_market.py
    'ZenPriceHistory', # Imported from zen_market.py
    'ZenTransaction', # Imported from zen_market.py
    'UserCurrency',   # Imported from currency.py
    'FinancialTransaction',  # Imported from currency.py
    'log_transaction', # Helper function
    'ActivityLog',    # Imported from activity.py
    'ActivityType',   # Imported from activity.py
    'UserSession',    # Imported from activity.py
    'PoliticalParty', # Imported from party.py
    'PartyMembership',# Imported from party.py
    'PartyElection',  # Imported from party.py
    'PartyCandidate', # Imported from party.py
    'PartyVote',      # Imported from party.py
    'ElectionStatus', # Imported from party.py
    'Referral',       # Imported from referral.py
    'ReferralStatus', # Imported from referral.py
    'Message',        # Imported from messaging.py
    'Alert',          # Imported from messaging.py
    'BlockedUser',    # Imported from messaging.py
    'AlertType',      # Imported from messaging.py
    'AlertPriority',  # Imported from messaging.py
    'Company',        # Imported from company.py
    'CompanyType',    # Imported from company.py
    'JobOffer',       # Imported from company.py
    'Employment',     # Imported from company.py
    'CompanyInventory', # Imported from company.py
    'CompanyTransaction', # Imported from company.py
    'CompanyTransactionType', # Imported from company.py
    'ExportLicense',  # Imported from company.py
    'CompanyProductionProgress', # Imported from company.py
    'TimeAllocation', # Imported from time_allocation.py
    'WorkSession',    # Imported from time_allocation.py
    'Newspaper',      # Imported from newspaper.py
    'Article',        # Imported from newspaper.py
    'ArticleVote',    # Imported from newspaper.py
    'NewspaperSubscription', # Imported from newspaper.py
    'ArticleComment', # Imported from newspaper.py
    'Friendship',     # Imported from friendship.py
    'FriendshipStatus', # Imported from friendship.py
    'Achievement',    # Imported from achievement.py
    'UserAchievement', # Imported from achievement.py
    'AchievementProgress', # Imported from achievement.py
    'AchievementCategory', # Imported from achievement.py
    'SecurityLog',    # Imported from security_log.py
    'SecurityEventType', # Imported from security_log.py
    'SecurityLogSeverity', # Imported from security_log.py
    'log_security_event', # Helper function
    'get_request_info', # Helper function
    'APIToken',       # Imported from api_token.py
    'APITokenScope',  # Imported from api_token.py
    'GovernmentElection',  # Imported from government.py
    'ElectionCandidate',   # Imported from government.py
    'ElectionVote',        # Imported from government.py
    'CountryPresident',    # Imported from government.py
    'CongressMember',      # Imported from government.py
    'Minister',            # Imported from government.py
    'Law',                 # Imported from government.py
    'LawVote',             # Imported from government.py
    'ElectionType',        # Imported from government.py
    'GovernmentElectionStatus',  # Imported from government.py
    'CandidateStatus',     # Imported from government.py
    'MinistryType',        # Imported from government.py
    'LawType',             # Imported from government.py
    'LawStatus',           # Imported from government.py
    'War',                 # Imported from government.py
    'PeaceVote',           # Imported from government.py
    'WarStatus',           # Imported from government.py
    'Embargo',             # Imported from government.py
    'NFTInventory',        # Imported from nft.py
    'PlayerNFTSlots',      # Imported from nft.py
    'CompanyNFTSlots',     # Imported from nft.py
    'NFTBurnHistory',      # Imported from nft.py
    'NFTDropHistory',      # Imported from nft.py
    'NFTMarketplace',      # Imported from nft.py
    'NFTTradeHistory',     # Imported from nft.py
    'MilitaryRank',        # Imported from military_rank.py
    'MutualProtectionPact',  # Imported from battle.py
    'Battle',              # Imported from battle.py
    'BattleRound',         # Imported from battle.py
    'BattleParticipation', # Imported from battle.py
    'BattleDamage',        # Imported from battle.py
    'BattleHero',          # Imported from battle.py
    'BattleStatus',        # Imported from battle.py
    'RoundStatus',         # Imported from battle.py
    'WallType',            # Imported from battle.py
    'SupportTicket',       # Imported from support.py
    'TicketResponse',      # Imported from support.py
    'TicketAuditLog',      # Imported from support.py
    'CannedResponse',      # Imported from support.py
    'Report',              # Imported from support.py
    'UserMute',            # Imported from support.py
    'TicketCategory',      # Imported from support.py
    'TicketStatus',        # Imported from support.py
    'TicketPriority',      # Imported from support.py
    'ReportType',          # Imported from support.py
    'ReportReason',        # Imported from support.py
    'ReportStatus',        # Imported from support.py
    'ReportAction',        # Imported from support.py
    'AuditActionType',     # Imported from support.py
    'Alliance',            # Imported from alliance.py
    'AllianceMembership',  # Imported from alliance.py
    'AllianceInvitation',  # Imported from alliance.py
    'AllianceKick',        # Imported from alliance.py
    'AllianceLeave',       # Imported from alliance.py
    'AllianceDissolution', # Imported from alliance.py
    'AllianceInvitationStatus',  # Imported from alliance.py
    'AllianceKickStatus',  # Imported from alliance.py
    # Military Unit models
    'MilitaryUnit',            # Imported from military_unit.py
    'MilitaryUnitMember',      # Imported from military_unit.py
    'MilitaryUnitApplication', # Imported from military_unit.py
    'MilitaryUnitInventory',   # Imported from military_unit.py
    'MilitaryUnitTransaction', # Imported from military_unit.py
    'MilitaryUnitMessage',     # Imported from military_unit.py
    'BountyContract',          # Imported from military_unit.py
    'BountyContractApplication', # Imported from military_unit.py
    'MilitaryUnitAchievement', # Imported from military_unit.py
    'MilitaryUnitRank',        # Imported from military_unit.py
    'BountyContractStatus',    # Imported from military_unit.py
    # Game Update models
    'GameUpdate',              # Imported from game_update.py
    'UpdateCategory',          # Imported from game_update.py
    # Mission models
    'Mission',                 # Imported from mission.py
    'UserMission',             # Imported from mission.py
    'MissionType',             # Imported from mission.py
    'MissionCategory',         # Imported from mission.py
]