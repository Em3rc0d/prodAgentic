from agents.visual_agent import SYSTEM_PROMPT
from core.visual_direction import VisualDirectionPolicy, VisualFormat
from models.visual import AspectRatio, VisualRenderRequest, VisualStyle


def test_architecture_content_chooses_schematic_not_cinematic_art():
    content = (
        "Separamos el LLM del validador determinista en una arquitectura con API gateway, "
        "MongoDB y un pipeline de Grounding antes de publicar."
    )
    direction = VisualDirectionPolicy.select(content, style="educational")

    assert direction.visual_format == VisualFormat.ARCHITECTURE_SCHEMATIC
    assert direction.recommended_aspect_ratio == "4:5"
    assert direction.recommended_style == "technical_editorial"
    assert "photorealistic server rooms" in direction.treatment


def test_ci_story_chooses_artifact_board():
    content = (
        "Un test de pytest dejó rojo el CI. El commit siguiente corrigió el boundary y el workflow volvió a verde."
    )
    direction = VisualDirectionPolicy.select(content, style="storytelling")

    assert direction.visual_format == VisualFormat.ARTIFACT_BOARD
    assert "artifact board" in direction.composition.lower()


def test_process_content_chooses_process_flow():
    content = (
        "El pipeline tiene cuatro pasos: extraer claims, validar, reintentar una vez y activar fallback."
    )
    direction = VisualDirectionPolicy.select(content, style="educational")

    assert direction.visual_format == VisualFormat.PROCESS_FLOW


def test_comparison_wins_over_other_visual_signals():
    content = (
        "Comparamos prompt-only vs validación determinista en un pipeline con MongoDB y tests de integración."
    )
    direction = VisualDirectionPolicy.select(content, style="educational")

    assert direction.visual_format == VisualFormat.COMPARISON


def test_strong_position_without_system_artifacts_becomes_editorial_poster():
    content = "Un LLM nunca debería poder declararse a sí mismo verdadero."
    direction = VisualDirectionPolicy.select(content, style="controversial")

    assert direction.visual_format == VisualFormat.EDITORIAL_POSTER


def test_visual_agent_explicitly_blocks_generic_ai_wallpaper_language():
    lowered = SYSTEM_PROMPT.lower()

    for banned in (
        "cyberpunk",
        "glowing orbs",
        "holograms",
        "glowing brains",
        "humanoid robots",
        "blue-purple energy waves",
        "8k masterpiece",
        "volumetric lighting",
    ):
        assert banned in lowered

    assert "do not default" in lowered
    assert "technical editorial" in lowered
    assert "communicate the post's core idea at feed size" in lowered


def test_render_contract_defaults_to_linkedin_portrait_editorial():
    request = VisualRenderRequest(
        run_id="run-visual",
        idempotency_key="visual-intent-123",
        prompt="Clean architecture schematic",
    )

    assert request.aspect_ratio == AspectRatio.PORTRAIT
    assert request.style == VisualStyle.TECHNICAL_EDITORIAL
