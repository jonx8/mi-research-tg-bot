import hashlib
import secrets

def generate_participant_code(telegram_id: int) -> str:
    """Генерация уникального обезличенного ID"""
    hash_input = f"{telegram_id}{secrets.token_hex(8)}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:10]

def validate_age(age_text: str):
    """Проверка корректности возраста"""
    try:
        age = int(age_text)
        if 18 <= age <= 120:
            return True, age
        return False, 0
    except ValueError:
        return False, 0