#!/usr/bin/env python3

from __future__ import annotations

import argparse
import secrets
import random


ADJECTIVES = [
    "ancient",
    "breezy",
    "brisk",
    "calm",
    "clever",
    "cool",
    "crisp",
    "curious",
    "daring",
    "eager",
    "elegant",
    "gentle",
    "happy",
    "hazy",
    "icy",
    "jolly",
    "kind",
    "lively",
    "merry",
    "mighty",
    "nimble",
    "playful",
    "quiet",
    "rapid",
    "shiny",
    "smooth",
    "spry",
    "steady",
    "tender",
    "vivid",
    "woolly",
    "zesty",
]

MIDDLES = [
    "beaming",
    "cooking",
    "drifting",
    "finding",
    "forging",
    "gliding",
    "juggling",
    "mapping",
    "plotting",
    "skipping",
    "spinning",
    "swimming",
    "twirling",
    "weaving",
    "wishing",
    "wobbling",
]

NOUNS = [
    "badger",
    "canyon",
    "journal",
    "kettle",
    "paddle",
    "plum",
    "porcupine",
    "puddle",
    "quilt",
    "rivest",
    "scroll",
    "snail",
    "treasure",
    "unicorn",
    "wave",
    "zebra",
]


def generate_slug(rng: random.Random) -> str:
    return "-".join(
        [
            rng.choice(ADJECTIVES),
            rng.choice(MIDDLES),
            rng.choice(NOUNS),
        ]
    )


def generate_artifact_id(rng: random.Random) -> str:
    return f"{generate_slug(rng)}-{secrets.token_hex(3)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate artifact ID")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    print(generate_artifact_id(rng))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
