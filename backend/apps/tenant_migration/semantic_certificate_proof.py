"""Typed contribution proof IDs; versions and original rendered PDF stay frozen."""
from copy import deepcopy


def remap_contribution_proof(layout, map_id):
    if not isinstance(layout, dict):
        raise ValueError("Invalid certificate layout snapshot.")
    value = deepcopy(layout)
    if "contribution_proof" not in value:
        return value
    proof = value["contribution_proof"]
    if not isinstance(proof, dict) or type(proof.get("version")) is not int or proof["version"] != 1:
        raise ValueError("Unknown certificate contribution proof.")

    def identity(label, pk):
        if type(pk) is not int or pk <= 0:
            raise ValueError("Invalid certificate work reference.")
        return map_id("events." + label, pk)

    def pairs(label, entries):
        if not isinstance(entries, list):
            raise ValueError("Invalid certificate work proof.")
        result = []
        for item in entries:
            if (not isinstance(item, list) or len(item) != 2
                    or type(item[1]) is not int or item[1] < 1):
                raise ValueError("Invalid certificate work revision.")
            result.append([identity(label, item[0]), item[1]])
        return result

    proof["role_assignment_id"] = identity("EventRoleAssignment", proof.get("role_assignment_id"))
    if proof.get("role") == "volunteer":
        proof["evidence"] = pairs("EventContributionHours", proof.get("evidence"))
    elif proof.get("role") == "mentor":
        entries = proof.get("evidence")
        if not isinstance(entries, list):
            raise ValueError("Invalid mentor work proof.")
        proof["evidence"] = [identity("MentorRoundCheckin", pk) for pk in entries]
    elif proof.get("role") == "judge":
        proof["scores"] = pairs("JudgeScore", proof.get("scores"))
        proof["ballots"] = pairs("JudgeRankingBallot", proof.get("ballots"))
    else:
        raise ValueError("Unknown contribution proof role.")
    return value
