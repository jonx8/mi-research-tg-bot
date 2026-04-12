import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from src.exceptions import (
    SessionNotFoundError,
    ValidationError,
    InvalidStepError,
)
from src.models import Participant
from src.questionnaires import (
    get_fagerstrom_questions,
    calculate_fagerstrom_score,
    get_prochaska_questions,
    calculate_prochaska_score
)
from src.services.participant_service import ParticipantService
from src.services.session_manager import SessionManager, RegistrationStep, RegistrationSession


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
    """Оркестратор процесса регистрации"""

    def __init__(
            self,
            session_manager: SessionManager,
            participant_service: ParticipantService
    ):
        self._session_manager = session_manager
        self._participant_service = participant_service

    def _get_session_or_raise(self, telegram_id: int) -> RegistrationSession:
        session = self._session_manager.get_registration_session(telegram_id)
        if not session:
            raise SessionNotFoundError(telegram_id)
        return session

    @staticmethod
    def _ensure_step(session: RegistrationSession, expected_step: RegistrationStep) -> None:
        if session.step != expected_step:
            raise InvalidStepError(
                f"Ожидался шаг '{expected_step.value}', текущий шаг '{session.step.value}'"
            )

    def start_registration(self, telegram_id: int) -> None:
        self._session_manager.create_registration_session(telegram_id)

    def get_current_step(self, telegram_id: int) -> Optional[RegistrationStep]:
        session = self._session_manager.get_registration_session(telegram_id)
        return session.step if session else None

    def is_registration_active(self, telegram_id: int) -> bool:
        return self._session_manager.has_registration_session(telegram_id)

    def set_age(self, telegram_id: int, age: int) -> None:
        session = self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.AGE)

        if not (18 <= age <= 120):
            raise ValidationError("⚠️ Возраст должен быть от 18 до 120 лет")

        session.age = age
        session.step = RegistrationStep.GENDER

    def set_gender(self, telegram_id: int, gender_key: str) -> None:
        session = self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.GENDER)

        if gender_key not in ('gender_male', 'gender_female'):
            raise ValidationError("Некорректное значение пола")

        session.gender = "male" if gender_key == "gender_male" else "female"
        session.step = RegistrationStep.FAGERSTROM

    def start_questionnaire(self, telegram_id: int, questionnaire_type: str) -> None:
        if questionnaire_type not in ('fagerstrom', 'prochaska'):
            raise ValidationError("Тип опросника должен быть 'fagerstrom' или 'prochaska'")

        session = self._get_session_or_raise(telegram_id)

        if questionnaire_type == 'fagerstrom':
            self._ensure_step(session, RegistrationStep.FAGERSTROM)
        elif questionnaire_type == 'prochaska':
            self._ensure_step(session, RegistrationStep.PROCHASKA)

        session.current_questionnaire = questionnaire_type
        session.current_question_index = 0

    def get_current_question(self, telegram_id: int) -> QuestionData:
        session = self._get_session_or_raise(telegram_id)

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

    def save_answer(
            self,
            telegram_id: int,
            questionnaire_type: str,
            question_index: int,
            answer_index: int
    ) -> None:
        session = self._get_session_or_raise(telegram_id)

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
            session.fagerstrom_answers[question['field']] = score
        else:
            session.prochaska_answers[question['field']] = score

        session.current_question_index += 1

    def go_to_previous_question(self, telegram_id: int) -> None:
        session = self._get_session_or_raise(telegram_id)

        if not session.current_questionnaire:
            raise InvalidStepError("Опросник не активен")

        if session.current_question_index <= 0:
            raise ValidationError("Нельзя вернуться назад с первого вопроса")

        session.current_question_index -= 1

    def is_questionnaire_completed(self, telegram_id: int, questionnaire_type: str) -> bool:
        session = self._get_session_or_raise(telegram_id)
        if questionnaire_type == 'fagerstrom':
            return len(get_fagerstrom_questions()) == len(session.fagerstrom_answers)
        elif questionnaire_type == 'prochaska':
            return len(get_prochaska_questions()) == len(session.prochaska_answers)
        else:
            raise NotImplementedError("Неподдерживаемый тип опросника")

    def complete_fagerstrom(self, telegram_id: int) -> QuestionnaireResult:
        session = self._get_session_or_raise(telegram_id)

        if session.current_questionnaire != 'fagerstrom':
            raise InvalidStepError("Опросник Фагерстрёма не активен")

        if session.fagerstrom_score is not None:
            raise InvalidStepError("Опросник Фагерстрёма уже завершён")

        score, level = calculate_fagerstrom_score(session.fagerstrom_answers)
        session.fagerstrom_score = score
        session.fagerstrom_level = level
        session.current_questionnaire = None
        session.current_question_index = 0
        session.step = RegistrationStep.PROCHASKA

        return QuestionnaireResult(score=score, level=level, is_fagerstrom=True)

    def complete_prochaska(self, telegram_id: int) -> QuestionnaireResult:
        session = self._get_session_or_raise(telegram_id)

        if session.current_questionnaire != 'prochaska':
            raise InvalidStepError("Опросник Прохаски не активен")

        if session.prochaska_score is not None:
            raise InvalidStepError("Опросник Прохаски уже завершён")

        score, level = calculate_prochaska_score(session.prochaska_answers)
        session.prochaska_score = score
        session.prochaska_level = level
        session.step = RegistrationStep.COMPLETED
        session.current_questionnaire = None

        return QuestionnaireResult(score=score, level=level, is_fagerstrom=False)

    async def finalize_registration(self, telegram_id: int) -> Participant:
        session = self._get_session_or_raise(telegram_id)
        self._ensure_step(session, RegistrationStep.COMPLETED)

        participant_code = self._participant_service.generate_participant_code(telegram_id)
        group = 'A' if random.random() < 0.5 else 'B'

        participant = Participant(
            participant_code=participant_code,
            telegram_id=telegram_id,
            group_name=group,
            registration_date=datetime.now().isoformat(),
            age=session.age,
            gender=session.gender,
            fagerstrom_score=session.fagerstrom_score,
            fagerstrom_level=session.fagerstrom_level,
            prochaska_score=session.prochaska_score,
            prochaska_level=session.prochaska_level,
            **session.fagerstrom_answers,
            **session.prochaska_answers
        )

        await self._participant_service.save(participant)
        self._session_manager.delete_registration_session(telegram_id)

        print(f"🎉 Новый участник: {participant_code}, Группа: {group}")
        return participant
