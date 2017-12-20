#!/usr/bin/env python

#
# copyright Tom Goetz
#

import os, logging, datetime

from sqlalchemy import *
from sqlalchemy.ext.declarative import *
from sqlalchemy.orm import *


logger = logging.getLogger(__name__)
#logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)


class DB():
    def __init__(self, filename, debug=False):
        url = "sqlite:///" + filename
        self.engine = create_engine(url, echo=debug)
        self.session_maker = sessionmaker(bind=self.engine)

    def session(self):
        return self.session_maker()


class DBObject():

    @classmethod
    def timedelta_to_secs(cls, timedelta):
        return (timedelta.days * 3600) + timedelta.seconds

    @classmethod
    def filename_from_pathname(cls, pathname):
        return os.path.basename(pathname)

    @classmethod
    def __filter_columns(cls, values_dict):
        return { key : value for key, value in values_dict.items() if key in cls.__dict__}

    @classmethod
    def _filter_columns(cls, values_dict):
        filtered_cols = cls.__filter_columns(values_dict)
        if len(filtered_cols) != len(values_dict):
            logger.debug("filtered some cols for %s from %s" % (cls.__tablename__, repr(values_dict)))
        if len(filtered_cols) == 0:
            raise ValueError("%s: filtered all cols for %s from %s" %
                (cls.__name__, cls.__tablename__, repr(values_dict)))
        return filtered_cols

    @classmethod
    def matches(cls, values_dict):
        filtered_cols = cls.__filter_columns(values_dict)
        return len(filtered_cols) >= cls.min_row_values

    @classmethod
    def relational_mappings(cls, db, values_dict):
        if len(cls._relational_mappings) == 0:
            return values_dict
        return {
            (cls._relational_mappings[key][0] if key in cls._relational_mappings else key) :
            (cls._relational_mappings[key][1](db, value) if key in cls._relational_mappings else value)
            for key, value in values_dict.items()
        }

    @classmethod
    def _translate_columns(cls, values_dict):
        if len(cls.col_translations) == 0:
            return values_dict
        return {
            key :
            (cls.col_translations[key](value) if key in cls.col_translations else value)
            for key, value in values_dict.items()
        }

    @classmethod
    def _translate_column(cls, col_name, col_value):
        if len(cls.col_translations) == 0:
            return col_value
        return (cls.col_translations[col_name](col_value) if col_name in cls.col_translations else col_value)

    @classmethod
    def _find(cls, session, values_dict):
        logger.debug("%s::_find %s" % (cls.__name__, repr(values_dict)))
        return cls.find_query(session, cls._translate_columns(values_dict))

    @classmethod
    def find(cls, db, values_dict):
        logger.debug("%s::find %s" % (cls.__name__, repr(values_dict)))
        return cls._find(db.session(), values_dict).all()

    @classmethod
    def find_one(cls, db, values_dict):
        logger.debug("%s::find_one %s" % (cls.__name__, repr(values_dict)))
        return cls._find(db.session(), values_dict).one_or_none()

    @classmethod
    def find_id(cls, db, values_dict):
        logger.debug("%s::find_id %s" % (cls.__name__, repr(values_dict)))
        instance = cls.find_one(db, values_dict)
        if instance is not None:
            return instance.id
        return None

    @classmethod
    def find_or_create_id(cls, db, values_dict):
        logger.debug("%s::find_or_create_id %s" % (cls.__name__, repr(values_dict)))
        instance = cls.find_one(db, values_dict)
        if instance is None:
            cls.create(db, values_dict)
            instance = cls.find_one(db, values_dict)
        return instance.id

    @classmethod
    def _create(cls, db, values_dict):
        logger.debug("%s::_create %s" % (cls.__name__, repr(values_dict)))
        non_none_values = 0
        for value in values_dict.values():
            if value is not None:
                non_none_values += 1
        if non_none_values < cls.min_row_values:
            raise ValueError("None row values: %s" % repr(values_dict))
        session = db.session()
        session.add(cls(**cls._filter_columns(cls.relational_mappings(db, values_dict))))
        session.commit()

    @classmethod
    def create(cls, db, values_dict):
        return cls._create(db, cls._translate_columns(values_dict))

    @classmethod
    def find_or_create(cls, db, values_dict):
        instance = cls.find_one(db, values_dict)
        if instance is None:
            cls.create(db, values_dict)
            instance = cls.find_one(db, values_dict)
        return instance

    @classmethod
    def update(cls, db, values_dict):
        logger.debug("%s::_create %s" % (cls.__name__, repr(values_dict)))
        session = db.session()
        found = cls._find(session, values_dict).one_or_none()
        if found:
            translated_dict = cls._translate_columns(values_dict)
            for key, value in translated_dict.items():
                if key in cls.__dict__:
                    found[key] = value
            session.commit()
        return found

    @classmethod
    def create_or_update(cls, db, values_dict):
        logger.debug("%s::_create %s" % (cls.__name__, repr(values_dict)))
        instance = cls.update(db, values_dict)
        if instance is None:
            cls.create(db, values_dict)
            instance = cls.find_one(db, values_dict)
        return instance

    @classmethod
    def row_to_int(cls, row):
        return int(row[0])

    @classmethod
    def rows_to_ints(cls, rows):
        return [cls.row_to_int(row) for row in rows]

    @classmethod
    def row_to_month(cls, row):
        return datetime.date(1900, int(row[0]), 1).strftime("%b")

    @classmethod
    def rows_to_months(cls, rows):
        return [cls.row_to_month(row) for row in rows]

    @classmethod
    def get_years(cls, db):
        return cls.rows_to_ints(db.session().query(extract('year', cls.timestamp)).distinct().all())

    @classmethod
    def get_months(cls, db, year):
          return (db.session().query(extract('month', cls.timestamp))
              .filter(extract('year', cls.timestamp) == str(year)).distinct().all())

    @classmethod
    def get_month_names(cls, db, year):
          return cls.rows_to_months(cls.get_months(db, year))

    @classmethod
    def get_days(cls, db, year):
        return cls.rows_to_ints(db.session().query(func.strftime("%j", cls.timestamp))
            .filter(extract('year', cls.timestamp) == str(year)).distinct().all())

    @classmethod
    def get_col_avg(cls, db, col, start_ts, end_ts):
        return (
            db.session().query(func.avg(col))
                .filter(cls.timestamp >= start_ts)
                .filter(cls.timestamp < end_ts)
                .one()[0]
        )

    @classmethod
    def get_col_min(cls, db, col, start_ts, end_ts):
        return (
            db.session().query(func.min(col))
                .filter(cls.timestamp >= start_ts)
                .filter(cls.timestamp < end_ts)
                .one()[0]
        )

    @classmethod
    def get_col_max(cls, db, col, start_ts, end_ts):
        return (
            db.session().query(func.max(col))
                .filter(cls.timestamp >= start_ts)
                .filter(cls.timestamp < end_ts)
                .one()[0]
        )

    @classmethod
    def get_col_sum(cls, db, col, start_ts, end_ts):
        return (
            db.session().query(func.sum(col))
                .filter(cls.timestamp >= start_ts)
                .filter(cls.timestamp < end_ts)
                .one()[0]
        )

    def __repr__(self):
        classname = self.__class__.__name__
        col_name = cls.find_col.name
        col_value = self.__dict__[col_name]
        return ("<%s(timestamp=%s %s=%s)>" % (classname, col.name, col_value))

