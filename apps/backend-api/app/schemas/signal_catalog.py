from typing import Literal

from pydantic import BaseModel, Field


SignalDataType = Literal[
    "analog",
    "analog_output",
    "binary",
    "binary_output",
    "counter",
    "string",
]

SignalSource = Literal["master", "sat01", "sat02"]


class SignalCatalogBase(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    unit: str | None = None
    description: str | None = None
    source: SignalSource = "master"
    dnp3_class: str = "Class 1"
    data_type: SignalDataType = "analog"
    dnp3_object_group: int = 30
    dnp3_index: int = 0
    scale: float = 1.0
    offset: float = 0.0
    supports_alarm: bool = False
    is_active: bool = True
    display_order: int = 0


class SignalCatalogCreate(SignalCatalogBase):
    pass


class SignalCatalogUpdate(BaseModel):
    label: str | None = None
    unit: str | None = None
    description: str | None = None
    source: SignalSource | None = None
    dnp3_class: str | None = None
    data_type: SignalDataType | None = None
    dnp3_object_group: int | None = None
    dnp3_index: int | None = None
    scale: float | None = None
    offset: float | None = None
    supports_alarm: bool | None = None
    is_active: bool | None = None
    display_order: int | None = None


class SignalCatalogRead(SignalCatalogBase):
    id: int

    class Config:
        from_attributes = True


class SignalLiveValue(BaseModel):
    """Canli degerler ekranina donulen tek satir."""

    signal_key: str
    signal_label: str
    unit: str | None = None
    source: str = "master"
    device_id: int
    device_code: str
    device_name: str
    value: float
    quality: str
    source_timestamp: str
