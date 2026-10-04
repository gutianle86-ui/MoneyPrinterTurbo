"""Reusable visual directions, independent of any story's characters or plot."""

CONSISTENCY = (
    "保持人物五官、发型和身材比例一致，同一场景服装一致；具体场景与情绪由分镜指定。"
)

PRESETS = [
    {
        "id": "urban-romance",
        "name": "都市甜宠",
        "style": "现代都市甜宠二维动漫风，精致清晰线稿，低饱和暖色，柔和自然光，表情细腻生动，轻松浪漫。"
        + CONSISTENCY,
    },
    {
        "id": "period-romance",
        "name": "古风言情",
        "style": "古风言情二维动漫风，细腻线稿，雅致柔和配色，织物与建筑具有古典质感，含蓄浪漫，光影随场景变化。"
        + CONSISTENCY,
    },
    {
        "id": "mystery",
        "name": "悬疑惊悚",
        "style": "二维悬疑漫剧，蓝灰冷色调，克制的明暗对比与局部光源，紧张神秘，主体清晰，避免全画面过暗。"
        + CONSISTENCY,
    },
    {
        "id": "fantasy",
        "name": "玄幻热血",
        "style": "东方玄幻二维动漫风，利落线稿，清晰轮廓，鲜明但有层次的色彩，富有力量感的构图，光效克制，动作易辨认。"
        + CONSISTENCY,
    },
    {
        "id": "urban-drama",
        "name": "都市情感",
        "style": "现代都市二维写实漫画风，自然肤色，中性色调，真实生活光线，克制细腻的表情，突出人物关系与情绪。"
        + CONSISTENCY,
    },
]


def require_style(project):
    if not project.get("style", "").strip():
        raise ValueError("请先采用推荐画风，或在项目设置中选择预设 / 自定义画风")


def apply_style(project, style):
    if project.get("style") != style:
        project["characters_approved"] = False
        for shot in project["shots"]:
            shot["approved"] = False
    project["style"] = style
