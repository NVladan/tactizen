"""
Military Rank Model
Defines military ranks from Recruit to Field Marshal
"""
from app.extensions import db

class MilitaryRank(db.Model):
    """Military rank definitions with progression requirements"""
    __tablename__ = 'military_ranks'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    xp_required = db.Column(db.Integer, nullable=False, default=0)
    damage_bonus = db.Column(db.Integer, nullable=False)  # Percentage bonus

    # Relationship to users
    users = db.relationship('User', back_populates='rank', foreign_keys='User.military_rank_id')

    def __repr__(self):
        return f'<MilitaryRank {self.id}: {self.name} (+{self.damage_bonus}% damage)>'

    @staticmethod
    def get_rank_by_id(rank_id):
        """Get rank by ID"""
        return db.session.get(MilitaryRank, rank_id)

    @staticmethod
    def get_next_rank(current_rank_id):
        """Get the next rank after current rank"""
        if current_rank_id >= 60:
            return None  # Already at max rank
        return db.session.get(MilitaryRank, current_rank_id + 1)

    @staticmethod
    def get_all_ranks():
        """Get all ranks ordered by ID"""
        return db.session.query(MilitaryRank).order_by(MilitaryRank.id).all()
