from typing import List, Optional, Dict, Tuple

from actor_state import ActorState
from skill_state import SkillState
from weapon_type import WeaponType


def search_greedy(actor_state: ActorState, max_time: Optional[int], depth: Optional[int] = None) \
        -> (int, Dict[str, List[Tuple[str, int]]]):
    sorted_skills = sorted(
        actor_state.skill_states.values(),
        key=lambda skill: skill.score_per_cast_time,
        reverse=True)

    total_damage = 0

    best_rotation = []
    time = 1
    while time <= max_time:
        if depth is not None and len(best_rotation) >= depth:
            break
        next_skill: Optional[SkillState] = None
        for skill in sorted_skills:
            if actor_state.can_cast(skill.skill_key):
                next_skill = skill
                break

        time_delta, executed_skill = actor_state.simulate(next_skill.skill_key)
        if time_delta == 0:
            raise Exception(f"Error: skill {next_skill.skill_key} cannot be cast")

        time += time_delta
        if executed_skill == next_skill.skill_key:
            total_damage += next_skill.skill_simulation_data.total_damage
            best_rotation.append({"skill": next_skill.skill_key, "cast_time_ms": time})

    return total_damage, {"skill_casts": best_rotation}
