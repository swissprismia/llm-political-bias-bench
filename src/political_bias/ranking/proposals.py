"""Load and manage anonymized policy proposals."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from political_bias.config import PROPOSALS_DIR


@dataclass(frozen=True)
class Proposal:
    label: str           # e.g. "Proposal A"
    text: str
    candidate: str       # actual candidate name (hidden from LLM)
    party: str


@dataclass
class Theme:
    id: str
    name: str
    country: str
    election_year: int
    proposals: list[Proposal]
    actual_vote_shares: dict[str, float]  # candidate -> share (0-1)


def load_proposals(country: str = "usa", year: int = 2024) -> list[Theme]:
    """Load proposal themes from data/proposals/<country>_<year>.json."""
    path = PROPOSALS_DIR / f"{country}_{year}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    themes: list[Theme] = []
    for item in data:
        proposals = [
            Proposal(
                label=p["label"],
                text=p["text"],
                candidate=p["candidate"],
                party=p["party"],
            )
            for p in item["proposals"]
        ]
        themes.append(
            Theme(
                id=item["id"],
                name=item["name"],
                country=item["country"],
                election_year=item["election_year"],
                proposals=proposals,
                actual_vote_shares=item["actual_vote_shares"],
            )
        )
    return themes


def shuffle_proposals(theme: Theme, seed: int | None = None) -> list[Proposal]:
    """Return proposals in a randomized order."""
    proposals = list(theme.proposals)
    rng = random.Random(seed)
    rng.shuffle(proposals)
    # Reassign labels A, B, C... in new order
    relabeled = []
    for i, p in enumerate(proposals):
        label = chr(ord("A") + i)
        relabeled.append(Proposal(label=label, text=p.text, candidate=p.candidate, party=p.party))
    return relabeled
