"""Strict fire arguments and percentile bonus/penalty rolls."""
import random
import re
import unicodedata
from dataclasses import dataclass

FIRE_HELP = (
    '.fire [normal/accuracy/recoil] [技能值] [+pN/+bN]：三次手枪检定；'
    '默认 accuracy（1/1/1 惩罚骰），normal 为 0/0/0，recoil 为 0/1/2。'
    '首个 p1/p2 兼容旧模式 accuracy/recoil；自定义修正推荐写 +pN（增加惩罚）'
    '或 +bN（增加奖励），每项 0～10 个，可叠加并相抵。'
    '例如 .fire recoil 60 +b1 → 1奖励/无/1惩罚；.fire normal 5 +p2 → 每发2惩罚。'
    '技能值 0～999；省略时读取人物卡手枪技能，无记录默认20。只检定，不计算伤害。'
)
MODES = {'normal': (0, 0, 0), 'accuracy': (1, 1, 1), 'recoil': (0, 1, 2)}


@dataclass(frozen=True)
class FireRequest:
    mode: str
    skill: int | None
    penalties: tuple[int, ...]


def parse_fire_args(text: str) -> FireRequest:
    tokens = unicodedata.normalize('NFKC', text).lower().split()
    mode = 'accuracy'
    if tokens and tokens[0] in ('p1', 'p2', *MODES):
        first = tokens.pop(0)
        mode = {'p1': 'accuracy', 'p2': 'recoil'}.get(first, first)
    skill = None
    adjustment = 0
    total = 0
    for token in tokens:
        modifier = re.fullmatch(r'\+?([pb])(\d+)', token)
        if modifier:
            count = int(modifier[2])
            total += count
            if count > 10 or total > 20:
                raise ValueError('每项奖励/惩罚骰最多10个，修正骰总数最多20个。')
            adjustment += count if modifier[1] == 'p' else -count
        elif re.fullmatch(r'\d{1,3}', token) and skill is None:
            skill = int(token)
        else:
            raise ValueError('fire 参数无效或重复。')
    return FireRequest(mode, skill, tuple(p + adjustment for p in MODES[mode]))


def roll_fire_percentile(penalty: int) -> tuple[int, list[int]]:
    ones = random.randint(0, 9)
    tens = [random.randint(0, 9) for _ in range(abs(penalty) + 1)]
    candidates = [digit * 10 + ones or 100 for digit in tens]
    result = min(candidates) if penalty < 0 else max(candidates)
    return result, candidates
