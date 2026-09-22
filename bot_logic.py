from __future__ import annotations

import re

DISCLAIMER = (
    "Помните, что эти советы могут вам помочь и очень важно не предпринимать "
    "непредсказуемые решения, в случае ухудшения своего состояния незамедлительно "
    "обратитесь к специалисту"
)

CRISIS_ANALYSIS = (
    "Сейчас в вашем сообщении видны признаки возможного острого кризиса. "
    "Я не могу безопасно помогать в вопросах, где есть риск причинения вреда себе или другим. "
    "Пожалуйста, немедленно обратитесь в местные экстренные службы/на горячую кризисную линию "
    "и свяжитесь с близким человеком, которому вы доверяете."
)

MAX_INPUT_CHARS = 2000

_CRISIS_PATTERNS = [
    r"\bсуицид\w*",
    r"\bпоконч(ить|у)\s+с\s+собой\b",
    r"\bне\s+хочу\s+жить\b",
    r"\bсамоповрежд\w*",
    r"\bубить\s+себя\b",
    r"\bkill\s+myself\b",
    r"\bsuicid\w*",
    r"\bself\s*-?\s*harm\b",
    r"\bhurt\s+myself\b",
    r"\bубить\s+его\b",
    r"\bубить\s+её\b",
    r"\bубить\s+их\b",
    r"\bнасили\w*",
    r"\bkill\s+him\b",
    r"\bkill\s+her\b",
    r"\bkill\s+them\b",
]

SYSTEM_PROMPT = (
    "Ты аккуратный и эмпатичный помощник поддержки (не врач, не психотерапевт и не кризисный консультант). "
    "Не ставь диагнозы и не утверждай медицинские факты как установленные. "
    "Дай краткую характеристику эмоционального состояния, ответь по сути на вопросы пользователя и предложи "
    "осторожные, практические и безопасные шаги самопомощи. "
    "Если есть признаки немедленной угрозы самоубийства, самоповреждения или насилия, "
    "не давай потенциально опасных инструкций: мягко порекомендуй срочно обратиться в местные экстренные службы "
    "или кризисную линию и к близкому человеку. "
    "Не обещай конфиденциальность сверх технических возможностей сервиса. "
    "Ответ должен быть только содержимым блока анализа, без заголовков шаблона."
)


def sanitize_user_input(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    text = text.replace("\x00", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def has_crisis_signals(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _CRISIS_PATTERNS)


def build_template_response(user_request: str, analysis_text: str) -> str:
    return (
        "Ваш запрос:\n"
        f"{user_request}\n\n"
        "Вот что я могу о вас сказать:\n"
        f"{analysis_text}\n\n"
        f"{DISCLAIMER}"
    )


def build_analysis_text(user_request: str, llm_analysis_text: str) -> str:
    if has_crisis_signals(user_request):
        return CRISIS_ANALYSIS

    cleaned = sanitize_user_input(llm_analysis_text, max_chars=2500)
    if not cleaned:
        return (
            "Мне сложно сделать вывод по вашему сообщению. "
            "Попробуйте описать ситуацию чуть подробнее, и я постараюсь поддержать вас безопасными шагами."
        )
    return cleaned
