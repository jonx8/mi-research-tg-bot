from datetime import datetime, timedelta
from typing import Optional

from src.models import FinalSurvey
from src.repositories.final_repo import FinalSurveyRepository


class FinalSurveyService:
    def __init__(self, repo: FinalSurveyRepository):
        self._repo = repo

    async def create_scheduled(
            self,
            participant_code: str,
            registration_date: datetime,
            interval_minutes: int
    ) -> FinalSurvey:
        """
        Создаёт финальный опрос.

        Args:
            participant_code: код участника
            registration_date: дата регистрации
            interval_minutes: интервал в минутах
        """
        survey = FinalSurvey(
            participant_code=participant_code,
            scheduled_date=registration_date + timedelta(minutes=interval_minutes)
        )
        return await self._repo.save(survey)

    async def get_pending(self, participant_code: str) -> Optional[FinalSurvey]:
        return await self._repo.get_pending(participant_code)

    async def complete(
            self,
            survey: FinalSurvey,
            ppa_30d: bool,
            ppa_7d: bool,
            cigs_per_day: Optional[int],
            quit_attempt_made: bool,
            days_to_first_lapse: Optional[int]
    ) -> FinalSurvey:
        survey.completed_at = datetime.now()
        survey.ppa_30d = ppa_30d
        survey.ppa_7d = ppa_7d
        survey.cigs_per_day = cigs_per_day
        survey.quit_attempt_made = quit_attempt_made
        survey.days_to_first_lapse = days_to_first_lapse
        return await self._repo.update(survey)