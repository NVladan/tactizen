"""
Seed initial achievements for the achievement system.

This script populates the database with predefined achievements
that users can unlock by reaching specific milestones.
"""

import sys
import io

# Fix Unicode encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app, db
from app.models.achievement import Achievement, AchievementCategory

app = create_app()


def seed_achievements():
    """Create initial achievement definitions."""
    with app.app_context():
        achievements = [
            # Work Achievements
            Achievement(
                code='hard_worker_30',
                name='Hard Worker',
                description='Work for 30 consecutive days',
                category=AchievementCategory.WORK.value,
                icon='fa-briefcase',
                gold_reward=5,
                free_nft_reward=1,  # Award 1 free NFT mint
                requirement_value=30,
                is_active=True
            ),

            # Training Achievements
            Achievement(
                code='training_hard_30',
                name='Training Hard',
                description='Train for 30 consecutive days',
                category=AchievementCategory.TRAINING.value,
                icon='fa-dumbbell',
                gold_reward=5,
                free_nft_reward=1,  # Award 1 free NFT mint
                requirement_value=30,
                is_active=True
            ),

            # Study Achievements
            Achievement(
                code='quick_learner_30',
                name='Quick Learner',
                description='Study for 30 consecutive days',
                category=AchievementCategory.STUDY.value,
                icon='fa-book',
                gold_reward=5,
                free_nft_reward=1,  # Award 1 free NFT mint
                requirement_value=30,
                is_active=True
            ),

            # Economic Achievements
            Achievement(
                code='entrepreneur_5',
                name='Entrepreneur',
                description='Own 5 companies simultaneously',
                category=AchievementCategory.ECONOMIC.value,
                icon='fa-building',
                gold_reward=5,
                free_nft_reward=1,  # Award 1 free NFT mint
                requirement_value=5,
                is_active=True
            ),

            # Exploration Achievements
            Achievement(
                code='explorer_all_countries',
                name='Explorer',
                description='Visit all countries in the world',
                category=AchievementCategory.EXPLORATION.value,
                icon='fa-globe',
                gold_reward=20,
                free_nft_reward=1,
                requirement_value=1,
                is_active=True
            ),

            # Additional Work Achievements
            Achievement(
                code='hard_worker_7',
                name='Dedicated Worker',
                description='Work for 7 consecutive days',
                category=AchievementCategory.WORK.value,
                icon='fa-briefcase',
                gold_reward=5,
                requirement_value=7,
                is_active=True
            ),

            Achievement(
                code='hard_worker_100',
                name='Work Legend',
                description='Work for 100 consecutive days',
                category=AchievementCategory.WORK.value,
                icon='fa-crown',
                gold_reward=5,
                free_nft_reward=3,  # Award 3 free NFT mints
                requirement_value=100,
                is_active=True
            ),

            # Additional Training Achievements
            Achievement(
                code='training_hard_7',
                name='Fitness Enthusiast',
                description='Train for 7 consecutive days',
                category=AchievementCategory.TRAINING.value,
                icon='fa-dumbbell',
                gold_reward=5,
                requirement_value=7,
                is_active=True
            ),

            Achievement(
                code='training_hard_100',
                name='Training Master',
                description='Train for 100 consecutive days',
                category=AchievementCategory.TRAINING.value,
                icon='fa-trophy',
                gold_reward=5,
                free_nft_reward=3,  # Award 3 free NFT mints
                requirement_value=100,
                is_active=True
            ),

            # Additional Study Achievements
            Achievement(
                code='quick_learner_7',
                name='Student',
                description='Study for 7 consecutive days',
                category=AchievementCategory.STUDY.value,
                icon='fa-book',
                gold_reward=5,
                requirement_value=7,
                is_active=True
            ),

            Achievement(
                code='quick_learner_100',
                name='Scholar',
                description='Study for 100 consecutive days',
                category=AchievementCategory.STUDY.value,
                icon='fa-graduation-cap',
                gold_reward=5,
                free_nft_reward=3,  # Award 3 free NFT mints
                requirement_value=100,
                is_active=True
            ),

            # Additional Economic Achievements
            Achievement(
                code='entrepreneur_1',
                name='Business Owner',
                description='Own your first company',
                category=AchievementCategory.ECONOMIC.value,
                icon='fa-store',
                gold_reward=5,
                requirement_value=1,
                is_active=True
            ),

            Achievement(
                code='entrepreneur_10',
                name='Business Tycoon',
                description='Own 10 companies simultaneously',
                category=AchievementCategory.ECONOMIC.value,
                icon='fa-city',
                gold_reward=5,
                free_nft_reward=2,  # Award 2 free NFT mints
                requirement_value=10,
                is_active=True
            ),

            # Recruiter Achievements
            Achievement(
                code='recruiter_10',
                name='Recruiter',
                description='Refer 10 players who reach level 10',
                category=AchievementCategory.SOCIAL.value,
                icon='fa-user-plus',
                gold_reward=25,
                free_nft_reward=1,  # Award 1 free NFT mint
                requirement_value=10,
                is_active=True
            ),

            Achievement(
                code='recruiter_100',
                name='Master Recruiter',
                description='Refer 100 players who reach level 10',
                category=AchievementCategory.SOCIAL.value,
                icon='fa-users-cog',
                gold_reward=100,
                free_nft_reward=2,  # Award 2 free NFT mints
                requirement_value=100,
                is_active=True
            ),

            Achievement(
                code='recruiter_1000',
                name='Legendary Recruiter',
                description='Refer 1000 players who reach level 10',
                category=AchievementCategory.SOCIAL.value,
                icon='fa-crown',
                gold_reward=500,
                free_nft_reward=3,  # Award 3 free NFT mints
                requirement_value=1000,
                is_active=True
            ),

            # Social Achievements
            Achievement(
                code='social_butterfly_10',
                name='Social Butterfly',
                description='Have 10 friends',
                category=AchievementCategory.SOCIAL.value,
                icon='fa-users',
                gold_reward=5,
                requirement_value=10,
                is_active=True
            ),

            Achievement(
                code='social_butterfly_50',
                name='Popular',
                description='Have 50 friends',
                category=AchievementCategory.SOCIAL.value,
                icon='fa-heart',
                gold_reward=5,
                requirement_value=50,
                is_active=True
            ),

            # Combat Achievements - Battle Hero
            Achievement(
                code='battle_hero_10',
                name='Rising Warrior',
                description='Earn 10 Battle Hero medals',
                category=AchievementCategory.COMBAT.value,
                icon='fa-medal',
                gold_reward=10,
                free_nft_reward=1,
                requirement_value=10,
                is_active=True
            ),

            Achievement(
                code='battle_hero_100',
                name='War Legend',
                description='Earn 100 Battle Hero medals',
                category=AchievementCategory.COMBAT.value,
                icon='fa-shield-halved',
                gold_reward=50,
                free_nft_reward=3,
                requirement_value=100,
                is_active=True
            ),

            # Combat Achievement - Freedom Fighter
            Achievement(
                code='freedom_fighter',
                name='Freedom Fighter',
                description='Start a resistance war and win it to liberate your homeland',
                category=AchievementCategory.COMBAT.value,
                icon='fa-fist-raised',
                gold_reward=10,
                free_nft_reward=0,
                requirement_value=1,
                is_active=True
            ),

            # Political Achievements
            Achievement(
                code='elected_president',
                name='Mr. President',
                description='Get elected as President of a country',
                category=AchievementCategory.POLITICAL.value,
                icon='fa-landmark',
                gold_reward=5,
                free_nft_reward=0,
                requirement_value=1,
                is_active=True
            ),

            Achievement(
                code='elected_congress',
                name='Congressman',
                description='Get elected as a Congress member',
                category=AchievementCategory.POLITICAL.value,
                icon='fa-university',
                gold_reward=5,
                free_nft_reward=0,
                requirement_value=1,
                is_active=True
            ),

            # Media Achievements - Newspaper Subscribers
            Achievement(
                code='rising_publisher',
                name='Rising Publisher',
                description='Reach 100 subscribers on your newspaper',
                category=AchievementCategory.MEDIA.value,
                icon='fa-newspaper',
                gold_reward=5,
                free_nft_reward=0,
                requirement_value=100,
                is_active=True
            ),

            Achievement(
                code='popular_publisher',
                name='Popular Publisher',
                description='Reach 1000 subscribers on your newspaper',
                category=AchievementCategory.MEDIA.value,
                icon='fa-star',
                gold_reward=15,
                free_nft_reward=1,
                requirement_value=1000,
                is_active=True
            ),
        ]

        print("Starting achievement seeding...")

        for achievement in achievements:
            existing = db.session.query(Achievement).filter_by(code=achievement.code).first()

            if existing:
                print(f"  ⚠ Achievement '{achievement.code}' already exists, skipping...")
            else:
                db.session.add(achievement)
                print(f"  ✓ Created achievement: {achievement.name} ({achievement.code})")

        db.session.commit()

        total_count = db.session.query(Achievement).count()
        print(f"\n✓ Seeding complete! Total achievements in database: {total_count}")


if __name__ == '__main__':
    seed_achievements()
