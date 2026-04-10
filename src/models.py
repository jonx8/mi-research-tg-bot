from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Participant(Base):
    __tablename__ = 'participants'

    participant_code = Column(String, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    group_name = Column(String, nullable=False)
    registration_date = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)

    fagerstrom_score = Column(Integer)
    fagerstrom_level = Column(String)
    prochaska_score = Column(Integer)
    prochaska_level = Column(String)
    fagerstrom_1 = Column(Integer)
    fagerstrom_2 = Column(Integer)
    fagerstrom_3 = Column(Integer)
    fagerstrom_4 = Column(Integer)
    fagerstrom_5 = Column(Integer)
    fagerstrom_6 = Column(Integer)
    prochaska_1 = Column(Integer)
    prochaska_2 = Column(Integer)


class Technique(Base):
    __tablename__ = 'techniques'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.now)
