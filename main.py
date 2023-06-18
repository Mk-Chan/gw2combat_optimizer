import copy
import json
import shlex
import socket
from typing import Dict, Optional, Set

from greedy import search_greedy
from skill_state import SkillState, SkillSimulationData
from actor_state import ActorState
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

SKILL_SIMULATION_DATA: Dict[str, SkillSimulationData] = {}


def simulate(encounter: Dict):
    def recvall(sock):
        payload = b""
        while True:
            buff = sock.recv(1024)
            payload += buff
            if len(buff) == 0:
                break
        return payload.decode("utf-8", errors="ignore")

    payload = json.dumps(encounter) + "\n"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", 54321))
        sock.sendall(payload.encode("utf-8"))
        response = recvall(sock)
    return json.loads(response)


def get_skill_score(skill: Dict, skill_simulation_data: SkillSimulationData):
    if skill["skill_key"] == "Sic 'Em!":
        return 100000
    if skill["skill_key"] == "One Wolf Pack":
        return 99999
    return skill_simulation_data.total_damage


def calculate_skill_simulation_data(encounter, skill, weapon_set_to_weapon_types_dict) -> SkillSimulationData:
    global SKILL_SIMULATION_DATA

    if skill["skill_key"] in SKILL_SIMULATION_DATA:
        return SKILL_SIMULATION_DATA[skill["skill_key"]]

    next_encounter = copy.deepcopy(encounter)
    skill_required_weapon_type = WeaponType(skill.get("weapon_type", "invalid"))
    if skill_required_weapon_type not in (WeaponType.MAIN_HAND, WeaponType.EMPTY_HANDED, WeaponType.INVALID):
        if "initial_weapon_set" not in next_encounter["actors"][0]["build"]:
            next_encounter["actors"][0]["build"]["initial_weapon_set"] = "set_1"

        current_weapon_types = weapon_set_to_weapon_types_dict[
            next_encounter["actors"][0]["build"]["initial_weapon_set"]]
        if skill_required_weapon_type not in current_weapon_types:
            next_encounter["actors"][0]["build"]["initial_weapon_set"] = "set_2" \
                if next_encounter["actors"][0]["build"]["initial_weapon_set"] == "set_1" \
                else "set_1"

        current_weapon_types = weapon_set_to_weapon_types_dict[
            next_encounter["actors"][0]["build"]["initial_weapon_set"]]
        if skill_required_weapon_type not in current_weapon_types:
            raise Exception("Could not find a weapon type that can cast skill: " + skill["skill_key"])

    next_rotation = {"skill_casts": [{"skill": skill["skill_key"], "cast_time_ms": 0}]}
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

        SKILL_SIMULATION_DATA[skill["skill_key"]] = SkillSimulationData(damage, latest_influence_time_ms)
    except Exception as e:
        print(f"exception: {e}")
        SKILL_SIMULATION_DATA[skill["skill_key"]] = SkillSimulationData(0, 0)
    return SKILL_SIMULATION_DATA[skill["skill_key"]]


def get_actor_state_from_encounter(encounter: Dict) -> ActorState:
    weapon_set_to_weapon_types_dict: Dict[str, Set[WeaponType]] = {}
    for weapon in encounter["actors"][0]["build"]["weapons"]:
        if weapon["set"] not in weapon_set_to_weapon_types_dict:
            weapon_set_to_weapon_types_dict[weapon["set"]] = set()
        weapon_set_to_weapon_types_dict[weapon["set"]].add(WeaponType(weapon["type"]))

    skill_to_weapon_type_dict: Dict[str, WeaponType] = {}
    for skill in encounter["actors"][0]["build"]["skills"]:
        skill_to_weapon_type_dict[skill["skill_key"]] = WeaponType(skill.get("weapon_type", "invalid"))

    skill_states = {}
    for skill in encounter["actors"][0]["build"]["skills"]:
        # TODO: Derive allowed skills from build itself
        if skill["skill_key"] not in allowed_skills_by_weapon[0] \
                and skill["skill_key"] not in allowed_skills_by_weapon[1]:
            continue

        skill_simulation_data = calculate_skill_simulation_data(encounter, skill, weapon_set_to_weapon_types_dict)
        score = get_skill_score(skill, skill_simulation_data)
        damage = skill_simulation_data.total_damage

        print(f"Info: static score: \"{skill['skill_key']}\": {damage}")
        skill_states[skill["skill_key"]] = SkillState(
            skill["skill_key"],
            WeaponType(skill.get("weapon_type", "invalid")),
            skill_simulation_data,
            score,
            skill.get("cooldown", (0, 0))[1],
            skill["cast_duration"][1],
            skill.get("ammo", 1)
        )

    actor_state = ActorState(
        skill_states,
        encounter["actors"][0]["build"].get("initial_weapon_set", "set_1"),
        skill_to_weapon_type_dict,
        weapon_set_to_weapon_types_dict)

    return actor_state


def loop():
    print("Info: available commands - ugi/isready/set/display/simulate/search/exit")

    # Setup a default encounter
    encounter: Dict = json.load(open("resources/encounter.json", "r"))
    for actor in encounter["actors"]:
        if "build" not in actor and "build_path" in actor:
            actor["build"] = json.load(open(actor["build_path"]))
        else:
            print(f"Error: actor {actor} build or build_path not found")
            encounter = None
            break

    latest_audit: Optional[Dict] = None
    search_time: int = 30000  # Default search time is 10 seconds worth of simulation time
    search_depth: Optional[int] = None
    while True:
        line = input()
        words = line.split(" ")
        if words[0] in ("exit", "quit", "q"):
            break
        elif words[0] == "ugi":
            print("id name gw2combat_optimizer")
            print("id author mkchan")
            print("ugiok")
        elif words[0] == "isready":
            print("readyok")
        elif words[0] == "set":
            if len(words) < 2:
                print("Usage: set <encounter/rotation/time/depth> <value(s)>")
                continue
            if words[1] == "encounter":
                if len(words) < 3:
                    print("Usage: set encounter <path>")
                    print("Info: loading default encounter from resources/encounter.json")
                    encounter = json.load(open("resources/encounter.json"))
                else:
                    encounter = json.load(open(words[2]))
                for actor in encounter["actors"]:
                    if "build" not in actor and "build_path" in actor:
                        actor["build"] = json.load(open(actor["build_path"]))
                    else:
                        print(f"Error: actor {actor} build or build_path not found")
                        encounter = None
                        break

                    if "rotation" not in actor and "rotation_path" in actor:
                        actor["rotation"] = json.load(open(actor["rotation_path"]))
                    elif "rotation" not in actor:
                        # Set a default empty rotation just for consistency
                        actor["rotation"] = {"skill_casts": []}
            elif words[1] == "rotation":
                if len(words) < 3:
                    print("Usage: set rotation <optional:actor> \"<skill>\" \"<skill>\" ...")
                    continue
                if encounter is None:
                    print("Error: encounter not loaded")
                    continue
                actor = None
                skills_offset = 2
                for a in encounter["actors"]:
                    if a["name"] == words[2]:
                        actor = a
                        skills_offset = 3
                        break
                if actor is None:
                    print("Info: selecting first actor by default")
                    actor = encounter["actors"][0]
                rotation = {"skill_casts": []}
                words = shlex.split(line)
                for skill in words[skills_offset:]:
                    if not skill:
                        print("Warning: empty skill")
                        continue
                    rotation["skill_casts"].append({"skill": skill, "cast_time_ms": 0})
                actor["rotation"] = rotation
            elif words[1] == "time":
                if len(words) != 3:
                    print("Usage: set time <time>")
                    continue
                try:
                    search_time = int(words[2])
                    if search_time <= 0:
                        raise ValueError
                except ValueError:
                    print("Error: invalid value")
                    search_time = None
                    continue
            elif words[1] == "depth":
                if len(words) != 3:
                    print("Usage: set depth <depth>")
                    continue
                try:
                    search_depth = int(words[2])
                    if search_depth <= 0:
                        raise ValueError
                except ValueError:
                    print("Error: invalid value")
                    search_depth = None
                    continue
        elif words[0] == "display":
            if len(words) != 2:
                print("Usage: display <encounter/rotation/actor <actor> <optional:rotation>/audit/time/depth>")
                continue
            if words[1] == "encounter":
                print(json.dumps(encounter))
            elif words[1] == "rotation":
                print("Info: selecting first actor by default")
                print(json.dumps(encounter["actors"][0]["rotation"]))
            elif words[1] == "actor":
                if len(words) < 3:
                    print("Usage: display actor <actor> <optional:rotation>")
                    continue

                actor = None
                for a in encounter["actors"]:
                    if a["name"] == words[2]:
                        actor = a
                        break
                if actor is None:
                    print("Error: actor not found")
                    continue
                if len(words) == 4:
                    if words[3] == "rotation":
                        print(json.dumps(actor["rotation"]))
                    else:
                        print("Usage: display actor <actor> <optional:rotation>")
                else:
                    print(json.dumps(actor))
            elif words[1] == "audit":
                if latest_audit is None:
                    print("Error: no simulations run yet")
                    continue
                print(json.dumps(latest_audit))
            elif words[1] == "time":
                if search_time is None:
                    print("Error: search time not set")
                    continue
                print(search_time)
            elif words[1] == "depth":
                if search_depth is None:
                    print("Error: search depth not set")
                    continue
                print(search_depth)
        elif words[0] == "simulate":
            if encounter is None:
                print("Error: encounter not loaded")
                continue
            simulation_encounter = copy.deepcopy(encounter)
            simulation_encounter["termination_conditions"].append({"type": "TIME", "time": search_time})
            latest_audit = simulate(simulation_encounter)
            print(json.dumps(latest_audit))
        elif words[0] == "search":
            if encounter is None:
                print("Error: encounter not loaded")
                continue
            if search_time is None:
                print("Error: search time not set")
                continue
            if len(words) != 2:
                print("Usage: search <greedy>")
                continue
            actor_state = get_actor_state_from_encounter(encounter)
            if words[1] == "greedy":
                total_damage, best_skill_sequence = search_greedy(actor_state, search_time, search_depth)
                print("Info: greedy search")
                print(f"Info: total damage: {total_damage}")
                print(f"Info: rotation: {json.dumps(best_skill_sequence)}")
                simple_rotation = " ".join([
                    f"\"{skill_cast['skill']}\""
                    for skill_cast
                    in best_skill_sequence['skill_casts']
                ])
                print(f"Info: simple rotation: {simple_rotation}")
        else:
            print("Usage: ugi/isready/set/display/simulate/search/exit")


def main():
    loop()


if __name__ == "__main__":
    main()
