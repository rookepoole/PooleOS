"""Typed channel telemetry for PooleOS kernel experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol


Coord = tuple[int, int, int]
Coord2 = tuple[int, int]

VOID = "void"
BODY = "body"
SEED = "seed"

BASE_BIRTH_WINDOW = (5, 7)
BASE_SURVIVAL_WINDOW = (5, 9)


class LatticeLike(Protocol):
    def state(self, coord: Coord) -> str:
        ...

    def support_count(self, coord: Coord) -> int:
        ...

    def evaluation_region(self, margin: int | None = None) -> set[Coord]:
        ...


@dataclass(frozen=True)
class ChannelEvent:
    coord: Coord
    previous_state: str
    active_previous_state: str
    support_count: int
    raw_channel: str
    accepted: bool
    next_state: str
    psi: int


@dataclass
class ChannelSummary:
    events: list[ChannelEvent] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    births: int = 0
    survivors: int = 0
    deaths: int = 0
    void_stays: int = 0
    psi_total: int = 0

    def add(self, event: ChannelEvent) -> None:
        self.events.append(event)
        self.counts[event.raw_channel] = self.counts.get(event.raw_channel, 0) + 1
        self.psi_total += event.psi

        if event.previous_state == VOID and event.next_state == BODY:
            self.births += 1
        elif event.active_previous_state == BODY and event.next_state == BODY:
            self.survivors += 1
        elif event.active_previous_state == BODY and event.next_state == VOID:
            self.deaths += 1
        else:
            self.void_stays += 1

    def accepted_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for event in self.events:
            if event.accepted:
                out[event.raw_channel] = out.get(event.raw_channel, 0) + 1
        return out


def active_state(state: str) -> str:
    return BODY if state == SEED else state


def support_strain(k: int, is_active: bool) -> int:
    capacity = 7 + (2 if is_active else 0)
    excess = max(0, k - capacity)
    deficit = max(0, 5 - k)
    return excess - deficit


def channel_for_site(
    lattice: LatticeLike,
    coord: Coord,
    *,
    birth_window: tuple[int, int] = BASE_BIRTH_WINDOW,
    survival_window: tuple[int, int] = BASE_SURVIVAL_WINDOW,
) -> ChannelEvent:
    previous = lattice.state(coord)
    active_previous = active_state(previous)
    is_active = active_previous == BODY
    k = lattice.support_count(coord)

    if is_active:
        accepted = survival_window[0] <= k <= survival_window[1]
        next_state = BODY if accepted else VOID
        raw_channel = "O10+" if k >= 10 else f"S{k}"
    else:
        accepted = birth_window[0] <= k <= birth_window[1]
        next_state = BODY if accepted else VOID
        raw_channel = f"B{k}"

    return ChannelEvent(
        coord=coord,
        previous_state=previous,
        active_previous_state=active_previous,
        support_count=k,
        raw_channel=raw_channel,
        accepted=accepted,
        next_state=next_state,
        psi=support_strain(k, is_active),
    )


def measure_channels(
    lattice: LatticeLike,
    coords: Iterable[Coord] | None = None,
    *,
    birth_window: tuple[int, int] = BASE_BIRTH_WINDOW,
    survival_window: tuple[int, int] = BASE_SURVIVAL_WINDOW,
) -> ChannelSummary:
    if coords is None:
        coords = sorted(lattice.evaluation_region())
    summary = ChannelSummary()
    for coord in sorted(coords):
        summary.add(
            channel_for_site(
                lattice,
                coord,
                birth_window=birth_window,
                survival_window=survival_window,
            )
        )
    return summary


def collapsed_body(summary: ChannelSummary) -> set[Coord]:
    return {event.coord for event in summary.events if event.next_state == BODY}


def open_defect_count(defects: set[Coord2], u: Coord2) -> int:
    x, y = u
    return sum(
        (x + dx, y + dy) in defects
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if not (dx == 0 and dy == 0)
    )


def closed_defect_count(defects: set[Coord2], u: Coord2) -> int:
    x, y = u
    return sum((x + dx, y + dy) in defects for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def defect_channel_label(coord: Coord, defects: set[Coord2], *, sheet_z: int = 0) -> str | None:
    x, y, z = coord
    u = (x, y)
    if z == sheet_z:
        q = open_defect_count(defects, u)
        return f"B{8 - q}" if u in defects else f"S{8 - q}"
    if abs(z - sheet_z) == 1:
        r = closed_defect_count(defects, u)
        return f"B{9 - r}"
    return None


def rectangular_defects(width: int, height: int, *, origin: Coord2 = (0, 0)) -> set[Coord2]:
    ox, oy = origin
    return {(ox + x, oy + y) for x in range(width) for y in range(height)}


def normal_layer_candidate_coords(defects: set[Coord2], *, sheet_z: int = 0) -> set[Coord]:
    out: set[Coord] = set()
    for x, y in defects:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.add((x + dx, y + dy, sheet_z - 1))
                out.add((x + dx, y + dy, sheet_z + 1))
    return out


def expected_rectangle_birth_spectrum(width: int, height: int) -> Mapping[str, int]:
    return {
        "B5": 12,
        "B6": 4 * width + 4 * height - 16,
        "B7": 16,
    }

