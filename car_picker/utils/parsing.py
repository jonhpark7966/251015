"""Utilities for building and caching the car metadata index."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Extend this list if you find additional manufacturers in the dataset.
DEFAULT_MAKE_ALIASES: Dict[str, List[str]] = {
    "Acura": ["acura"],
    "Alfa Romeo": ["alfa", "alfa romeo"],
    "Aston Martin": ["aston", "aston martin"],
    "Audi": ["audi"],
    "Bentley": ["bentley"],
    "BMW": ["bmw"],
    "Buick": ["buick"],
    "Cadillac": ["cadillac"],
    "Chevrolet": ["chevrolet", "chevy"],
    "Chrysler": ["chrysler"],
    "Dodge": ["dodge"],
    "Ferrari": ["ferrari"],
    "Fiat": ["fiat"],
    "Ford": ["ford"],
    "GMC": ["gmc"],
    "Honda": ["honda"],
    "Hyundai": ["hyundai"],
    "Infiniti": ["infiniti"],
    "Jaguar": ["jaguar"],
    "Jeep": ["jeep"],
    "Kia": ["kia"],
    "Lamborghini": ["lamborghini"],
    "Land Rover": ["land rover", "landrover"],
    "Lexus": ["lexus"],
    "Lincoln": ["lincoln"],
    "Maserati": ["maserati"],
    "Mazda": ["mazda"],
    "McLaren": ["mclaren"],
    "Mercedes-Benz": ["mercedes", "mercedes benz", "mercedes-benz"],
    "Mini": ["mini"],
    "Mitsubishi": ["mitsubishi"],
    "Nissan": ["nissan"],
    "Porsche": ["porsche"],
    "Ram": ["ram"],
    "Rolls-Royce": ["rolls royce", "rolls-royce"],
    "Saab": ["saab"],
    "Scion": ["scion"],
    "Subaru": ["subaru"],
    "Tesla": ["tesla"],
    "Toyota": ["toyota"],
    "Volkswagen": ["volkswagen", "vw"],
    "Volvo": ["volvo"],
}

YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")


@dataclass(frozen=True)
class CarRecord:
    """Single parsed entry for an image."""

    path: str  # Stored relative to the data directory
    make: str
    model: str
    year: int

    @property
    def label(self) -> str:
        return f"{self.make} {self.model} {self.year}"


@dataclass
class Lexicon:
    makes: Dict[str, List[str]]
    _alias_lookup: Dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        alias_lookup: Dict[str, str] = {}
        for canonical, aliases in self.makes.items():
            tokens = aliases + [canonical]
            for alias in tokens:
                normalized = normalize_name(alias)
                alias_lookup[normalized] = canonical
        self._alias_lookup = alias_lookup

    def resolve_make(self, tokens: Sequence[str]) -> Tuple[Optional[str], int]:
        """
        Attempt to resolve manufacturer from a sequence of tokens.

        Returns the canonical make name and the number of tokens consumed.
        """
        max_window = min(len(tokens), 3)
        token_list = list(tokens)
        for size in range(max_window, 0, -1):
            candidate = normalize_name(" ".join(token_list[:size]))
            match = self._alias_lookup.get(candidate)
            if match:
                return match, size
        return None, 0

    def to_dict(self) -> Dict[str, Dict[str, List[str]]]:
        return {"makes": self.makes}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def ensure_lexicon(lexicon_path: Path) -> Lexicon:
    if lexicon_path.exists():
        with lexicon_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        makes = data.get("makes") or DEFAULT_MAKE_ALIASES
    else:
        makes = DEFAULT_MAKE_ALIASES
        lexicon_path.parent.mkdir(parents=True, exist_ok=True)
        with lexicon_path.open("w", encoding="utf-8") as handle:
            json.dump({"makes": makes}, handle, indent=2, ensure_ascii=False)
    return Lexicon(makes=makes)


def load_or_build_index(
    data_dir: Path,
    index_path: Path,
    lexicon_path: Path,
    *,
    force_rebuild: bool = False,
) -> List[CarRecord]:
    lexicon = ensure_lexicon(lexicon_path)
    if index_path.exists() and not force_rebuild:
        with index_path.open("r", encoding="utf-8") as handle:
            raw_records = json.load(handle)
        return [CarRecord(**record) for record in raw_records]

    records = build_index(data_dir=data_dir, lexicon=lexicon)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(record) for record in records], handle, indent=2, ensure_ascii=False)
    return records


def build_index(data_dir: Path, lexicon: Lexicon) -> List[CarRecord]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    supported_exts = {".jpg", ".jpeg", ".png"}
    records: List[CarRecord] = []

    for path in sorted(data_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in supported_exts:
            continue
        record = parse_car_filename(path, base_dir=data_dir, lexicon=lexicon)
        if record:
            records.append(record)
        else:
            logging.debug("Failed to parse car metadata for %s", path.name)

    return records


def parse_car_filename(path: Path, base_dir: Path, lexicon: Lexicon) -> Optional[CarRecord]:
    stem = path.stem
    tokens = stem.split("_")
    year_idx = find_year_index(tokens)
    if year_idx is None or year_idx == 0:
        return None

    pre_year_tokens = tokens[:year_idx]
    if not pre_year_tokens:
        return None

    make, consumed = lexicon.resolve_make(pre_year_tokens)
    if not make:
        # Default to the first token if lookup fails.
        make = humanize_token(pre_year_tokens[0])
        consumed = 1

    model_tokens = pre_year_tokens[consumed:]
    if not model_tokens:
        return None

    model = humanize_tokens(model_tokens)
    year_value = int(tokens[year_idx])

    rel_path = str(path.relative_to(base_dir))
    return CarRecord(path=rel_path, make=make, model=model, year=year_value)


def find_year_index(tokens: Sequence[str]) -> Optional[int]:
    for idx, token in enumerate(tokens):
        if YEAR_PATTERN.match(token):
            year = int(token)
            if 1950 <= year <= 2035:
                return idx
    return None


def humanize_tokens(tokens: Iterable[str]) -> str:
    return " ".join(humanize_token(token) for token in tokens)


def humanize_token(token: str) -> str:
    if token.isupper():
        return token
    if token.isdigit():
        return token
    if len(token) <= 3 and token.upper() == token:
        return token
    cleaned = token.replace("-", " ")
    parts = [part.capitalize() if part else "" for part in cleaned.split(" ")]
    return " ".join(parts).strip()

