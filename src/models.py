"""
Modelos de datos centrales con Pydantic v2.
"""

from dataclasses import dataclass
from datetime import date, time, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerados
# ---------------------------------------------------------------------------

class MatchStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    CONFLICT = "conflict"
    MANUALLY_MODIFIED = "manually_modified"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Entidades base
# ---------------------------------------------------------------------------

class Player(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    surname: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    level: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}".strip()


class Pair(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                        # Nombre legible, p.ej. "García / Martínez"
    player_1: Player
    player_2: Player
    group_id: Optional[str] = None
    # Disponibilidad de la pareja (extraída de Observaciones en Syltek)
    available_weekdays: list[int] = Field(default_factory=list)  # 0=Lun … 6=Dom, vacío=cualquier día
    available_from: Optional[time] = None     # hora mínima de juego para esta pareja
    available_until: Optional[time] = None    # hora máxima
    availability_notes: str = ""              # texto original de Observaciones
    # Pista fija: día y hora preferidos (PF X2030 → miércoles 20:30)
    preferred_weekday: Optional[int] = None   # 0=Lun … 6=Dom
    preferred_time: Optional[time] = None     # hora exacta preferida
    # Si True, el scheduler NO asigna horario automáticamente (p.ej. "MIRAR MAIL")
    manual_only: bool = False

    @property
    def display_name(self) -> str:
        return self.name or f"{self.player_1.full_name} / {self.player_2.full_name}"


class Group(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                        # "Grupo A", "Nivel 1", etc.
    level: Optional[str] = None
    gender: Gender = Gender.UNKNOWN
    pairs: list[Pair] = Field(default_factory=list)


class Court(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                        # "Pista 1", "Pista Indoor 2", etc.
    indoor: bool = False
    active: bool = True


class Booking(BaseModel):
    """Reserva ya existente en Syltek (bloquea ese hueco)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    court_id: str
    court_name: str = ""
    start_datetime: datetime
    end_datetime: datetime
    description: str = ""
    source: str = "syltek"           # "syltek" | "manual"


@dataclass
class AvailabilitySlot:
    """Hueco libre en una pista en un momento dado. Dataclass (sin validación Pydantic)."""
    court: Court
    date: date
    start_time: time
    end_time: time

    @property
    def start_datetime(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

    @property
    def end_datetime(self) -> datetime:
        return datetime.combine(self.date, self.end_time)


# ---------------------------------------------------------------------------
# Partidos y resultados
# ---------------------------------------------------------------------------

class Match(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    group_id: str
    group_name: str = ""
    pair_1: Pair
    pair_2: Pair
    suggested_date: Optional[date] = None
    suggested_start_time: Optional[time] = None
    suggested_end_time: Optional[time] = None
    court: Optional[Court] = None
    status: MatchStatus = MatchStatus.PENDING
    conflict_reason: Optional[str] = None
    notes: str = ""

    @property
    def is_scheduled(self) -> bool:
        return self.status == MatchStatus.SCHEDULED

    @property
    def label(self) -> str:
        return f"{self.pair_1.display_name} vs {self.pair_2.display_name}"


class Conflict(BaseModel):
    match_id: str
    match_label: str
    reason: str
    pair_ids_involved: list[str] = Field(default_factory=list)


class ScheduleResult(BaseModel):
    scheduled: list[Match] = Field(default_factory=list)
    conflicts: list[Match] = Field(default_factory=list)
    total_matches: int = 0
    courts_used: list[str] = Field(default_factory=list)
    conflict_details: list[Conflict] = Field(default_factory=list)

    @property
    def scheduled_count(self) -> int:
        return len(self.scheduled)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def success_rate(self) -> float:
        if self.total_matches == 0:
            return 0.0
        return self.scheduled_count / self.total_matches * 100


class BalanceWeights(BaseModel):
    """
    Pesos del scheduler para equilibrar la asignación.
    Valor más alto = penalización más fuerte = se evita más.
    """
    same_hour_penalty: float = 10.0       # misma franja horaria que un partido previo de la pareja
    same_weekday_penalty: float = 6.0     # mismo día de la semana repetido para la pareja
    same_court_penalty: float = 2.0       # misma pista repetida para la pareja
    day_load_penalty: float = 1.5         # cuanto más cargado está el día, peor
    court_load_penalty: float = 1.0       # cuanto más cargada está la pista, peor
    global_hour_load_penalty: float = 3.0 # evita concentrar demasiados partidos en la misma hora
    group_hour_penalty: float = 14.0      # evita que un grupo juegue casi siempre a la misma hora
    early_day_bonus: float = 0.2          # preferencia muy leve por programar pronto en la fase
    preferred_slot_bonus: float = 25.0    # fuerte preferencia por día+hora de pista fija (PF)


class RankingPhase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Fase 1"
    start_date: date
    end_date: date
    groups: list[Group] = Field(default_factory=list)
    courts: list[Court] = Field(default_factory=list)
    bookings: list[Booking] = Field(default_factory=list)
    match_duration_minutes: int = 90
    day_start_time: time = time(16, 0)
    day_end_time: time = time(22, 30)
    # Separación entre posibles horas de inicio. 30 min da mucha más variedad
    # que usar bloques fijos de 90 min (16:00, 17:30, 19:00, 20:30).
    slot_step_minutes: int = 30
    max_matches_per_week: int = 1
    # Separación mínima entre dos partidos consecutivos de la misma pareja (en días).
    # 0 = sin restricción. Es una restricción dura.
    min_days_between_matches: int = 2
    # Semilla para que la asignación sea reproducible. None = aleatorio cada vez.
    random_seed: Optional[int] = 42
    # Pesos del scoring del scheduler.
    balance_weights: BalanceWeights = Field(default_factory=BalanceWeights)
