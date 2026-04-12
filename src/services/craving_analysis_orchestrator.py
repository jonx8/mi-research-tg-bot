from dataclasses import dataclass
from typing import List

from src.exceptions import InvalidStepError, CravingSessionNotFoundError, ValidationError
from src.services.session_manager import SessionManager


@dataclass
class CravingQuestionData:
    """DTO для вопроса анализа тяги"""
    number: int
    total: int
    text: str


@dataclass
class CravingAnalysisResult:
    """DTO для результатов анализа"""
    user_id: int
    answers: List[str]


class CravingAnalysisOrchestrator:
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager

    @staticmethod
    def get_craving_analysis_questions() -> List[str]:
        """Вопросы для анализа триггеров тяги"""
        return [
            "Что спровоцировало тягу? (ситуация, эмоции, место)",
            "Какие мысли были у вас в момент тяги?",
            "Что вы почувствовали физически?",
            "Какой способ помог справиться с тягой?"
        ]

    def _get_session_or_raise(self, user_id: int):
        session = self._session_manager.get_craving_session(user_id)
        if not session:
            raise CravingSessionNotFoundError(user_id)
        return session

    def start_analysis(self, telegram_id: int) -> None:
        self._session_manager.create_craving_session(telegram_id)

    def get_current_question(self, user_id: int) -> CravingQuestionData:
        """Возвращает текущий вопрос"""
        session = self._get_session_or_raise(user_id)
        questions = self.get_craving_analysis_questions()

        if session.step >= len(questions):
            raise InvalidStepError("Анализ уже завершён")

        return CravingQuestionData(
            number=session.step + 1,
            total=len(questions),
            text=questions[session.step]
        )

    def save_answer(self, user_id: int, answer: str) -> None:
        """Сохраняет ответ и переходит к следующему вопросу"""
        session = self._get_session_or_raise(user_id)
        questions = self.get_craving_analysis_questions()

        if session.step >= len(questions):
            raise InvalidStepError("Анализ уже завершён")

        if not answer.strip():
            raise ValidationError("Пожалуйста, введите ответ")

        session.answers.append(answer.strip())
        session.step += 1

    def is_completed(self, user_id: int) -> bool:
        """Проверяет, завершён ли анализ"""
        session = self._get_session_or_raise(user_id)
        questions = self.get_craving_analysis_questions()
        return session.step >= len(questions)

    def get_result(self, user_id: int) -> CravingAnalysisResult:
        """Возвращает результаты анализа"""
        session = self._get_session_or_raise(user_id)
        questions = self.get_craving_analysis_questions()

        if session.step < len(questions):
            raise InvalidStepError("Анализ ещё не завершён")

        return CravingAnalysisResult(
            user_id=user_id,
            answers=session.answers.copy()
        )

    def finish_analysis(self, user_id: int) -> CravingAnalysisResult:
        """Завершает анализ и очищает сессию"""
        result = self.get_result(user_id)
        self._session_manager.delete_craving_session(user_id)
        # TODO Сохранять результаты в БД
        return result

    def is_analysis_active(self, user_id: int) -> bool:
        """Проверяет, активен ли анализ"""
        return self._session_manager.has_craving_session(user_id)
