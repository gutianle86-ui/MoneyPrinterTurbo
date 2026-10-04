import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class Character(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    appearance: str = Field(min_length=1, max_length=1000)
    voice: str = Field(default="Tingting", max_length=100)
    voice_description: str = Field(default="", max_length=300)
    reference_uri: str = Field(default="", max_length=1000)
    reference_file: str = Field(default="", max_length=80)

    @field_validator("reference_uri")
    @classmethod
    def valid_reference_uri(cls, value):
        value = value.strip()
        if not value:
            return ""
        parsed = urlsplit(value)
        if parsed.scheme == "asset" and parsed.netloc.startswith("asset-"):
            return value
        if (
            parsed.scheme == "https"
            and parsed.netloc
            and not parsed.username
            and not parsed.password
        ):
            return value
        raise ValueError("角色参考素材必须使用 asset://asset-... 或 HTTPS 地址")

    @field_validator("reference_file")
    @classmethod
    def valid_reference_file(cls, value):
        if value and not re.fullmatch(
            r"[a-f0-9]{32}\.(png|jpg|jpeg|webp)", value, re.IGNORECASE
        ):
            raise ValueError("角色参考图文件名无效")
        return value


class Shot(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    scene: str = Field(min_length=1, max_length=200)
    visual: str = Field(min_length=1, max_length=2000)
    narration: str = Field(default="", max_length=300)
    speaker: str = Field(default="旁白", max_length=40)
    duration: int = Field(default=6, ge=2, le=12)
    characters: list[str] = Field(default_factory=list, max_length=5)
    purpose: str = Field(default="", max_length=300)
    start_state: str = Field(default="", max_length=500)
    end_state: str = Field(default="", max_length=500)
    beat_index: int | None = Field(default=None, ge=1, le=24)
    delivery: str = Field(default="", max_length=300)


StoryFormat = Literal["dialogue", "narration", "mixed"]


class DramaBeat(BaseModel):
    scene: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=1000)
    speaker: str = Field(default="", max_length=40)
    line: str = Field(default="", max_length=300)
    emotion: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_beat(self):
        if not self.scene.strip() or not self.action.strip():
            raise ValueError("每段剧本需要场景和动作")
        if self.line.strip() and not self.speaker.strip():
            raise ValueError("有台词的段落必须填写说话人")
        return self


class ContentBrief(BaseModel):
    # Missing format in saved briefs means the original narration workflow.
    format: StoryFormat = "narration"
    audience: str = Field(default="", max_length=300)
    source_notes: str = Field(default="", max_length=3000)
    promise: str = Field(default="", max_length=500)
    opening: str = Field(default="", max_length=500)
    payoff: str = Field(default="", max_length=500)
    cliffhanger: str = Field(default="", max_length=500)
    narration: str = Field(default="", max_length=3000)
    target_duration: int = Field(default=30, ge=15, le=120)
    beats: list[DramaBeat] = Field(default_factory=list, max_length=24)


class StylePreset(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    style: str = Field(min_length=1, max_length=500)

    @field_validator("name", "style")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称和画风不能为空")
        return value.strip()


class StyleRecommendation(StylePreset):
    reason: str = Field(min_length=1, max_length=500)


class BriefDraft(ContentBrief):
    recommended_style: StyleRecommendation


class WorkflowReview(BaseModel):
    stage: str = Field(pattern="^(content|preview|pilot)$")
    artifact_id: str = Field(default="", max_length=80)
    notes: str = Field(min_length=5, max_length=1000)


class ClipEdit(BaseModel):
    start: float = Field(default=0, ge=0, le=3600, allow_inf_nan=False)
    end: float | None = Field(default=None, gt=0, le=3600, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered(self):
        if self.end is not None and self.end <= self.start:
            raise ValueError("出点必须晚于入点")
        return self


class Script(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    hook: str = Field(min_length=1, max_length=500)
    synopsis: str = Field(min_length=1, max_length=2000)
    characters: list[Character] = Field(min_length=1, max_length=5)
    shots: list[Shot] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def check_characters(self):
        names = [c.name for c in self.characters]
        if len(set(names)) != len(names):
            raise ValueError("角色名称不能重复")
        for shot in self.shots:
            if set(shot.characters) - set(names):
                raise ValueError("分镜引用了未定义的角色")
            if shot.speaker not in names + ["旁白"] and (
                shot.narration.strip() or shot.speaker
            ):
                raise ValueError("说话人必须是角色或旁白")
        return self


class NewProject(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    premise: str = Field(min_length=1, max_length=5000)
    story_format: StoryFormat = "dialogue"
    style: str = Field(default="", max_length=500)
    style_mode: str = Field(default="auto", pattern="^(auto|preset|custom)$")
    style_preset_id: str = Field(default="", max_length=80)
    budget: float = Field(default=100, gt=0, le=100000, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def legacy_style(cls, values):
        if (
            isinstance(values, dict)
            and "style_mode" not in values
            and values.get("style")
        ):
            return {**values, "style_mode": "custom"}
        return values

    @model_validator(mode="after")
    def valid_style(self):
        self.style = self.style.strip()
        if self.style_mode == "custom" and not self.style:
            raise ValueError("请填写自定义画风")
        if self.style_mode == "preset" and not self.style_preset_id:
            raise ValueError("请选择画风预设")
        if self.style_mode != "preset":
            self.style_preset_id = ""
        return self


class GenerateRequest(BaseModel):
    shot_ids: list[str] = Field(min_length=1, max_length=24)
    mode: str = Field(pattern="^(preview|seedance)$")
    variants: int = Field(default=1, ge=1, le=3)
    confirm_paid: bool = False


class BatchShotDuration(BaseModel):
    shot_ids: list[str] = Field(min_length=1, max_length=24)
    duration: int = Field(ge=2, le=12)


class PublicationFeedback(BaseModel):
    platform: str = Field(default="", max_length=80)
    published_url: str = Field(default="", max_length=2000)
    views: int | None = Field(default=None, ge=0, le=10**12)
    likes: int | None = Field(default=None, ge=0, le=10**12)
    conversions: int | None = Field(default=None, ge=0, le=10**12)
    revenue: float | None = Field(default=None, ge=0, le=10**9, allow_inf_nan=False)
    actual_cost: float | None = Field(default=None, ge=0, le=10**9, allow_inf_nan=False)
    notes: str = Field(default="", max_length=2000)

    @field_validator("published_url")
    @classmethod
    def valid_url(cls, value):
        value = value.strip()
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("发布链接须使用 HTTP 或 HTTPS 地址")
        return value


class ExportRequest(BaseModel):
    kind: str = Field(default="preview", pattern="^(preview|production|animatic)$")
    voice: bool = False


class Settings(BaseModel):
    llm_base_url: str = Field(default="https://api.openai.com/v1", max_length=500)
    llm_model: str = Field(default="", max_length=200)
    llm_api_key: str = Field(default="", max_length=1000)
    llm_use_env_proxy: bool = True
    seedance_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3", max_length=500
    )
    seedance_model: str = Field(
        default="doubao-seedance-1-0-pro-250528", max_length=200
    )
    seedance_api_key: str = Field(default="", max_length=1000)
    estimate_per_second: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    seedance_estimates: dict[
        str, Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)]
    ] = Field(default_factory=dict, max_length=50)
