"""Signed-state projections and membrane metrics for PooleOS."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .channel_telemetry import Coord


PLUS = 1
MINUS = -1
ZERO = 0
SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.signed_membrane_metrics"

N26_OFFSETS: tuple[Coord, ...] = tuple(
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if not (dx == 0 and dy == 0 and dz == 0)
)


@dataclass
class SignedLattice:
    states: dict[Coord, int] = field(default_factory=dict)

    def state(self, coord: Coord) -> int:
        return self.states.get(coord, ZERO)

    def set_state(self, coord: Coord, state: int) -> None:
        if state not in {MINUS, ZERO, PLUS}:
            raise ValueError(f"bad signed state {state!r}")
        if state == ZERO:
            self.states.pop(coord, None)
        else:
            self.states[coord] = state

    def positive_cells(self) -> set[Coord]:
        return {coord for coord, state in self.states.items() if state == PLUS}

    def negative_cells(self) -> set[Coord]:
        return {coord for coord, state in self.states.items() if state == MINUS}

    def projection(self, kind: str) -> set[Coord]:
        normalized = kind.strip().lower()
        if normalized in {"plus", "+", "positive"}:
            return self.positive_cells()
        if normalized in {"minus", "-", "negative"}:
            return self.negative_cells()
        if normalized in {"abs", "active", "absolute"}:
            return set(self.states)
        if normalized == "interface":
            return {coord for coord in self.omega() if self.local_overlap(coord) > 0}
        raise ValueError(f"unknown projection {kind!r}")

    def omega(self) -> set[Coord]:
        region = set(self.states)
        for coord in list(self.states):
            for dx, dy, dz in N26_OFFSETS:
                region.add((coord[0] + dx, coord[1] + dy, coord[2] + dz))
        return region or {(0, 0, 0)}

    def signed_support(self, coord: Coord, sign: int) -> int:
        if sign not in {PLUS, MINUS}:
            raise ValueError("support sign must be PLUS or MINUS")
        return sum(
            self.state((coord[0] + dx, coord[1] + dy, coord[2] + dz)) == sign
            for dx, dy, dz in N26_OFFSETS
        )

    def local_overlap(self, coord: Coord) -> int:
        plus = self.signed_support(coord, PLUS) + (1 if self.state(coord) == PLUS else 0)
        minus = self.signed_support(coord, MINUS) + (1 if self.state(coord) == MINUS else 0)
        return min(plus, minus)


@dataclass(frozen=True)
class MembraneMetrics:
    positive_count: int
    negative_count: int
    omega_size: int
    interface_support: int
    interface_density: float
    signed_imbalance: float
    thickness_y: float
    membrane_quality: float


def measure_membrane(lattice: SignedLattice, *, q0: int = 1, epsilon: float = 1e-9) -> MembraneMetrics:
    omega = sorted(lattice.omega())
    weighted: list[tuple[Coord, int]] = []
    total_support = 0
    plus_total = 0
    minus_total = 0

    for coord in omega:
        overlap = lattice.local_overlap(coord)
        plus_total += lattice.signed_support(coord, PLUS) + (1 if lattice.state(coord) == PLUS else 0)
        minus_total += lattice.signed_support(coord, MINUS) + (1 if lattice.state(coord) == MINUS else 0)
        if overlap >= q0:
            weighted.append((coord, overlap))
            total_support += overlap

    omega_size = len(omega)
    density = total_support / omega_size if omega_size else 0.0
    imbalance = abs(plus_total - minus_total) / (plus_total + minus_total + epsilon)

    if total_support:
        mean_y = sum(coord[1] * weight for coord, weight in weighted) / total_support
        variance_y = sum(((coord[1] - mean_y) ** 2) * weight for coord, weight in weighted) / total_support
        thickness_y = math.sqrt(variance_y)
    else:
        thickness_y = 0.0

    quality = (density / (1.0 + thickness_y)) * max(0.0, 1.0 - imbalance)
    return MembraneMetrics(
        positive_count=len(lattice.positive_cells()),
        negative_count=len(lattice.negative_cells()),
        omega_size=omega_size,
        interface_support=total_support,
        interface_density=density,
        signed_imbalance=imbalance,
        thickness_y=thickness_y,
        membrane_quality=quality,
    )


def metrics_to_json(metrics: MembraneMetrics) -> dict[str, Any]:
    return {
        "positive_count": metrics.positive_count,
        "negative_count": metrics.negative_count,
        "omega_size": metrics.omega_size,
        "interface_support": metrics.interface_support,
        "interface_density": f"{metrics.interface_density:.12g}",
        "signed_imbalance": f"{metrics.signed_imbalance:.12g}",
        "thickness_y": f"{metrics.thickness_y:.12g}",
        "membrane_quality": f"{metrics.membrane_quality:.12g}",
    }


def make_metrics_artifact(metrics: MembraneMetrics, *, claim: dict[str, Any], q0: int = 1, epsilon: float = 1e-9) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "claim": claim,
        "parameters": {
            "q0": q0,
            "epsilon": f"{epsilon:.12g}",
        },
        "summary": metrics_to_json(metrics),
    }


def mirrored_sheet_pair(size: int = 3, *, gap: int = 1) -> SignedLattice:
    lattice = SignedLattice()
    radius = size // 2
    for x in range(-radius, radius + 1):
        for z in range(-radius, radius + 1):
            lattice.set_state((x, -gap, z), PLUS)
            lattice.set_state((x, gap, z), MINUS)
    return lattice


def single_sign_sheet(size: int = 3, *, y: int = 0) -> SignedLattice:
    lattice = SignedLattice()
    radius = size // 2
    for x in range(-radius, radius + 1):
        for z in range(-radius, radius + 1):
            lattice.set_state((x, y, z), PLUS)
    return lattice

