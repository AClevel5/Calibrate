"""Pure nutrition math — scaling per-100 g values and rolling up day totals."""

from dataclasses import dataclass


@dataclass
class Macros:
    calories: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(
            self.calories + other.calories,
            self.protein + other.protein,
            self.carbs + other.carbs,
            self.fat + other.fat,
        )

    def rounded(self) -> "Macros":
        return Macros(
            round(self.calories),
            round(self.protein, 1),
            round(self.carbs, 1),
            round(self.fat, 1),
        )


def scale_per_100g(per_100g: Macros, grams: float) -> Macros:
    """Scale a per-100 g nutrition profile to an arbitrary gram quantity."""
    factor = grams / 100.0
    return Macros(
        per_100g.calories * factor,
        per_100g.protein * factor,
        per_100g.carbs * factor,
        per_100g.fat * factor,
    )
