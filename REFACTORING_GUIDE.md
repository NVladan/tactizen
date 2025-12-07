# User Model Refactoring - Implementation Guide

## Overview

The User model has been refactored from **1,738 lines with 57 methods** into **6 service classes**:

1. **InventoryService** - Inventory management (6 methods, ~170 lines)
2. **CurrencyService** - Currency operations (10 methods, ~220 lines)
3. **SkillService** - Training and skill progression (5 methods, ~350 lines)
4. **EmploymentService** - Work allocation and production (4 methods, ~300 lines)
5. **WellnessService** - Food consumption and residence (3 methods, ~250 lines)
6. **SocialService** - Friendships and referrals (8 methods, ~200 lines)

## Status: COMPLETED

All services have been implemented and are being used throughout the application.

### Service Files (in `app/services/`):
- `inventory_service.py`
- `currency_service.py`
- `skill_service.py`
- `employment_service.py`
- `wellness_service.py`
- `social_service.py`

### Additional Services Added:
- `battle_service.py` - Battle system logic
- `mission_service.py` - Missions and rewards
- `achievement_service.py` - Achievements tracking
- `alliance_service.py` - Alliance operations
- `nft_service.py` - NFT management
- `bonus_calculator.py` - NFT bonus calculations

## Method Mapping Reference

### InventoryService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.get_total_inventory_count()` | `InventoryService.get_total_count(user)` |
| `user.get_available_storage_space()` | `InventoryService.get_available_storage(user)` |
| `user.get_inventory_item(r, q)` | `InventoryService.get_item(user, r, q)` |
| `user.get_resource_quantity(r, q)` | `InventoryService.get_resource_quantity(user, r, q)` |
| `user.add_to_inventory(r, q, ql)` | `InventoryService.add_item(user, r, q, ql)` |
| `user.remove_from_inventory(r, q, ql)` | `InventoryService.remove_item(user, r, q, ql)` |

### CurrencyService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.get_currency_amount(c)` | `CurrencyService.get_amount(user, c)` |
| `user.local_currency` | `CurrencyService.get_local_currency(user)` |
| `user.local_currency_code` | `CurrencyService.get_local_currency_code(user)` |
| `user.all_currencies` | `CurrencyService.get_all_currencies(user)` |
| `user.add_currency(c, a)` | `CurrencyService.add_currency(user, c, a)` |
| `user.remove_currency(c, a)` | `CurrencyService.remove_currency(user, c, a)` |
| `user.has_sufficient_currency(c, a)` | `CurrencyService.has_sufficient(user, c, a)` |
| `user.safe_remove_currency(c, a)` | `CurrencyService.safe_remove(user, c, a)` |

### SkillService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.train_skill(type)` | `SkillService.train_skill(user, type)` |
| `user.study_skill(type)` | `SkillService.study_skill(user, type)` |
| `user.get_skill_for_company_type(type)` | `SkillService.get_skill_for_company_type(user, type)` |
| `user.allocate_training_hours(type, hours)` | `SkillService.allocate_training_hours(user, type, hours)` |
| `user.allocate_studying_hours(type, hours)` | `SkillService.allocate_studying_hours(user, type, hours)` |

### EmploymentService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.get_today_allocation()` | `EmploymentService.get_today_allocation(user)` |
| `user.get_remaining_hours_today()` | `EmploymentService.get_remaining_hours(user)` |
| `user.can_allocate_hours(type, hours)` | `EmploymentService.can_allocate_hours(user, type, hours)` |
| `user.allocate_work_hours(emp_id, hours)` | `EmploymentService.allocate_work_hours(user, emp_id, hours)` |

### WellnessService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.eat_bread(qty, quality)` | `WellnessService.eat_bread(user, qty, quality)` |
| `user.drink_beer(qty, quality)` | `WellnessService.drink_beer(user, qty, quality)` |
| `user.process_residence_restoration()` | `WellnessService.process_residence_restoration(user)` |

### SocialService
| Old User Method | New Service Method |
|-----------------|-------------------|
| `user.get_friendship_status(other_id)` | `SocialService.get_friendship_status(user, other_id)` |
| `user.are_friends(other_id)` | `SocialService.are_friends(user, other_id)` |
| `user.get_friends()` | `SocialService.get_friends(user)` |
| `user.get_pending_friend_requests()` | `SocialService.get_pending_requests(user)` |
| `user.generate_referral_code()` | `SocialService.generate_referral_code(user)` |
| `user.check_and_award_referral_bonus()` | `SocialService.check_and_award_referral_bonus(user)` |
| `user.referrer` | `SocialService.get_referrer(user)` |
| `user.referral_stats` | `SocialService.get_referral_stats(user)` |

## Performance Benefits

- User model reduced to core properties and relationships
- Each service: 150-350 lines (easier to understand)
- Better testability (test services independently)
- Better performance (can optimize services separately)
- Better code organization (Single Responsibility Principle)
