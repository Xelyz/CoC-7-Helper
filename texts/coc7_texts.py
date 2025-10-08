"""
存放各种描述文本，供命令引用。
"""

from __future__ import annotations

TEMP_INSANITY_D10: dict[int, dict[str, str]] = {
    1: {
        "name": "Flee in Panic",
        "desc": (
            "The investigator flees in blind panic for 1d10 rounds,"
            " avoiding perceived threats and seeking immediate escape."
        ),
    },
    2: {
        "name": "Paralysis",
        "desc": (
            "The investigator is rooted to the spot, unable to act due to"
            " overwhelming terror, for 1d10 rounds."
        ),
    },
    3: {
        "name": "Violent Outburst",
        "desc": (
            "An uncontrolled surge of aggression: the investigator lashes out"
            " at nearby targets (friend or foe) for 1d10 rounds."
        ),
    },
    4: {
        "name": "Mania",
        "desc": (
            "A temporary, irrational fixation or euphoric mania grips the investigator"
            " for 1d10 rounds (e.g., pyromania, kleptomania, or obsessive chanting)."
        ),
    },
    5: {
        "name": "Phobia",
        "desc": (
            "A sudden phobic reaction to a nearby stimulus strikes for 1d10 rounds"
            " (e.g., fear of darkness, blood, confined spaces)."
        ),
    },
    6: {
        "name": "Hysteria",
        "desc": (
            "Fits of uncontrollable weeping or hysterical laughter seize the investigator"
            " for 1d10 rounds, hindering coherent action."
        ),
    },
    7: {
        "name": "Amnesia",
        "desc": (
            "Transient memory loss (1d10 rounds): the investigator cannot recall recent"
            " events or even their own identity."
        ),
    },
    8: {
        "name": "Psychosomatic Impairment",
        "desc": (
            "A functional deficit manifests (e.g., blindness, deafness, or muteness)"
            " for 1d10 rounds without physical cause."
        ),
    },
    9: {
        "name": "Hallucinations",
        "desc": (
            "Disturbing visions or voices assail the investigator for 1d10 rounds,"
            " making it difficult to distinguish reality."
        ),
    },
    10: {
        "name": "Catatonia",
        "desc": (
            "The investigator withdraws into a non-responsive state for 1d10 rounds,"
            " barely reacting to external stimuli."
        ),
    },
}


