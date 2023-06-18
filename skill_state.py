import dataclasses
from typing import Dict

from weapon_type import WeaponType


@dataclasses.dataclass
class SkillSimulationData:
    total_damage: int
    time_for_full_damage: int


class SkillState:
    def __init__(self,
                 skill_key: str,
                 weapon_type: WeaponType,
                 skill_simulation_data: SkillSimulationData,
                 score: int,
                 max_cooldown: int,
                 cast_duration: int,
                 max_ammo: int):
        self.skill_key = skill_key
        self.weapon_type = weapon_type
        self.skill_simulation_data = skill_simulation_data
        self.score = score
        self.max_cooldown = max_cooldown
        self.cast_duration = cast_duration
        self.max_ammo = max_ammo
        self.total_influence_time = cast_duration + max_cooldown + skill_simulation_data.time_for_full_damage
        self.score_per_cast_time = (score / cast_duration) if cast_duration > 0.0 else score
        self.current_cooldown = 0
        self.current_ammo = max_ammo

    def can_cast(self, current_weapon_type):
        return self.current_ammo > 0 and (
                self.weapon_type == current_weapon_type or
                self.weapon_type == WeaponType.MAIN_HAND or
                self.weapon_type == WeaponType.EMPTY_HANDED or
                self.weapon_type == WeaponType.INVALID
        )

    def cast(self):
        if self.current_ammo == self.max_ammo:
            self.current_cooldown = self.max_cooldown
        self.current_ammo -= 1

    def tick_cooldown(self, delta=1):
        if self.current_cooldown > 0:
            self.current_cooldown = max(self.current_cooldown - delta, 0)
        if self.current_cooldown == 0 and self.current_ammo < self.max_ammo:
            self.current_ammo += 1


@dataclasses.dataclass
class SkillStates(object):
    skill_states: Dict[str, SkillState]
