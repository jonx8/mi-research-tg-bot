from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Participant(Base):
    """Основная информация об участнике"""
    __tablename__ = 'participants'

    participant_code = Column(String, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    group_name = Column(String, nullable=False)
    registration_date = Column(DateTime, nullable=False, default=datetime.now)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)


class BaselineQuestionnaire(Base):
    """Базовый опросник дня 0"""
    __tablename__ = 'baseline_questionnaires'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), unique=True, nullable=False)
    completed_at = Column(DateTime, nullable=False)

    # Курительный профиль
    smoking_years = Column(Integer, nullable=False)
    cigs_per_day = Column(Integer, nullable=False)
    quit_attempts_before = Column(Boolean, nullable=False)
    uses_vape = Column(Boolean, nullable=False)
    smoker_in_household = Column(Boolean, nullable=False)
    prior_medical_help = Column(String, nullable=False)

    # Тест Фагерстрёма
    fagerstrom_score = Column(Integer, nullable=False)
    fagerstrom_level = Column(String, nullable=False)
    fagerstrom_1 = Column(Integer, nullable=False)
    fagerstrom_2 = Column(Integer, nullable=False)
    fagerstrom_3 = Column(Integer, nullable=False)
    fagerstrom_4 = Column(Integer, nullable=False)
    fagerstrom_5 = Column(Integer, nullable=False)
    fagerstrom_6 = Column(Integer, nullable=False)

    # Опросник Прохаски
    prochaska_score = Column(Integer, nullable=False)
    prochaska_level = Column(String, nullable=False)
    prochaska_1 = Column(Integer, nullable=False)
    prochaska_2 = Column(Integer, nullable=False)


class FollowUp(Base):
    """Промежуточные опросы (1 и 3 месяца)"""
    __tablename__ = 'follow_ups'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    ppa_7d = Column(Boolean, nullable=True)
    cigs_per_day = Column(Integer, nullable=True)


class WeeklyCheckIn(Base):
    """Еженедельные чек-ины (только группа Б)"""
    __tablename__ = 'weekly_checkins'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), nullable=False)
    week_number = Column(Integer, nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    smoking_status = Column(String, nullable=True)
    craving_level = Column(Integer, nullable=True)
    mood = Column(String, nullable=True)


class DailyLog(Base):
    """Ежедневная активность (только группа Б)"""
    __tablename__ = 'daily_logs'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), nullable=False)
    log_date = Column(Date, nullable=False)

    morning_sent_at = Column(DateTime, nullable=True)

    evening_sent_at = Column(DateTime, nullable=True)
    evening_response = Column(String, nullable=True)  # ✅ Да / ❌ Трудности / 🆘 Тяга
    evening_response_at = Column(DateTime, nullable=True)


class SOSUsage(Base):
    """Использование кнопки SOS"""
    __tablename__ = 'sos_usage'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), nullable=False)
    triggered_at = Column(DateTime, nullable=False)

    technique_id = Column(String, ForeignKey('techniques.id'), nullable=True)


class CravingAnalysis(Base):
    """Результаты анализа тяги"""
    __tablename__ = 'craving_analyses'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), nullable=False)
    sos_usage_id = Column(Integer, ForeignKey('sos_usage.id'), nullable=True)
    completed_at = Column(DateTime, nullable=False)

    trigger_situation = Column(Text, nullable=True)
    thoughts = Column(Text, nullable=True)
    physical_sensation = Column(Text, nullable=True)
    coping_strategy = Column(Text, nullable=True)


class FinalSurvey(Base):
    """Финальный опрос (6 месяцев)"""
    __tablename__ = 'final_surveys'

    id = Column(Integer, primary_key=True)
    participant_code = Column(String, ForeignKey('participants.participant_code'), unique=True, nullable=False)
    scheduled_date = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    ppa_30d = Column(Boolean, nullable=True)
    ppa_7d = Column(Boolean, nullable=True)
    cigs_per_day = Column(Integer, nullable=True)
    quit_attempt_made = Column(Boolean, nullable=True)
    days_to_first_lapse = Column(Integer, nullable=True)


class Technique(Base):
    """Техники для борьбы с тягой"""
    __tablename__ = 'techniques'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.now)
