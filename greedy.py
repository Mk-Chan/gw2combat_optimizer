from typing import List

from skill_state import SkillStates
from weapon_type import WeaponType


def search_greedy(skill_states: SkillStates, max_time) -> (int, List[str]):
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

        total_damage += best_skill.skill_simulation_data.total_damage
        best_skill_sequence.append(best_skill.skill_key)
        time += best_skill.cast_duration
        for skill in sorted_skills:
            skill.tick_cooldown(best_skill.cast_duration)

    return total_damage, best_skill_sequence
