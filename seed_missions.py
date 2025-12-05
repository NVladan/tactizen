"""
Seed script for initial mission data.

Run with: flask seed-missions
Or directly: python seed_missions.py
"""

import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.mission import Mission, MissionType, MissionCategory


def seed_missions():
    """Seed the database with initial mission data."""

    # Daily Missions (5 assigned per day, random from pool)
    # Gold rewards at 1/10 of original values
    daily_missions = [
        {
            'code': 'daily_fight_5',
            'name': 'Warrior',
            'description': 'Fight 5 times in battle',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.COMBAT.value,
            'icon': 'fa-fist-raised',
            'action_type': 'fight',
            'requirement_count': 5,
            'gold_reward': 0.2,
            'xp_reward': 10,
        },
        {
            'code': 'daily_fight_10',
            'name': 'Battle Hardened',
            'description': 'Fight 15 times in battle',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.COMBAT.value,
            'icon': 'fa-shield-alt',
            'action_type': 'fight',
            'requirement_count': 15,
            'gold_reward': 0.5,
            'xp_reward': 20,
        },
        {
            'code': 'daily_work_1',
            'name': 'Hard Worker',
            'description': 'Work at least 6 hours today',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.WORK.value,
            'icon': 'fa-briefcase',
            'action_type': 'work',
            'requirement_count': 6,
            'gold_reward': 0.2,
            'xp_reward': 5,
        },
        {
            'code': 'daily_train_1',
            'name': 'Military Training',
            'description': 'Train for at least 6 hours today',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.TRAINING.value,
            'icon': 'fa-dumbbell',
            'action_type': 'train',
            'requirement_count': 6,
            'gold_reward': 0.1,
            'xp_reward': 5,
        },
        {
            'code': 'daily_study_1',
            'name': 'Scholar',
            'description': 'Study for at least 6 hours today',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.STUDY.value,
            'icon': 'fa-book',
            'action_type': 'study',
            'requirement_count': 6,
            'gold_reward': 0.1,
            'xp_reward': 5,
        },
        {
            'code': 'daily_travel_1',
            'name': 'Explorer',
            'description': 'Travel to a different region',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.EXPLORATION.value,
            'icon': 'fa-plane',
            'action_type': 'travel',
            'requirement_count': 1,
            'gold_reward': 0.1,
            'xp_reward': 3,
        },
        {
            'code': 'daily_market_buy',
            'name': 'Shopper',
            'description': 'Buy 5 items from the market',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.ECONOMIC.value,
            'icon': 'fa-shopping-cart',
            'action_type': 'market_buy',
            'requirement_count': 5,
            'gold_reward': 0.1,
            'xp_reward': 3,
        },
        {
            'code': 'daily_market_sell',
            'name': 'Merchant',
            'description': 'Sell 5 items on the market',
            'mission_type': MissionType.DAILY.value,
            'category': MissionCategory.ECONOMIC.value,
            'icon': 'fa-store',
            'action_type': 'market_sell',
            'requirement_count': 5,
            'gold_reward': 0.1,
            'xp_reward': 3,
        },
    ]

    # Weekly Missions (3 assigned per week)
    # Gold rewards at 1/5 of original values
    weekly_missions = [
        {
            'code': 'weekly_fight_50',
            'name': 'Warmonger',
            'description': 'Fight 50 times this week',
            'mission_type': MissionType.WEEKLY.value,
            'category': MissionCategory.COMBAT.value,
            'icon': 'fa-skull-crossbones',
            'action_type': 'fight',
            'requirement_count': 50,
            'gold_reward': 3.0,
            'xp_reward': 50,
        },
        {
            'code': 'weekly_work_7',
            'name': 'Dedicated Worker',
            'description': 'Work 40 hours this week',
            'mission_type': MissionType.WEEKLY.value,
            'category': MissionCategory.WORK.value,
            'icon': 'fa-hard-hat',
            'action_type': 'work',
            'requirement_count': 40,
            'gold_reward': 2.0,
            'xp_reward': 30,
        },
        {
            'code': 'weekly_train_7',
            'name': 'Military Expert',
            'description': 'Train for 40 hours this week',
            'mission_type': MissionType.WEEKLY.value,
            'category': MissionCategory.TRAINING.value,
            'icon': 'fa-medal',
            'action_type': 'train',
            'requirement_count': 40,
            'gold_reward': 2.0,
            'xp_reward': 30,
        },
        {
            'code': 'weekly_study_7',
            'name': 'Academic',
            'description': 'Study for 40 hours this week',
            'mission_type': MissionType.WEEKLY.value,
            'category': MissionCategory.STUDY.value,
            'icon': 'fa-graduation-cap',
            'action_type': 'study',
            'requirement_count': 40,
            'gold_reward': 2.0,
            'xp_reward': 30,
        },
        {
            'code': 'weekly_travel_10',
            'name': 'World Traveler',
            'description': 'Travel to 10 different regions this week',
            'mission_type': MissionType.WEEKLY.value,
            'category': MissionCategory.EXPLORATION.value,
            'icon': 'fa-globe',
            'action_type': 'travel',
            'requirement_count': 10,
            'gold_reward': 1.0,
            'xp_reward': 25,
        },
    ]

    # Tutorial Missions (Sequential, one-time)
    # Gold rewards at 1/5 of original values
    tutorial_missions = [
        {
            'code': 'tut_first_train',
            'name': 'First Training',
            'description': 'Complete your first military training session',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.TRAINING.value,
            'icon': 'fa-dumbbell',
            'action_type': 'train',
            'requirement_count': 1,
            'gold_reward': 1.0,
            'xp_reward': 10,
            'tutorial_order': 1,
        },
        {
            'code': 'tut_first_work',
            'name': 'First Job',
            'description': 'Work at a company for the first time',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.WORK.value,
            'icon': 'fa-briefcase',
            'action_type': 'work',
            'requirement_count': 1,
            'gold_reward': 1.0,
            'xp_reward': 10,
            'tutorial_order': 2,
        },
        {
            'code': 'tut_first_fight',
            'name': 'First Battle',
            'description': 'Fight in your first battle',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.COMBAT.value,
            'icon': 'fa-crosshairs',
            'action_type': 'fight',
            'requirement_count': 1,
            'gold_reward': 1.0,
            'xp_reward': 10,
            'tutorial_order': 3,
        },
        {
            'code': 'tut_first_travel',
            'name': 'First Journey',
            'description': 'Travel to a different region',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.EXPLORATION.value,
            'icon': 'fa-plane',
            'action_type': 'travel',
            'requirement_count': 1,
            'gold_reward': 1.0,
            'xp_reward': 10,
            'tutorial_order': 4,
        },
        {
            'code': 'tut_reach_level_5',
            'name': 'Reach Level 5',
            'description': 'Reach experience level 5',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.TRAINING.value,
            'icon': 'fa-star',
            'action_type': 'level_up',
            'requirement_count': 5,
            'gold_reward': 2.0,
            'xp_reward': 0,
            'tutorial_order': 5,
        },
        {
            'code': 'tut_first_company',
            'name': 'Entrepreneur',
            'description': 'Create your first company',
            'mission_type': MissionType.TUTORIAL.value,
            'category': MissionCategory.ECONOMIC.value,
            'icon': 'fa-building',
            'action_type': 'create_company',
            'requirement_count': 1,
            'gold_reward': 4.0,
            'xp_reward': 25,
            'tutorial_order': 6,
        },
    ]

    all_missions = daily_missions + weekly_missions + tutorial_missions

    created_count = 0
    updated_count = 0

    for mission_data in all_missions:
        existing = Mission.query.filter_by(code=mission_data['code']).first()

        if existing:
            # Update existing mission
            for key, value in mission_data.items():
                setattr(existing, key, value)
            updated_count += 1
            print(f"Updated mission: {mission_data['code']}")
        else:
            # Create new mission
            mission = Mission(**mission_data)
            db.session.add(mission)
            created_count += 1
            print(f"Created mission: {mission_data['code']}")

    db.session.commit()
    print(f"\nSeed complete: {created_count} created, {updated_count} updated")
    return created_count, updated_count


def main():
    """Run the seed script."""
    app = create_app()
    with app.app_context():
        seed_missions()


if __name__ == '__main__':
    main()
