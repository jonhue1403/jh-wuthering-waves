"""Non-authorizing acquisition-method references for screenshot materials.

These methods are community/guide descriptions, not verified in-game item IDs,
actual drops, open challenge availability, resource budgets, route profiles,
or approvals to interact with the game. Never feed them into an executor.
"""
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


class SourceKind(str, Enum):
    MOB_DROP = "MOB_DROP"
    FORGERY = "FORGERY_CHALLENGE"
    SIMULATION = "SIMULATION_TRAINING"
    TACET_FIELD = "TACET_FIELD"
    SYNTHESIS = "SYNTHESIS"
    EXPLORATION = "EXPLORATION_OR_QUEST"
    REWARD = "EVENT_OR_EXCHANGE"
    SUBSCRIPTION = "HISTORICAL_SUBSCRIPTION"


@dataclass(frozen=True)
class AcquisitionReference:
    material_id: str
    kind: SourceKind
    label: str
    reference_url: str
    requires_fresh_check: bool = True

    def __post_init__(self):
        if not self.material_id or not self.label or not isinstance(self.kind, SourceKind):
            raise ValueError("Invalid material acquisition reference")
        url = urlsplit(self.reference_url)
        if (url.scheme != "https" or not url.hostname
                or url.username is not None or url.password is not None
                or any(ch.isspace() for ch in self.reference_url)):
            raise ValueError("Acquisition source must have an HTTPS citation")


# For each material: (reference URL, [(kind, UI-facing method label), ...]).
# Links are selected from material-specific community/guide descriptions.
# Availability, item identity, domain names and spend requirements must be
# independently re-observed in the player's installed game version.
_REFERENCE_ROWS = {
    "premium-tuner": (
        "https://wutheringwaves.fandom.com/wiki/Premium_Tuner",
        ((SourceKind.TACET_FIELD, "Tacet Field reward"),
         (SourceKind.SYNTHESIS, "Synthesis"),
         (SourceKind.EXPLORATION, "Exploration reward")),
    ),
    "premium-sealed-tube": (
        "https://wutheringwaves.fandom.com/wiki/Premium_Sealed_Tube",
        ((SourceKind.TACET_FIELD, "Tacet Field reward"),
         (SourceKind.EXPLORATION, "Exploration reward")),
    ),
    "premium-resonance-potion": (
        "https://wutheringwaves.fandom.com/wiki/Premium_Resonance_Potion",
        ((SourceKind.SIMULATION, "Simulation Training reward"),
         (SourceKind.EXPLORATION, "Exploration / quest reward")),
    ),
    "heterized-metallic-drip": (
        "https://wutheringwaves.fandom.com/wiki/Heterized_Metallic_Drip",
        ((SourceKind.FORGERY, "Forgery Challenge: Flaming Remnants / Garden of Salvation"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "mysterious-code": (
        "https://wutheringwaves.fandom.com/wiki/Mysterious_Code",
        ((SourceKind.EXPLORATION, "Casket Delivery / quest reward (not a repeatable mob route)"),),
    ),
    "ff-whisperin-core": (
        "https://wutheringwaves.fandom.com/wiki/FF_Whisperin_Core",
        ((SourceKind.MOB_DROP, "Whisperin enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "ff-howler-core": (
        "https://wutheringwaves.fandom.com/wiki/FF_Howler_Core",
        ((SourceKind.MOB_DROP, "Howler enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "tailored-ring": (
        "https://wutheringwaves.fandom.com/wiki/Tailored_Ring",
        ((SourceKind.MOB_DROP, "Exile enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "mask-of-insanity": (
        "https://wutheringwaves.fandom.com/wiki/Mask_of_Insanity",
        ((SourceKind.MOB_DROP, "Fractsidus enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "flawless-phlogiston": (
        "https://wutheringwaves.fandom.com/wiki/Flawless_Phlogiston",
        ((SourceKind.FORGERY, "Forgery Challenge: Marigold Woods / Abyss of Confession"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "presto-helix": (
        "https://wutheringwaves.fandom.com/wiki/Presto_Helix",
        ((SourceKind.FORGERY, "Forgery Challenge: Misty Forest / Abyss of Initiation"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "waveworn-residue-239": (
        "https://wutheringwaves.fandom.com/wiki/Waveworn_Residue_239",
        ((SourceKind.FORGERY, "Forgery Challenge: Eroded Ruins / Garden of Adoration"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "cadence-blossom": (
        "https://wutheringwaves.fandom.com/wiki/Cadence_Blossom",
        ((SourceKind.FORGERY, "Forgery Challenge: Moonlit Groves / Abyss of Sacrifice"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "premium-energy-core": (
        "https://wutheringwaves.fandom.com/wiki/Premium_Energy_Core",
        ((SourceKind.SIMULATION, "Simulation Training reward"),
         (SourceKind.EXPLORATION, "Exploration / quest reward")),
    ),
    "ff-tidal-residuum": (
        "https://wutheringwaves.fandom.com/wiki/FF_Tidal_Residuum",
        ((SourceKind.MOB_DROP, "Dark Tide-affected Tacet Discords"),
         (SourceKind.SYNTHESIS, "Synthesis"),
         (SourceKind.FORGERY, "Rinascita Forgery Challenge")),
    ),
    "ff-polygon-core": (
        "https://wutheringwaves.fandom.com/wiki/FF_Polygon_Core",
        ((SourceKind.MOB_DROP, "Clamoring / Tranquilite enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "echo-modifier": (
        "https://wutheringwaves.fandom.com/wiki/Modifier",
        ((SourceKind.REWARD, "Events / Pioneer Podcast / item exchange; confirm exact item label"),),
    ),
    "ff-exoswarm-core": (
        "https://wutheringwaves.fandom.com/wiki/FF_Exoswarm_Core",
        ((SourceKind.MOB_DROP, "Exoswarm enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "reverb-combustor": (
        "https://wutheringwaves.fandom.com/wiki/Reverb_Combustor",
        ((SourceKind.FORGERY, "Forgery Challenge: Lesson in Embers"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "ff-mech-core": (
        "https://wutheringwaves.fandom.com/wiki/FF_Mech_Core",
        ((SourceKind.MOB_DROP, "Clamorling Tacet Discords in Lahai-Roi"),
         (SourceKind.SYNTHESIS, "Synthesis"),
         (SourceKind.FORGERY, "Forgery Challenge")),
    ),
    "intact-exoswarm-pendant": (
        "https://wutheringwaves.fandom.com/wiki/Intact_Exoswarm_Pendant",
        ((SourceKind.MOB_DROP, "Roya Outcast enemies"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "layered-wing-polarizer": (
        "https://wutheringwaves.fandom.com/wiki/Layered_Wing_Polarizer",
        ((SourceKind.FORGERY, "Forgery Challenge: Fallen Sanctum"),
         (SourceKind.SYNTHESIS, "Synthesis conversion")),
    ),
    "melodic-string": (
        "https://wutheringwaves.fandom.com/wiki/Melodic_String",
        ((SourceKind.FORGERY, "Forgery Challenge: Lesson in Sunset"),
         (SourceKind.SYNTHESIS, "Synthesis conversion")),
    ),
    "ff-carved-crystal": (
        "https://wutheringwaves.fandom.com/wiki/FF_Carved_Crystal",
        ((SourceKind.FORGERY, "Forgery Challenge: Stricken Sanctum"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "ff-waveworn-shard": (
        "https://wutheringwaves.fandom.com/wiki/FF_Waveworn_Shard",
        ((SourceKind.FORGERY, "Forgery Challenge: Lesson in Void"),
         (SourceKind.SYNTHESIS, "Synthesis")),
    ),
    "transducer": (
        "https://senseos.gg/guides/wuthering-waves/wuthering-waves-echoes/",
        ((SourceKind.SUBSCRIPTION, "Historical limited-time subscription; availability unconfirmed"),),
    ),
    "ff-autopuppet-kernel": (
        "https://wuthering.th.gl/db/inventory/item_41100094",
        ((SourceKind.MOB_DROP, "Autopuppet enemies"),
         (SourceKind.SYNTHESIS, "Purification / conversion")),
    ),
}


def documented_acquisition(material_id: str) -> dict:
    """Operator-facing, path-free community references; NEVER executable."""
    if type(material_id) is not str or material_id not in _REFERENCE_ROWS:
        raise ValueError("Unknown material reference")
    url, methods = _REFERENCE_ROWS[material_id]
    entries = tuple(
        AcquisitionReference(material_id, kind, label, url)
        for kind, label in methods
    )
    return {
        "status": "REFERENCE_ONLY",
        "methods": [
            {"kind": entry.kind.value, "label": entry.label,
             "reference_url": entry.reference_url,
             "qualification": "NOT_OBSERVED_CURRENT_GAME"}
            for entry in entries
        ],
        "possible_mob_source": any(entry.kind == SourceKind.MOB_DROP
                                   for entry in entries),
        "executable_source_ids": [],
        "can_start": False,
        "requires_game_verification": True,
        "note": "Community references only. Confirm current item identity, "
                "reward source, limits and actual inventory gain in-game.",
    }
