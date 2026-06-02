"""
Modelos de datos para el módulo de torneos.
Independiente del ranking — puede usarse para cualquier torneo de pádel.
"""

from datetime import date, time, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerados
# ---------------------------------------------------------------------------

class TournamentFormat(str, Enum):
    GROUPS         = "groups"          # Solo fase de grupos (round-robin)
    BRACKET        = "bracket"         # Solo cuadro eliminatorio
    GROUPS_BRACKET = "groups_bracket"  # Grupos → clasificados pasan al cuadro


class TournamentCategory(str, Enum):
    MASCULINO = "masculino"
    FEMENINO  = "femenino"
    MIXTO     = "mixto"

    @property
    def label(self) -> str:
        return {"masculino": "Masculino", "femenino": "Femenino", "mixto": "Mixto"}[self.value]

    @property
    def icon(self) -> str:
        return {"masculino": "👨", "femenino": "👩", "mixto": "🤝"}[self.value]

    @property
    def color(self) -> str:
        return {"masculino": "#1565c0", "femenino": "#c2185b", "mixto": "#6a1b9a"}[self.value]


class TournamentSubcategory(str, Enum):
    # Pádel — categorías por número
    PRIMERA  = "1a"
    SEGUNDA  = "2a"
    TERCERA  = "3a"
    CUARTA   = "4a"
    QUINTA   = "5a"
    # Pickleball — niveles por puntuación
    PB_SUB3  = "pb_lt3"   # -3
    PB_3     = "pb_3"     # +3
    PB_35    = "pb_35"    # +3.5
    PB_4     = "pb_4"     # +4
    PB_45    = "pb_45"    # +4.5

    @property
    def label(self) -> str:
        return {
            "1a": "1ª", "2a": "2ª", "3a": "3ª", "4a": "4ª", "5a": "5ª",
            "pb_lt3": "-3", "pb_3": "+3", "pb_35": "+3.5", "pb_4": "+4", "pb_45": "+4.5",
        }[self.value]

    @property
    def sport(self) -> str:
        return "pickleball" if self.value.startswith("pb_") else "padel"


# Subcategorías agrupadas por deporte (para construir los selectores de la UI)
SUBCATEGORIES_BY_SPORT: dict[str, list["TournamentSubcategory"]] = {
    "padel": [
        TournamentSubcategory.PRIMERA, TournamentSubcategory.SEGUNDA,
        TournamentSubcategory.TERCERA, TournamentSubcategory.CUARTA,
        TournamentSubcategory.QUINTA,
    ],
    "pickleball": [
        TournamentSubcategory.PB_SUB3, TournamentSubcategory.PB_3,
        TournamentSubcategory.PB_35, TournamentSubcategory.PB_4,
        TournamentSubcategory.PB_45,
    ],
}


class MatchRound(str, Enum):
    GROUP         = "group"
    ROUND_OF_16   = "round_of_16"
    QUARTERFINAL  = "quarterfinal"
    SEMIFINAL     = "semifinal"
    THIRD_PLACE   = "third_place"
    FINAL         = "final"

    @property
    def order(self) -> int:
        return {
            MatchRound.GROUP:        0,
            MatchRound.ROUND_OF_16:  1,
            MatchRound.QUARTERFINAL: 2,
            MatchRound.SEMIFINAL:    3,
            MatchRound.THIRD_PLACE:  4,
            MatchRound.FINAL:        5,
        }[self]

    @property
    def display(self) -> str:
        return {
            MatchRound.GROUP:        "Fase de Grupos",
            MatchRound.ROUND_OF_16:  "Dieciseisavos",
            MatchRound.QUARTERFINAL: "Cuartos de Final",
            MatchRound.SEMIFINAL:    "Semifinal",
            MatchRound.THIRD_PLACE:  "3er y 4º Puesto",
            MatchRound.FINAL:        "Final",
        }[self]


class TMatchStatus(str, Enum):
    PENDING   = "pending"
    SCHEDULED = "scheduled"
    CONFLICT  = "conflict"


# ---------------------------------------------------------------------------
# Entidades base del torneo
# ---------------------------------------------------------------------------

class TournamentCourt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    active: bool = True


class TournamentPlayer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    surname: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}".strip()


class TournamentPair(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                          # "García / López"
    player_1: TournamentPlayer
    player_2: TournamentPlayer
    seed: Optional[int] = None         # Cabeza de serie (1 = favorito)
    group_id: Optional[str] = None     # Asignado en la generación
    division: Optional[str] = None     # Clave de división "categoria:subcategoria" (ej. "masculino:1a")
    assigned_group: Optional[int] = None  # Índice de grupo manual (0=A, 1=B, …). None = reparto automático

    @property
    def display_name(self) -> str:
        return self.name or f"{self.player_1.full_name} / {self.player_2.full_name}"


class TournamentGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                          # "Grupo A", "Grupo B", …
    pairs: list[TournamentPair] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Partido de torneo
# ---------------------------------------------------------------------------

class TournamentMatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    round: MatchRound
    match_number: int                  # Número secuencial dentro de la ronda
    group_id: Optional[str] = None     # Sólo en fase de grupos
    division: Optional[str] = None     # Clave de división "categoria:subcategoria"

    # Rivales: pueden ser None si aún no se conoce el ganador de un partido previo
    pair_1: Optional[TournamentPair] = None
    pair_2: Optional[TournamentPair] = None
    # Etiquetas legibles cuando los rivales son TBD
    pair_1_label: str = ""
    pair_2_label: str = ""

    # Horario asignado
    match_date: Optional[date]    = None
    start_time: Optional[time]    = None
    end_time:   Optional[time]    = None
    court:      Optional[TournamentCourt] = None

    status: TMatchStatus = TMatchStatus.PENDING
    conflict_reason: Optional[str] = None

    # Resultado del partido (P1 torneos)
    winner_id: Optional[str] = None      # id de la pareja ganadora
    score: str = ""                       # marcador legible: "6-4 6-3"

    @property
    def is_played(self) -> bool:
        return self.winner_id is not None

    @property
    def winner_pair(self) -> Optional["TournamentPair"]:
        if self.winner_id is None:
            return None
        if self.pair_1 and self.pair_1.id == self.winner_id:
            return self.pair_1
        if self.pair_2 and self.pair_2.id == self.winner_id:
            return self.pair_2
        return None

    @property
    def loser_pair(self) -> Optional["TournamentPair"]:
        if self.winner_id is None:
            return None
        if self.pair_1 and self.pair_1.id == self.winner_id:
            return self.pair_2
        if self.pair_2 and self.pair_2.id == self.winner_id:
            return self.pair_1
        return None

    @property
    def p1_display(self) -> str:
        if self.pair_1:
            return self.pair_1.display_name
        return self.pair_1_label or "Por determinar"

    @property
    def p2_display(self) -> str:
        if self.pair_2:
            return self.pair_2.display_name
        return self.pair_2_label or "Por determinar"

    @property
    def label(self) -> str:
        return f"{self.p1_display} vs {self.p2_display}"

    @property
    def round_display(self) -> str:
        return self.round.display


# ---------------------------------------------------------------------------
# División (una categoría/subcategoría con su propio cuadro)
# ---------------------------------------------------------------------------

class TournamentDivision(BaseModel):
    """
    Una categoría dentro de un torneo (ej. "Masculino 1ª").
    Tiene su propio formato, parejas, grupos y cuadro — independiente de las
    demás divisiones, pero comparte pistas y horario con ellas.
    """
    key: str                            # "masculino:1a"
    category:    Optional[TournamentCategory]    = None
    subcategory: Optional[TournamentSubcategory] = None

    # Formato propio de la división
    format: TournamentFormat = TournamentFormat.GROUPS
    group_size:        int  = 4
    num_groups:        int  = 0    # 0 = derivar de group_size; >0 = nº exacto de grupos
    groups_qualifiers: int  = 2
    bracket_size:      int  = 8
    third_place_match: bool = False

    # Parejas y estructura generada (propias de esta división)
    pairs:   list[TournamentPair]  = Field(default_factory=list)
    groups:  list[TournamentGroup] = Field(default_factory=list)
    matches: list[TournamentMatch] = Field(default_factory=list)

    @property
    def label(self) -> str:
        parts = []
        if self.category:
            parts.append(self.category.label)
        if self.subcategory:
            parts.append(self.subcategory.label)
        return " ".join(parts) or self.key or "Categoría"

    @property
    def scheduled_count(self) -> int:
        return sum(1 for m in self.matches if m.status == TMatchStatus.SCHEDULED)


# ---------------------------------------------------------------------------
# Inscripción pública de una pareja
# ---------------------------------------------------------------------------

class RegistrationStatus(str, Enum):
    PENDING  = "pending"   # esperando revisión del admin
    APPROVED = "approved"  # aprobada → pasa a t.pairs
    REJECTED = "rejected"  # rechazada


class TournamentRegistration(BaseModel):
    """
    Registro de una pareja enviado desde el enlace público de inscripción.
    El admin lo revisa y aprueba (→ pasa a TournamentConfig.pairs) o rechaza.
    """
    id:          str = Field(default_factory=lambda: str(uuid4()))
    pair_name:   str = ""
    player1_name: str = ""
    player1_phone: Optional[str] = None
    player1_email: Optional[str] = None
    player2_name: str = ""
    player2_phone: Optional[str] = None
    player2_email: Optional[str] = None
    division:    Optional[str] = None    # categoría solicitada
    notes:       str = ""                # mensaje libre del jugador
    status:      RegistrationStatus = RegistrationStatus.PENDING
    submitted_at: str = ""               # ISO timestamp


# ---------------------------------------------------------------------------
# Configuración del torneo (objeto raíz)
# ---------------------------------------------------------------------------

class TournamentConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Torneo"

    # Identidad del torneo
    category:    Optional[TournamentCategory]    = None
    subcategory: Optional[TournamentSubcategory] = None
    # Soporte multi-categoría/subcategoría (formato: "masculino:1a", "mixto:3a", ...).
    # Se mantiene `category`/`subcategory` por compatibilidad con datos antiguos.
    divisions: list[str] = Field(default_factory=list)
    # Tandas de juego: {division_key: nº de tanda (1, 2, 3…)}. Las categorías de
    # la tanda 1 se juegan primero; las de la 2 después, etc. Vacío o todas con
    # el mismo número = todas se juegan a la vez.
    division_waves: dict[str, int] = Field(default_factory=dict)
    is_top:      bool   = False        # Torneo TOP (máximo prestigio)
    prize:       str    = ""           # Premio / descripción del torneo
    location:    str    = ""           # Club / sede

    # Fechas
    start_date: date
    end_date:   date                   # Mismo día = torneo de un día

    # Recursos
    courts: list[TournamentCourt] = Field(default_factory=list)
    pairs:  list[TournamentPair]  = Field(default_factory=list)

    # Formato
    format: TournamentFormat = TournamentFormat.GROUPS

    # Parámetros de tiempo
    match_duration_minutes:    int  = 60
    semifinal_duration_minutes: int = 0    # 0 = usar duración general
    final_duration_minutes:     int = 0    # 0 = usar duración general
    rest_between_matches_min:  int  = 15   # Descanso mínimo para el mismo equipo
    day_start_time:            time = time(9, 0)
    day_end_time:              time = time(22, 0)

    # Parámetros de grupos
    group_size:                int  = 4    # Parejas por grupo
    groups_qualifiers:         int  = 2    # Clasificados por grupo al cuadro (si formato mixto)

    # Parámetros de cuadro
    bracket_size:              int  = 8    # 4 / 8 / 16
    third_place_match:         bool = False

    # Datos generados (vacíos hasta que se genera la estructura)
    # Para torneos multi-categoría, `matches`/`groups` son la UNIÓN de todas las
    # divisiones (para el scheduler y vistas globales); cada división mantiene
    # además su propia estructura en `division_draws`.
    groups:  list[TournamentGroup] = Field(default_factory=list)
    matches: list[TournamentMatch] = Field(default_factory=list)
    division_draws: list[TournamentDivision] = Field(default_factory=list)

    # Inscripciones públicas: parejas que se registran desde el enlace público
    registration_open: bool = False           # el admin abre/cierra las inscripciones
    registrations: list["TournamentRegistration"] = Field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Propiedades de conveniencia
    # ---------------------------------------------------------------------------

    @property
    def scheduled_count(self) -> int:
        return sum(1 for m in self.matches if m.status == TMatchStatus.SCHEDULED)

    @property
    def conflict_count(self) -> int:
        return sum(1 for m in self.matches if m.status == TMatchStatus.CONFLICT)

    @property
    def total_match_count(self) -> int:
        return len(self.matches)

    @property
    def is_multi_division(self) -> bool:
        return len(self.division_draws) > 0

    def division_for_pair(self, pair: "TournamentPair") -> Optional[str]:
        """Clave de división de una pareja (o la primaria del torneo si no tiene)."""
        return pair.division
