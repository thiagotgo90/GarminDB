#!/usr/bin/env python

#
# copyright Tom Goetz
#

from DB import *


class GarminDB(DB):
    Base = declarative_base()
    db_name = 'garmin.db'

    def __init__(self, db_path, debug=False):
        DB.__init__(self, db_path + "/" + GarminDB.db_name, debug)
        GarminDB.Base.metadata.create_all(self.engine)


class FileType(GarminDB.Base, DBObject):
    __tablename__ = 'file_types'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

    _relational_mappings = {}
    col_translations = {}
    min_row_values = 1

    @classmethod
    def find_query(cls, session, values_dict):
        return  session.query(cls).filter(cls.name == values_dict['name'])

    @classmethod
    def get_id(cls, db, name):
        return cls.find_or_create_id(db, {'name' : name})


class File(GarminDB.Base, DBObject):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    type_id = Column(Integer)

    _relational_mappings = {
        'type' : ('type_id', FileType.get_id)
    }
    col_translations = {
        'name' : DBObject.filename_from_pathname
    }
    min_row_values = 1

    @classmethod
    def find_query(cls, session, values_dict):
        logger.debug("%s::find_query %s" % (cls.__name__, repr(values_dict)))
        return  session.query(cls).filter(cls.name == values_dict['name'])
