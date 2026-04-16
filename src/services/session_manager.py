from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RegistrationStep(Enum):
    AGE = "age"
    GENDER = "gender"
    SMOKING_YEARS = "smoking_years"
    CIGS_PER_DAY = "cigs_per_day"
    QUIT_ATTEMPTS = "quit_attempts"
    VAPE_USAGE = "vape_usage"
    SMOKER_HOUSEHOLD = "smoker_household"
    MEDICAL_HELP = "medical_help"
    FAGERSTROM = "fagerstrom"
    PROCHASKA = "prochaska"
    COMPLETED = "completed"


@dataclass
class RegistrationSession:
    """Сессия регистрации участника"""
    telegram_id: int
    created_at: datetime = field(default_factory=datetime.now)
    step: RegistrationStep = RegistrationStep.AGE

    # Демография
    age: Optional[int] = None
    gender: Optional[str] = None

    # Курительный профиль
    smoking_years: Optional[int] = None
    cigs_per_day: Optional[int] = None
    quit_attempts_before: Optional[bool] = None
    uses_vape: Optional[bool] = None
    smoker_in_household: Optional[bool] = None
    prior_medical_help: Optional[str] = None

    # Опросники
    fagerstrom_answers: Dict[str, int] = field(default_factory=dict)
    prochaska_answers: Dict[str, int] = field(default_factory=dict)

    fagerstrom_score: Optional[int] = None
    fagerstrom_level: Optional[str] = None
    prochaska_score: Optional[int] = None
    prochaska_level: Optional[str] = None

    current_questionnaire: Optional[str] = None
    current_question_index: int = 0

@dataclass
class CravingAnalysisSession:
    """Сессия анализа тяги"""
    telegram_id: int
    created_at: datetime = field(default_factory=datetime.now)
    step: int = 0
    answers: List[str] = field(default_factory=list)


class SessionManager:
    """Сервис для управления пользовательскими сессиями"""

    def __init__(self):
        self._registration_sessions: Dict[int, RegistrationSession] = {}
        self._craving_sessions: Dict[int, CravingAnalysisSession] = {}

    def create_registration_session(self, telegram_id: int) -> RegistrationSession:
        """Создает новую сессию регистрации"""
        session = RegistrationSession(telegram_id=telegram_id)
        self._registration_sessions[telegram_id] = session
        return session

    def get_registration_session(self, telegram_id: int) -> Optional[RegistrationSession]:
        """Получает активную сессию регистрации"""
        return self._registration_sessions.get(telegram_id)

    def has_registration_session(self, telegram_id: int) -> bool:
        """Проверяет наличие активной сессии"""
        return telegram_id in self._registration_sessions

    def update_registration_session(self, telegram_id: int, **kwargs) -> Optional[RegistrationSession]:
        """Обновляет данные сессии"""
        session = self.get_registration_session(telegram_id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
        return session

    def delete_registration_session(self, telegram_id: int) -> None:
        """Удаляет сессию после завершения регистрации"""
        self._registration_sessions.pop(telegram_id, None)

    def create_craving_session(self, telegram_id: int) -> CravingAnalysisSession:
        """Создает новую сессию анализа тяги"""
        session = CravingAnalysisSession(telegram_id=telegram_id)
        self._craving_sessions[telegram_id] = session
        return session

    def get_craving_session(self, telegram_id: int) -> Optional[CravingAnalysisSession]:
        """Получает активную сессию анализа тяги"""
        return self._craving_sessions.get(telegram_id)

    def has_craving_session(self, telegram_id: int) -> bool:
        """Проверяет наличие активной сессии анализа"""
        return telegram_id in self._craving_sessions

    def delete_craving_session(self, telegram_id: int) -> None:
        """Удаляет сессию анализа"""
        self._craving_sessions.pop(telegram_id, None)
