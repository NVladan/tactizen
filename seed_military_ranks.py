"""
Seed Military Ranks
Creates all military ranks from Recruit to Field Marshal (60 ranks)
"""
from app import create_app
from app.extensions import db
from app.models.military_rank import MilitaryRank

# Military ranks with XP requirements and damage bonuses
# XP progression: exponential growth starting at 100, with 12% increase per rank
MILITARY_RANKS = [
    # (ID, Name, XP Required, Damage Bonus %)
    (1, 'Recruit', 0, 2),
    (2, 'Apprentice', 100, 4),
    (3, 'Private III', 212, 6),
    (4, 'Private II', 337, 8),
    (5, 'Private I', 477, 10),
    (6, 'Specialist III', 634, 12),
    (7, 'Specialist II', 810, 14),
    (8, 'Specialist I', 1007, 16),
    (9, 'Lance Corporal', 1228, 18),
    (10, 'Corporal', 1475, 20),
    (11, 'Senior Corporal', 1752, 22),
    (12, 'Master Corporal', 2062, 24),
    (13, 'Sergeant III', 2409, 26),
    (14, 'Sergeant II', 2798, 28),
    (15, 'Sergeant I', 3234, 30),
    (16, 'Staff Sergeant III', 3722, 32),
    (17, 'Staff Sergeant II', 4269, 34),
    (18, 'Staff Sergeant I', 4882, 36),
    (19, 'Technical Sergeant', 5568, 38),
    (20, 'Senior Sergeant', 6336, 40),
    (21, 'First Sergeant', 7197, 42),
    (22, 'Master Sergeant III', 8161, 44),
    (23, 'Master Sergeant II', 9241, 46),
    (24, 'Master Sergeant I', 10451, 48),
    (25, 'Sergeant Major', 11806, 50),
    (26, 'Command Sergeant Major', 13323, 52),
    (27, 'Sergeant Major of the Guard', 15023, 54),
    (28, 'Warrant Officer III', 16927, 56),
    (29, 'Warrant Officer II', 19059, 58),
    (30, 'Warrant Officer I', 21447, 60),
    (31, 'Chief Warrant Officer', 24121, 62),
    (32, 'Master Warrant Officer', 27116, 64),
    (33, '2nd Lieutenant', 30471, 66),
    (34, '1st Lieutenant', 34229, 68),
    (35, 'Captain III', 38438, 70),
    (36, 'Captain II', 43152, 72),
    (37, 'Captain I', 48431, 74),
    (38, 'Major III', 54344, 76),
    (39, 'Major II', 60967, 78),
    (40, 'Major I', 68384, 80),
    (41, 'Lieutenant Colonel III', 76692, 82),
    (42, 'Lieutenant Colonel II', 85997, 84),
    (43, 'Lieutenant Colonel I', 96418, 86),
    (44, 'Colonel III', 108090, 88),
    (45, 'Colonel II', 121162, 90),
    (46, 'Colonel I', 135803, 92),
    (47, 'Senior Colonel', 152201, 94),
    (48, 'Brigadier General III', 170567, 96),
    (49, 'Brigadier General II', 191137, 98),
    (50, 'Brigadier General I', 214176, 100),
    (51, 'Major General III', 239979, 102),
    (52, 'Major General II', 268879, 104),
    (53, 'Major General I', 301247, 106),
    (54, 'Lieutenant General III', 337499, 108),
    (55, 'Lieutenant General II', 378101, 110),
    (56, 'Lieutenant General I', 423576, 112),
    (57, 'General III', 474508, 114),
    (58, 'General II', 531551, 116),
    (59, 'General I', 595440, 118),
    (60, 'Field Marshal', 666995, 120),
]


def seed_military_ranks():
    """Seed military ranks into database"""
    app = create_app()

    with app.app_context():
        # Check if ranks already exist
        existing_count = MilitaryRank.query.count()
        if existing_count > 0:
            print(f"Military ranks table already has {existing_count} ranks.")
            user_input = input("Do you want to clear and reseed? (y/n): ")
            if user_input.lower() != 'y':
                print("Aborted.")
                return

            # Clear existing ranks
            MilitaryRank.query.delete()
            db.session.commit()
            print("Cleared existing military ranks.")

        # Insert all ranks
        for rank_id, name, xp_required, damage_bonus in MILITARY_RANKS:
            rank = MilitaryRank(
                id=rank_id,
                name=name,
                xp_required=xp_required,
                damage_bonus=damage_bonus
            )
            db.session.add(rank)

        db.session.commit()
        print(f"Successfully seeded {len(MILITARY_RANKS)} military ranks!")

        # Show first few and last few ranks
        print("\nFirst 5 ranks:")
        for rank in MilitaryRank.query.order_by(MilitaryRank.id).limit(5).all():
            print(f"  {rank.id}. {rank.name} - {rank.xp_required} XP, +{rank.damage_bonus}% damage")

        print("\nLast 5 ranks:")
        for rank in MilitaryRank.query.order_by(MilitaryRank.id.desc()).limit(5).all():
            print(f"  {rank.id}. {rank.name} - {rank.xp_required} XP, +{rank.damage_bonus}% damage")


if __name__ == '__main__':
    seed_military_ranks()
