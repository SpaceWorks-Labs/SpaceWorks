"""Default submission-stage presets (#178, #179, #180 S10). Data only: a preset never creates money settings.

The organiser picks a preset in the stage editor, then edits, adds, removes and reorders stages and
sets every date. Shortlist gates are optional per stage in every preset. "Single submission" is
today's behaviour and the backfill of every existing event.
"""

_PROBLEM = {"key": "problem_statement", "label": "Problem statement", "type": "long_text", "required": True,
            "help": "What problem are you solving, and for whom?", "visible_to": "staff_and_judges"}
_IDEA = {"name": "Idea", "description": "Describe the idea. A deck or sketch is welcome but optional.",
         "content_mode": "files_and_links", "custom_fields": [_PROBLEM]}


def _stage(name, description="", **rules):
    return {"name": name, "description": description, "content_mode": "files_and_links", "required_link_kinds": [],
            "min_files": 0, "max_files": None, "max_links": None, "accepted_families": [], "max_bytes_per_file": None,
            "video_hosts": [], "custom_fields": [], "requires_previous": False, "shortlist_after": False,
            "shortlist_label": "", "late_policy": "reject", "resubmission": "until_deadline", "grace_minutes": 0,
            **rules}


PRESETS = (
    {"key": "single", "name": "Single submission", "requires_admission": False,
     "description": "One submission window with files and links. Today's behaviour.",
     "stages": [_stage("Submission")]},
    {"key": "idea_final", "name": "Idea → Final", "requires_admission": False,
     "description": "Teams share an idea first, then submit the finished project.",
     "stages": [_stage(**_IDEA),
                _stage("Final", "The finished project: code, files and a demo.", requires_previous=True)]},
    {"key": "idea_prototype_final", "name": "Idea → Prototype → Final", "requires_admission": False,
     "description": "An idea, a working prototype, then the final project.",
     "stages": [_stage(**_IDEA),
                _stage("Prototype", "A first working version. Link the repository.", required_link_kinds=["repo"],
                       requires_previous=True),
                _stage("Final", "The finished project: code, files and a demo.", requires_previous=True)]},
    {"key": "hardware_build", "name": "Hardware build: Proposal → Build log → Demo", "requires_admission": False,
     "description": "A proposal, a build log with photos and design files, then a demo video.",
     "stages": [_stage("Proposal", "What you will build, and the parts you need.",
                       custom_fields=[{**_PROBLEM, "key": "build_plan", "label": "Build plan",
                                       "help": "What will you build, and how?"}]),
                _stage("Build log", "Photos, CAD, PCB and firmware as you build.", content_mode="files_only", min_files=1,
                       accepted_families=["images", "video", "hardware-cad", "hardware-pcb", "firmware", "source",
                                          "fab-2d", "fab-3dprint", "fab-cnc"], requires_previous=True),
                _stage("Demo", "A demo video of the working build.", required_link_kinds=["video"],
                       requires_previous=True)]},
    {"key": "design_sprint", "name": "Design sprint: Brief → Concept → Final", "requires_admission": False,
     "description": "Respond to the brief, share a concept, then deliver the final design.",
     "stages": [_stage("Brief", "Your reading of the brief.", custom_fields=[
                    {**_PROBLEM, "key": "brief_response", "label": "Brief response", "help": "How do you read the brief?"}]),
                _stage("Concept", "Sketches, moodboards or a short deck.", content_mode="files_only", min_files=1,
                       accepted_families=["images", "deck"], requires_previous=True),
                _stage("Final", "The final design files and a presentation deck.", requires_previous=True)]},
    {"key": "full_pipeline", "name": "Full pipeline: Application → Shortlist → Idea → Shortlist → Prototype → Finalists → Final",
     "requires_admission": True,
     "description": "Teams apply and are reviewed first (applications), then an idea round with a shortlist, "
                    "a prototype round that picks finalists, and the final.",
     "stages": [_stage(**{**_IDEA, "shortlist_after": True, "shortlist_label": "Shortlist"}),
                _stage("Prototype", "A first working version. Link the repository.", required_link_kinds=["repo"],
                       shortlist_after=True, shortlist_label="Finalists"),
                _stage("Final", "The finished project, presented to the judges.")]},
    {"key": "ideathon", "name": "Ideathon: Idea → Deck → Pitch", "requires_admission": False,
     "description": "An idea, a pitch deck, then a live pitch with nothing to upload.",
     "stages": [_stage(**_IDEA),
                _stage("Deck", "Your pitch deck.", content_mode="files_only", min_files=1, max_files=1,
                       accepted_families=["deck"], requires_previous=True),
                _stage("Pitch", "The live pitch. Nothing to upload.", content_mode="presentation",
                       requires_previous=True)]},
    {"key": "case_competition", "name": "Case competition: Deck → Final pitch", "requires_admission": False,
     "description": "A case deck picks the finalists, who pitch live.",
     "stages": [_stage("Deck", "Your case deck.", content_mode="files_only", min_files=1, max_files=1,
                       accepted_families=["deck"], shortlist_after=True, shortlist_label="Finalists"),
                _stage("Final pitch", "The live pitch. Nothing to upload.", content_mode="presentation")]},
)

PRESET_KEYS = frozenset(row["key"] for row in PRESETS)


def default_stage(config, *, context=None):
    """The "Single submission" stage for an event's current window (the #178 default and backfill)."""
    if config is None:
        return {**_stage("Submission"), "opens_at": None,
                "deadline": context.deadline if context is not None else None,
                "grace_minutes": (context.grace_seconds // 60) if context is not None else 0,
                "late_policy": context.late_policy if context is not None else "reject"}
    return {**_stage("Submission"), "opens_at": config.submission_opens_at, "deadline": config.submission_deadline,
            "grace_minutes": config.submission_grace_minutes, "late_policy": config.late_policy}
