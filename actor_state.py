import dataclasses
from typing import Dict, Set, Optional

from skill_state import SkillState
from weapon_type import WeaponType


@dataclasses.dataclass
class ActorState(object):
    skill_states: Dict[str, SkillState]
    current_weapon_set: str
    skill_to_weapon_type_dict: Dict[str, WeaponType]
    weapon_set_to_weapon_types_dict: Dict[str, Set[WeaponType]]

    def can_cast(self, skill_key: str) -> bool:
        skill_required_weapon_type = self.skill_to_weapon_type_dict[skill_key]
        current_weapon_types = self.weapon_set_to_weapon_types_dict[self.current_weapon_set]
        return self.skill_states[skill_key].current_ammo > 0 and (
                skill_required_weapon_type == WeaponType.MAIN_HAND or
                skill_required_weapon_type == WeaponType.EMPTY_HANDED or
                skill_required_weapon_type == WeaponType.INVALID or
                skill_required_weapon_type in current_weapon_types
        )

    def cast(self, skill_key: str):
        skill_state = self.skill_states[skill_key]
        if skill_state.current_ammo == skill_state.max_ammo:
            skill_state.current_cooldown = skill_state.max_cooldown
        skill_state.current_ammo -= 1

        if skill_key == "Weapon Swap":
            self.current_weapon_set = "set_2" \
                if self.current_weapon_set == "set_1" \
                else "set_1"

    def tick_cooldown(self, delta=1):
        for skill_state in self.skill_states.values():
            if skill_state.current_cooldown > 0:
                skill_state.current_cooldown = max(skill_state.current_cooldown - delta, 0)
            if skill_state.current_cooldown == 0 and skill_state.current_ammo < skill_state.max_ammo:
                skill_state.current_ammo += 1

    def simulate(self, next_skill: Optional[str]) -> (int, Optional[str]):
        """

        :param next_skill:
        :return: time_delta, executed_skill
        """
        if next_skill is None:
            self.tick_cooldown()
            return 1, None

        if not self.can_cast(next_skill):
            return 0, None

        self.cast(next_skill)

        time_delta = max(1, self.skill_states[next_skill].cast_duration)
        self.tick_cooldown(time_delta)
        return time_delta, next_skill
