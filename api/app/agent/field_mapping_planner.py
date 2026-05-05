"""AI 字段映射规划器，把原始列名识别为标准测量字段。

用户上传的表头经常不统一，甚至是中英混杂、自定义命名。
这个模块的目标不是“理解全部业务”，而是尽可能稳地识别出后续流程最需要的几列：
测量值、规格限、批次、样本编号、时间、序号等。
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from api.app.agent.factory import build_agent_model
from api.app.config import get_settings
from api.app.schemas import FieldMapping
from api.app.services.report_localization import has_cjk_text


class FieldMappingPlanResponse(BaseModel):
    """模型返回的结构化字段映射结果。

    这是 AI 层的轻量协议，后面还会再经过业务校验才真正用于标准化。
    """

    sample_id_column: str | None
    batch_column: str | None
    measurement_column: str
    lsl_column: str | None
    usl_column: str | None
    target_column: str | None
    timestamp_column: str | None
    sequence_column: str | None
    reasoning: str


class FieldMappingPlanner:
    """负责调用模型识别原始数据中的关键业务列。

    这个类把字段识别拆成三步：
    1. 构造提示词，把列名、类型和样例行给模型。
    2. 让模型按固定结构返回候选映射。
    3. 用代码做强校验，确保映射真的可执行。
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("DEEPEXCEL_OPENAI_API_KEY is required for AI field mapping")
        self.model = build_agent_model()

    def _build_messages(self, frame: pd.DataFrame, file_name: str) -> list[dict[str, str]]:
        """把列名、类型和样例数据压缩成模型容易消费的提示词。

        只给前 5 行示例，是为了让模型看见数据长相，同时控制 token 成本。
        """
        columns_with_dtypes = "\n".join(f"- {column}: {frame[column].dtype}" for column in frame.columns)
        head_csv = frame.head(5).to_csv(index=False)
        return [
            {
                "role": "system",
                "content": (
                    "You identify SPC dataset columns for a Chinese quality report. "
                    "Return only a JSON object with no markdown. "
                    "The reasoning field must be one Chinese sentence. "
                    "Every column field must be copied exactly from the provided candidate columns or set to null."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"File name: {file_name}\n"
                    f"Candidate columns:\n{columns_with_dtypes}\n"
                    f"First 5 rows:\n{head_csv}\n"
                    "Identify sample_id_column, batch_column, measurement_column, lsl_column, usl_column, "
                    "target_column, timestamp_column, sequence_column, and reasoning. "
                    "measurement_column is required and must point to a numeric column."
                ),
            },
        ]

    @staticmethod
    def _validate_optional_column(frame: pd.DataFrame, value: str | None, field_name: str) -> str | None:
        """校验可选字段要么为空，要么引用现有列名。

        模型返回的字符串必须原样命中 DataFrame 列名，不能“猜一个相似名字”。
        """
        if value is None:
            return None
        if value not in frame.columns:
            raise ValueError(f"{field_name} must reference an existing dataframe column")
        return value

    def _validate_response(self, frame: pd.DataFrame, response: FieldMappingPlanResponse) -> tuple[FieldMapping, str]:
        """把模型输出收敛为可执行映射，并检查关键约束。

        这里最重要的硬约束是：
        - measurement_column 必须存在；
        - measurement_column 必须真的是数值列；
        - reasoning 必须是非空中文。
        """
        measurement_column = self._validate_optional_column(frame, response.measurement_column, "measurement_column")
        if measurement_column is None:
            raise ValueError("measurement_column is required")
        if not pd.api.types.is_numeric_dtype(frame[measurement_column]):
            raise ValueError("measurement_column must be numeric")

        reasoning = response.reasoning.strip()
        if not reasoning:
            raise ValueError("reasoning must not be empty")
        if not has_cjk_text(reasoning):
            raise ValueError("reasoning must contain Chinese text")

        mapping = FieldMapping(
            sample_id_column=self._validate_optional_column(frame, response.sample_id_column, "sample_id_column"),
            batch_column=self._validate_optional_column(frame, response.batch_column, "batch_column"),
            measurement_column=measurement_column,
            lsl_column=self._validate_optional_column(frame, response.lsl_column, "lsl_column"),
            usl_column=self._validate_optional_column(frame, response.usl_column, "usl_column"),
            target_column=self._validate_optional_column(frame, response.target_column, "target_column"),
            timestamp_column=self._validate_optional_column(frame, response.timestamp_column, "timestamp_column"),
            sequence_column=self._validate_optional_column(frame, response.sequence_column, "sequence_column"),
        )
        return mapping, reasoning

    def plan(self, frame: pd.DataFrame, file_name: str) -> tuple[FieldMapping, str]:
        """执行字段识别并返回字段映射与中文推理说明。

        返回的 `FieldMapping` 会直接进入 `normalize_measurements()`，
        所以这里必须保证它已经是“可落地执行”的映射，而不是仅供参考的建议。
        """
        structured_model = self.model.with_structured_output(FieldMappingPlanResponse)
        response = structured_model.invoke(self._build_messages(frame, file_name))
        structured = FieldMappingPlanResponse.model_validate(response)
        return self._validate_response(frame, structured)


def build_field_mapping_planner() -> FieldMappingPlanner:
    """创建字段映射规划器实例。"""
    return FieldMappingPlanner()
