from bot_logic import (
    CRISIS_ANALYSIS,
    build_analysis_text,
    build_template_response,
    has_crisis_signals,
    sanitize_user_input,
)


def test_template_response_structure() -> None:
    result = build_template_response("Мне тревожно", "Вы выглядите уставшим")

    assert result.startswith("Ваш запрос:\nМне тревожно\n\nВот что я могу о вас сказать:\n")
    assert "Помните, что эти советы могут вам помочь" in result


def test_sanitize_user_input_limits_and_cleans() -> None:
    raw = "  Привет\x00   мир  " + "а" * 3000
    cleaned = sanitize_user_input(raw, max_chars=100)

    assert "\x00" not in cleaned
    assert "  " not in cleaned
    assert len(cleaned) == 100


def test_crisis_behavior_overrides_llm_text() -> None:
    user_request = "Я хочу покончить с собой"
    llm_text = "какой-то обычный анализ"

    assert has_crisis_signals(user_request)
    assert build_analysis_text(user_request, llm_text) == CRISIS_ANALYSIS
