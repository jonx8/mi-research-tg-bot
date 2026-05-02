import logging
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

from src.config import Config
from src.exceptions import (
    SessionNotFoundError,
    ValidationError,
    InvalidStepError,
)
from src.models import Participant, BaselineQuestionnaire, RegistrationSession as RegistrationSessionDB
from src.questionnaires import (
    get_fagerstrom_questions,
    calculate_fagerstrom_score,
    get_prochaska_questions,
    calculate_prochaska_score
)
from src.services.baseline_questionnaire_service import BaselineQuestionnaireService
from src.services.final_service import FinalSurveyService
from src.services.follow_up_service import FollowUpService
from src.services.participant_service import ParticipantService
from src.services.session_manager import SessionManager
from src.services.weekly_check_in_service import WeeklyCheckInService

logger = logging.getLogger(__name__)


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
class QuestionData:
    """DTO для данных вопроса"""
    number: int
    total: int
    text: str
    options: List[str]
    field_name: str
    can_go_back: bool
    callback_prefix: str


@dataclass
class QuestionnaireResult:
    """DTO для результатов опросника"""
    score: int
    level: str
    is_fagerstrom: bool


class RegistrationOrchestrator:
    """Оркестратор процесса регистрации — работает напрямую с ORM моделью"""

    def __init__(
            self,
            session_manager: SessionManager,
            participant_service: ParticipantService,
            baseline_service: BaselineQuestionnaireService,
            follow_up_service: FollowUpService,
            weekly_check_in_service: WeeklyCheckInService,
            final_survey_service: FinalSurveyService,
            config: Config
    ):
        self._session_manager = session_manager
        self._baseline_service = baseline_service
        self._participant_service = participant_service
        self._follow_up_service = follow_up_service
        self._weekly_check_in_service = weekly_check_in_service
        self._final_survey_service = final_survey_service
        self._config = config

    async def _get_session_or_raise(self, telegram_id: int) -> RegistrationSessionDB:
        """Получает сессию из БД или выбрасывает исключение"""
        session = await self._session_manager.get_registration_session(telegram_id)
        if not session:
            raise SessionNotFoundError(telegram_id)
        return session

    async def _save_session(self, session_obj: RegistrationSessionDB) -> None:
        """Сохраняет изменения сессии в БД"""
        await self._session_manager.update_registration_session(session_obj)

    @staticmethod
    def _ensure_step(session: RegistrationSessionDB, expected_step: RegistrationStep) -> None:
        """Проверяет, что сессия находится на ожидаемом шаге"""
        current_step_str = session.step if isinstance(session.step, str) else session.step.value
        if current_step_str != expected_step.value:
            raise InvalidStepError(
                f"Ожидался шаг '{expected_step.value}', текущий шаг '{current_step_str}'"
            )

    async def start_registration(self, telegram_id: int) -> None:
        """Начинает новую регистрацию"""
        if await self._session_manager.has_registration_session(telegram_id):
            raise ValidationError("Регистрация уже активна")

        await self._session_manager.create_registration_session(telegram_id)

    async def get_current_step(self, telegram_id: int) -> Optional[RegistrationStep]:
        """Возвращает текущий шаг регистрации"""
        session = await self._session_manager.get_registration_session(telegram_id)
        if not session:
            return None

        step_value = session.step if isinstance(session.step, str) else session.step.value
        return RegistrationStep(step_value)

    async def is_registration_active(self, telegram_id: int) -> bool:
        """Проверяет, активна ли регистрация"""
        return await self._session_manager.has_registration_session(telegram_id)

    async def set_age(self, telegram_id: int, age: int) -> None:
        """Устанавливает возраст"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.AGE)

        if not (18 <= age <= 120):
            raise ValidationError("⚠️ Возраст должен быть от 18 до 120 лет")

        session.age = age
        session.step = RegistrationStep.GENDER.value
        await self._save_session(session)

    async def set_gender(self, telegram_id: int, gender_key: str) -> None:
        """Устанавливает пол"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.GENDER)

        if gender_key not in ('gender_male', 'gender_female'):
            raise ValidationError("Некорректное значение пола")

        session.gender = "male" if gender_key == "gender_male" else "female"
        session.step = RegistrationStep.SMOKING_YEARS.value
        await self._save_session(session)

    async def set_smoking_years(self, telegram_id: int, years: int) -> None:
        """Устанавливает стаж курения"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.SMOKING_YEARS)

        if not (0 <= years <= 120):
            raise ValidationError(f"⚠️ Количество лет курения должно быть от 0 до 120")

        session.smoking_years = years
        session.step = RegistrationStep.CIGS_PER_DAY.value
        await self._save_session(session)

    async def set_cigs_per_day(self, telegram_id: int, cigs: int) -> None:
        """Устанавливает количество сигарет в день"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.CIGS_PER_DAY)

        if not (0 <= cigs <= 100):
            raise ValidationError("⚠️ Количество сигарет должно быть от 0 до 100")

        session.cigs_per_day = cigs
        session.step = RegistrationStep.QUIT_ATTEMPTS.value
        await self._save_session(session)

    async def set_quit_attempts(self, telegram_id: int, has_attempts: bool) -> None:
        """Устанавливает информацию о попытках бросить"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.QUIT_ATTEMPTS)

        session.quit_attempts_before = has_attempts
        session.step = RegistrationStep.VAPE_USAGE.value
        await self._save_session(session)

    async def set_uses_vape(self, telegram_id: int, uses_vape: bool) -> None:
        """Устанавливает информацию об использовании вейпа"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.VAPE_USAGE)

        session.uses_vape = uses_vape
        session.step = RegistrationStep.SMOKER_HOUSEHOLD.value
        await self._save_session(session)

    async def set_smoker_in_household(self, telegram_id: int, has_smoker: bool) -> None:
        """Устанавливает информацию о курящих в семье"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.SMOKER_HOUSEHOLD)

        session.smoker_in_household = has_smoker
        session.step = RegistrationStep.MEDICAL_HELP.value
        await self._save_session(session)

    async def set_prior_medical_help(self, telegram_id: int, answer: str) -> None:
        """Устанавливает информацию о медицинской помощи"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.MEDICAL_HELP)

        session.prior_medical_help = answer
        session.step = RegistrationStep.FAGERSTROM.value
        await self._save_session(session)

    async def start_questionnaire(self, telegram_id: int, questionnaire_type: str) -> None:
        """Начинает опросник (Фагерстрём или Прохаска)"""
        if questionnaire_type not in ('fagerstrom', 'prochaska'):
            raise ValidationError("Тип опросника должен быть 'fagerstrom' или 'prochaska'")

        session = await self._get_session_or_raise(telegram_id)

        if questionnaire_type == 'fagerstrom':
            self._ensure_step(session, RegistrationStep.FAGERSTROM)
        else:
            self._ensure_step(session, RegistrationStep.PROCHASKA)

        session.current_questionnaire = questionnaire_type
        session.current_question_index = 0
        await self._save_session(session)

    async def get_current_question(self, telegram_id: int) -> QuestionData:
        """Возвращает текущий вопрос опросника"""
        session = await self._get_session_or_raise(telegram_id)

        if not session.current_questionnaire:
            raise InvalidStepError("Опросник не активен")

        questions = (
            get_fagerstrom_questions()
            if session.current_questionnaire == 'fagerstrom'
            else get_prochaska_questions()
        )

        idx = session.current_question_index

        if idx >= len(questions):
            raise InvalidStepError("Опросник уже завершён")

        q = questions[idx]
        return QuestionData(
            number=q['number'],
            total=len(questions),
            text=q['question'],
            options=q['options'],
            field_name=q['field'],
            can_go_back=(idx > 0),
            callback_prefix=session.current_questionnaire
        )

    async def save_answer(
            self,
            telegram_id: int,
            questionnaire_type: str,
            question_index: int,
            answer_index: int
    ) -> None:
        """Сохраняет ответ на вопрос опросника"""
        session = await self._get_session_or_raise(telegram_id)

        if session.current_questionnaire != questionnaire_type:
            raise InvalidStepError(
                f"Активен опросник '{session.current_questionnaire}', получен ответ для '{questionnaire_type}'"
            )

        questions = (
            get_fagerstrom_questions()
            if questionnaire_type == 'fagerstrom'
            else get_prochaska_questions()
        )

        if question_index >= len(questions):
            raise InvalidStepError(f"Вопрос {question_index} не существует")

        question = questions[question_index]

        if answer_index >= len(question['options']):
            raise InvalidStepError(f"Ответ {answer_index} не существует")

        score = question['scores'][answer_index]

        if questionnaire_type == 'fagerstrom':
            if session.fagerstrom_answers is None:
                session.fagerstrom_answers = {}
            session.fagerstrom_answers[question['field']] = score
        else:
            if session.prochaska_answers is None:
                session.prochaska_answers = {}
            session.prochaska_answers[question['field']] = score

        session.current_question_index += 1
        await self._save_session(session)

    async def go_to_previous_question(self, telegram_id: int) -> None:
        """Возвращает к предыдущему вопросу"""
        session = await self._get_session_or_raise(telegram_id)

        if not session.current_questionnaire:
            raise InvalidStepError("Опросник не активен")

        if session.current_question_index <= 0:
            raise ValidationError("Нельзя вернуться назад с первого вопроса")

        session.current_question_index -= 1
        await self._save_session(session)

    async def is_questionnaire_completed(self, telegram_id: int, questionnaire_type: str) -> bool:
        """Проверяет, завершён ли опросник"""
        session = await self._get_session_or_raise(telegram_id)

        if questionnaire_type == 'fagerstrom':
            total_questions = len(get_fagerstrom_questions())
            answers_count = len(session.fagerstrom_answers or {})
            return total_questions == answers_count
        else:
            total_questions = len(get_prochaska_questions())
            answers_count = len(session.prochaska_answers or {})
            return total_questions == answers_count

    async def complete_fagerstrom(self, telegram_id: int) -> QuestionnaireResult:
        """Завершает опросник Фагерстрёма и рассчитывает результат"""
        session = await self._get_session_or_raise(telegram_id)

        if session.current_questionnaire != 'fagerstrom':
            raise InvalidStepError("Опросник Фагерстрёма не активен")

        if session.fagerstrom_score is not None:
            raise InvalidStepError("Опросник Фагерстрёма уже завершён")

        score, level = calculate_fagerstrom_score(session.fagerstrom_answers or {})
        session.fagerstrom_score = score
        session.fagerstrom_level = level
        session.current_questionnaire = None
        session.current_question_index = 0
        session.step = RegistrationStep.PROCHASKA.value

        await self._save_session(session)

        return QuestionnaireResult(score=score, level=level, is_fagerstrom=True)

    async def complete_prochaska(self, telegram_id: int) -> QuestionnaireResult:
        """Завершает опросник Прохаски и рассчитывает результат"""
        session = await self._get_session_or_raise(telegram_id)

        if session.current_questionnaire != 'prochaska':
            raise InvalidStepError("Опросник Прохаски не активен")

        if session.prochaska_score is not None:
            raise InvalidStepError("Опросник Прохаски уже завершён")

        score, level = calculate_prochaska_score(session.prochaska_answers or {})
        session.prochaska_score = score
        session.prochaska_level = level
        session.step = RegistrationStep.COMPLETED.value
        session.current_questionnaire = None

        await self._save_session(session)

        return QuestionnaireResult(score=score, level=level, is_fagerstrom=False)

    async def _schedule_all_surveys(self, participant: Participant) -> None:
        """Планирует все опросы для участника"""
        await self._follow_up_service.create_scheduled(
            participant.participant_code,
            participant.registration_date,
            self._config.FOLLOW_UP_INTERVALS
        )

        if participant.group_name == 'B':
            await self._weekly_check_in_service.create_scheduled(
                participant.participant_code,
                participant.registration_date,
                self._config.WEEKLY_CHECKIN_INTERVAL,
                24
            )

        await self._final_survey_service.create_scheduled(
            participant.participant_code,
            participant.registration_date,
            self._config.FINAL_SURVEY_INTERVAL
        )

    async def finalize_registration(self, telegram_id: int) -> Participant:
        """Завершает регистрацию, создаёт участника и сохраняет все данные"""
        session = await self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.COMPLETED)

        if await self._participant_service.exists(telegram_id):
            raise ValidationError("Пользователь уже зарегистрирован")

        participant_code = self._participant_service.generate_participant_code(telegram_id)
        group = 'A' if random.random() < 0.5 else 'B'
        registration_date = datetime.now()

        participant = Participant(
            participant_code=participant_code,
            telegram_id=telegram_id,
            group_name=group,
            registration_date=registration_date,
            age=session.age,
            gender=session.gender
        )
        await self._participant_service.save(participant)

        baseline = BaselineQuestionnaire(
            participant_code=participant_code,
            completed_at=registration_date,
            smoking_years=session.smoking_years,
            cigs_per_day=session.cigs_per_day,
            quit_attempts_before=session.quit_attempts_before,
            uses_vape=session.uses_vape,
            smoker_in_household=session.smoker_in_household,
            prior_medical_help=session.prior_medical_help,
            fagerstrom_score=session.fagerstrom_score,
            fagerstrom_level=session.fagerstrom_level,
            prochaska_score=session.prochaska_score,
            prochaska_level=session.prochaska_level,
            **(session.fagerstrom_answers or {}),
            **(session.prochaska_answers or {})
        )
        await self._baseline_service.save(baseline)

        await self._schedule_all_surveys(participant)
        await self._session_manager.delete_registration_session(telegram_id)

        logger.info(f"Новый участник: {participant_code}, Группа: {group}")

        return participant
