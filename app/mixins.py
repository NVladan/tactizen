"""Database mixins for common model functionality."""

from datetime import datetime
from sqlalchemy import Column, Boolean, DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Query


class SoftDeleteMixin:
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False, index=True)

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True, index=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        return self

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        return self

    @property
    def is_active(self):
        return not self.is_deleted

    @classmethod
    def get_active_query(cls):
        from app.extensions import db
        return db.session.query(cls).filter_by(is_deleted=False)

    @classmethod
    def get_deleted_query(cls):
        from app.extensions import db
        return db.session.query(cls).filter_by(is_deleted=True)

    def __repr__(self):
        base_repr = super().__repr__()
        if self.is_deleted:
            return base_repr.replace('>', ' [DELETED]>')
        return base_repr


class SoftDeleteQuery(Query):
    """Automatically filters out soft-deleted records by default."""

    def __new__(cls, *args, **kwargs):
        if args and hasattr(args[0], '__mapper__'):
            if hasattr(args[0].__mapper__.class_, 'is_deleted'):
                return Query.__new__(cls)
        return Query.__new__(Query)

    def __init__(self, *args, **kwargs):
        super(SoftDeleteQuery, self).__init__(*args, **kwargs)
        self._with_deleted = False
        self._only_deleted = False

    def _filter_by_deleted(self):
        if hasattr(self, '_with_deleted') and self._with_deleted:
            return self

        if hasattr(self, '_only_deleted') and self._only_deleted:
            return self.filter_by(is_deleted=True)

        return self.filter_by(is_deleted=False)

    def with_deleted(self):
        self._with_deleted = True
        return self

    def only_deleted(self):
        self._only_deleted = True
        return self

    def all(self):
        return self._filter_by_deleted().all()

    def first(self):
        return self._filter_by_deleted().first()

    def one(self):
        return self._filter_by_deleted().one()

    def one_or_none(self):
        return self._filter_by_deleted().one_or_none()

    def count(self):
        return self._filter_by_deleted().count()
