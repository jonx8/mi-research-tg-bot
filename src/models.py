from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean, Date, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.utils.encryption import get_encryption_service


class Base(DeclarativeBase):
    pass


class Participant(Base):
    """Main participant information."""
    __tablename__ = 'participants'

    participant_code: Mapped[str] = mapped_column(primary_key=True)
    telegram_id_encrypted: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
    group_name: Mapped[str] = mapped_column(nullable=False)
    registration_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
    age: Mapped[int] = mapped_column(nullable=False)
    gender: Mapped[str] = mapped_column(nullable=False)

    # Relationships
    baseline_questionnaire: Mapped[Optional["BaselineQuestionnaire"]] = relationship(back_populates="participant")
    follow_ups: Mapped[List["FollowUp"]] = relationship(back_populates="participant")
    weekly_checkins: Mapped[List["WeeklyCheckIn"]] = relationship(back_populates="participant")
    daily_logs: Mapped[List["DailyLog"]] = relationship(back_populates="participant")
    sos_usages: Mapped[List["SOSUsage"]] = relationship(back_populates="participant")
    craving_analyses: Mapped[List["CravingAnalysis"]] = relationship(back_populates="participant")
    final_survey: Mapped[Optional["FinalSurvey"]] = relationship(back_populates="participant")
    intervention_content_logs: Mapped[List["InterventionContentLog"]] = relationship(back_populates="participant")

    @property
    def telegram_id(self) -> int:
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(
            self.telegram_id_encrypted
        )


class BaselineQuestionnaire(Base):
    """Baseline questionnaire (day 0)."""
    __tablename__ = 'baseline_questionnaires'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        unique=True,
        nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Курительный профиль
    smoking_years: Mapped[int] = mapped_column(Integer, nullable=False)
    cigs_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    quit_attempts_before: Mapped[bool] = mapped_column(Boolean, nullable=False)
    uses_vape: Mapped[bool] = mapped_column(Boolean, nullable=False)
    smoker_in_household: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prior_medical_help: Mapped[str] = mapped_column(String, nullable=False)

    # Тест Фагерстрёма
    fagerstrom_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_level: Mapped[str] = mapped_column(String, nullable=False)
    fagerstrom_1: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_2: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_3: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_4: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_5: Mapped[int] = mapped_column(Integer, nullable=False)
    fagerstrom_6: Mapped[int] = mapped_column(Integer, nullable=False)

    # Опросник Прохаски
    prochaska_score: Mapped[int] = mapped_column(Integer, nullable=False)
    prochaska_level: Mapped[str] = mapped_column(String, nullable=False)
    prochaska_1: Mapped[int] = mapped_column(Integer, nullable=False)
    prochaska_2: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="baseline_questionnaire")


class FollowUp(Base):
    """Intermediate surveys (1 and 3 months)."""
    __tablename__ = 'follow_ups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ppa_7d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cigs_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="follow_ups")


class WeeklyCheckIn(Base):
    """Weekly check-ins (Group B only)."""
    __tablename__ = 'weekly_checkins'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    smoking_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    craving_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="weekly_checkins")


class DailyLog(Base):
    """Daily activity (Group B only)."""
    __tablename__ = 'daily_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)

    morning_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    high_dep_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    evening_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    evening_response: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # ✅ Да / ❌ Трудности / 🆘 Тяга
    evening_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="daily_logs")


class SOSUsage(Base):
    """SOS button usage tracking."""
    __tablename__ = 'sos_usage'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    technique_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey('techniques.id'),
        nullable=True
    )

    # Relationships
    participant: Mapped["Participant"] = relationship(back_populates="sos_usages")
    technique: Mapped[Optional["Technique"]] = relationship(back_populates="sos_usages")


class CravingAnalysis(Base):
    """Craving analysis results."""
    __tablename__ = 'craving_analyses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Responses
    trigger_situation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thoughts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    physical_sensation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coping_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="craving_analyses")


class FinalSurvey(Base):
    """Final survey (6 months)."""
    __tablename__ = 'final_surveys'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        unique=True,
        nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ppa_30d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ppa_7d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cigs_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quit_attempt_made: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    days_to_first_lapse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship
    participant: Mapped["Participant"] = relationship(back_populates="final_survey")


class Technique(Base):
    """Techniques for craving management."""
    __tablename__ = 'techniques'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    sos_usages: Mapped[List["SOSUsage"]] = relationship(back_populates="technique")


class MorningTip(Base):
    """Morning tips."""
    __tablename__ = 'morning_tips'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class InterventionContent(Base):
    """Educational and motivational content for Group B (intervention)."""
    __tablename__ = 'intervention_content'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-6
    week: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-24 (weeks from program start)
    content_type: Mapped[str] = mapped_column(String, nullable=False)  # 'educational', 'motivational'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationship
    logs: Mapped[List["InterventionContentLog"]] = relationship(back_populates="content")


class InterventionContentLog(Base):
    """Log of educational and motivational content delivery."""
    __tablename__ = 'intervention_content_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(
        String,
        ForeignKey('participants.participant_code'),
        nullable=False,
        index=True
    )
    content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('intervention_content.id'),
        nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    participant: Mapped["Participant"] = relationship(back_populates="intervention_content_logs")
    content: Mapped["InterventionContent"] = relationship(back_populates="logs")


class RegistrationSession(Base):
    """Registration session model for database storage."""
    __tablename__ = 'registration_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id_encrypted: Mapped[str] = mapped_column(String, primary_key=True)  # Encrypted telegram_id
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    step: Mapped[str] = mapped_column(String, nullable=False, default='age')

    # Demographics
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Smoking profile
    smoking_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cigs_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quit_attempts_before: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    uses_vape: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    smoker_in_household: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    prior_medical_help: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Questionnaires - answers stored as JSON
    fagerstrom_answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    prochaska_answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    fagerstrom_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fagerstrom_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prochaska_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prochaska_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    last_bot_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_questionnaire: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def telegram_id(self) -> int:
        """Returns the decrypted telegram_id."""
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(self.telegram_id_encrypted)




class CravingAnalysisSession(Base):
    """Craving analysis session model for database storage."""
    __tablename__ = 'craving_analysis_sessions'

    telegram_id_encrypted: Mapped[str] = mapped_column(String, primary_key=True)  # Encrypted telegram_id
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    @property
    def telegram_id(self) -> int:
        """Returns the decrypted telegram_id."""
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(self.telegram_id_encrypted)


class FollowUpSession(Base):
    """Follow-up survey session model for intermediate data storage."""
    __tablename__ = 'follow_up_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id_encrypted: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Encrypted telegram_id
    follow_up_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    ppa_7d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    @property
    def telegram_id(self) -> int:
        """Returns the decrypted telegram_id."""
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(self.telegram_id_encrypted)


class FinalSurveySession(Base):
    """Final survey session model for intermediate data storage."""
    __tablename__ = 'final_survey_sessions'

    survey_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id_encrypted: Mapped[str] = mapped_column(String, unique=True)  # Encrypted telegram_id
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    # Intermediate answers
    ppa_30d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ppa_7d: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cigs_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quit_attempt_made: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    days_to_first_lapse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    @property
    def telegram_id(self) -> int:
        """Returns the decrypted telegram_id."""
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(self.telegram_id_encrypted)


class WeeklyCheckInSession(Base):
    """Weekly check-in session model for intermediate data storage."""
    __tablename__ = 'weekly_checkin_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id_encrypted: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Encrypted telegram_id
    checkin_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    # Intermediate answers
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    craving: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @property
    def telegram_id(self) -> int:
        """Returns the decrypted telegram_id."""
        encryption_service = get_encryption_service()
        return encryption_service.decrypt_to_int(self.telegram_id_encrypted)
