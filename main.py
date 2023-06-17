import copy
import json
import socket
from typing import Dict, List

from skill_properties import SkillProperties
from skill_state import SkillState, SkillStates
from weapon_type import WeaponType

allowed_skills_by_weapon = ((
                                "Barrage",
                                "Frost Trap",
                                "Sic 'Em!",
                                "Point-Blank Shot",
                                "One Wolf Pack",
                                "Frenzied Attack",
                                "Worldly Impact",
                                "Rapid Fire",
                                "Long Range Shot",
                                "AFK 40ms",
                            ), (
                                "Splitblade",
                                "Frost Trap",
                                "Path of Scars",
                                "Winter's Bite",
                                "Frenzied Attack",
                                "Worldly Impact",
                                "Whirling Defense",
                                "Ricochet",
                                "One Wolf Pack",
                                "Sic 'Em!",
                                "AFK 40ms",
                            ))


def recvall(sock):
    payload = b""
    while True:
        buff = sock.recv(1024)
        payload += buff
        if len(buff) == 0:
            break
    return payload.decode("utf-8", errors="ignore")


def simulate(encounter: Dict):
    payload = json.dumps(encounter) + "\n"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", 54321))
        sock.sendall(payload.encode("utf-8"))
        response = recvall(sock)
    return json.loads(response)


def calculate_skill_properties(encounter, skill):
    next_encounter = copy.deepcopy(encounter)
    next_rotation = {"skill_casts": []}
    if WeaponType(skill.get("weapon_type", "invalid")) == WeaponType.AXE:
        for weapon in next_encounter["actors"][0]["build"]["weapons"]:
            if weapon["set"] == "set_1":
                weapon["set"] = "set_2"
            else:
                weapon["set"] = "set_1"

    next_rotation["skill_casts"].append({"skill": skill["skill_key"], "cast_time_ms": 0})
    next_encounter["actors"][0]["rotation"] = next_rotation
    next_encounter["termination_conditions"].append({
        "type": "TIME",
        "actor": "lb-slb",
        "time": 30000
    })

    try:
        audit = simulate(next_encounter)
        damage = 0
        latest_influence_time_ms = 0
        for tick_event in audit["tick_events"]:
            if tick_event["actor"] == "golem":
                damage += tick_event["event"]["damage"] if tick_event["event"]["event_type"] == "damage_event" else 0

        for tick_event in reversed(audit["tick_events"]):
            if (tick_event["actor"] == "golem" and
                    tick_event["event"]["event_type"] == "damage_event" and
                    tick_event["event"]["source_actor"] == "lb-slb" and
                    tick_event["event"]["source_skill"] == skill["skill_key"]):
                latest_influence_time_ms = int(tick_event["time_ms"])
                break

        return SkillProperties(damage, latest_influence_time_ms)
    except Exception as e:
        print(f"exception: {e}")
        return SkillProperties(0, 0)


def get_skill_score(skill: Dict, skill_properties: SkillProperties):
    if skill["skill_key"] == "Sic 'Em!":
        return 100000
    if skill["skill_key"] == "One Wolf Pack":
        return 99999
    return skill_properties.total_damage


def get_relevant_skills_from_encounter(encounter: Dict) -> SkillStates:
    skills = {}
    for skill in encounter["actors"][0]["build"]["skills"]:
        if skill["skill_key"] not in allowed_skills_by_weapon[0] \
                and skill["skill_key"] not in allowed_skills_by_weapon[1]:
            continue
        skill_properties = calculate_skill_properties(encounter, skill)
        score = get_skill_score(skill, skill_properties)
        damage = skill_properties.total_damage

        print(f"{skill['skill_key']}: {damage}")
        skills[skill["skill_key"]] = SkillState(
            skill["skill_key"],
            WeaponType(skill.get("weapon_type", "invalid")),
            score,
            damage,
            skill.get("cooldown", (0, 0))[1],
            skill["cast_duration"][1],
            skill_properties.time_for_full_damage,
            skill.get("ammo", 1)
        )

    return SkillStates(skills)


def maximize_damage(skill_states: SkillStates, max_time) -> (int, List[str]):
    sorted_skills = sorted(
        skill_states.skill_states.values(),
        key=lambda skill: skill.score_per_cast_time,
        reverse=True)

    total_damage = 0

    current_weapon_type = WeaponType.LONGBOW
    best_skill_sequence = []
    time = 0
    while time < max_time:
        castable_skills = []
        for skill in sorted_skills:
            if skill.can_cast(current_weapon_type):
                castable_skills.append(skill)

        if not castable_skills:
            time += 1
            for skill in sorted_skills:
                skill.tick_cooldown()
            continue

        best_skill = castable_skills[0]
        best_skill.cast()
        if best_skill.skill_key == "Weapon Swap":
            current_weapon_type = WeaponType.LONGBOW if current_weapon_type == WeaponType.AXE else WeaponType.AXE

        total_damage += best_skill.total_damage
        best_skill_sequence.append(best_skill.skill_key)
        time += best_skill.cast_duration
        for skill in sorted_skills:
            skill.tick_cooldown(best_skill.cast_duration)

    return total_damage, best_skill_sequence


def main():
    encounter = json.load(open("resources/encounter.json"))
    for actor in encounter["actors"]:
        actor["build"] = json.load(open(actor["build_path"]))
    skill_states = get_relevant_skills_from_encounter(encounter)
    total_damage, best_skill_sequence = maximize_damage(skill_states, 30000)
    print("--------")
    print(f"total damage: {total_damage}")
    print(f"best skill sequence: {best_skill_sequence}")


if __name__ == "__main__":
    main()
