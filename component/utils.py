import random
from faker import Faker

def generate_names(language="cn", num=5, sex=None):
    """
    批量生成随机名字，支持多语言和性别。
    """
    if language == "cn" or "中" in language or language == "zh" or language == "zh_CN":
        fake = Faker(locale="zh_CN")
    elif language == "en" or "英" in language or language == "en_GB":
        fake = Faker(locale="en_GB")
    elif language == "us" or "美" in language or language == "en_US":
        fake = Faker(locale="en_US")
    elif language == "jp" or "=日" in language or language == "ja_JP":
        fake = Faker(locale="ja_JP")
    else:
        fake = Faker()

    if sex == "男":
        names = [fake.name_male() for _ in range(num)]
    elif sex == "女":
        names = [fake.name_female() for _ in range(num)]
    else:
        names = [fake.name() for _ in range(num)]
    return names

def get_db_build(str_val, siz_val):
    """
    根据力量和体型计算DB和Build。
    """
    DB_BUILD_TABLE = [
        (64, "-2D6", -2),
        (84, "-1D6", -1),
        (124, "+0", 0),
        (164, "+1D4", 1),
        (204, "+1D6", 2),
        (999, "+2D6", 3)
    ]
    total = str_val + siz_val
    for limit, db, build in DB_BUILD_TABLE:
        if total <= limit:
            return db, build
    return "+0", 0

def roll_character():
    """
    生成一个CoC角色属性字典。
    """
    STR = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
    CON = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
    SIZ = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5
    DEX = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
    APP = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
    INT = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5
    POW = (random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5
    EDU = (random.randint(1, 6) + random.randint(1, 6) + 6) * 5

    HP = (SIZ + CON) // 10
    MP = POW // 5
    SAN = POW
    LUCK = ((random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)) * 5)
    DB, BUILD = get_db_build(STR, SIZ)
    TOTAL = STR + CON + SIZ + DEX + APP + INT + POW + EDU

    return {
        "STR": STR, "CON": CON, "SIZ": SIZ, "DEX": DEX,
        "APP": APP, "INT": INT, "POW": POW, "EDU": EDU,
        "HP": HP, "MP": MP, "SAN": SAN, "LUCK": LUCK,
        "DB": DB, "BUILD": BUILD, "TOTAL": TOTAL
    }

def format_character(data, index=1):
    """
    格式化CoC角色属性输出。
    """
    return (
        f"第 {index} 号调查员\n"
        f"力量: {data['STR']}  体质: {data['CON']}  体型: {data['SIZ']}\n"
        f"敏捷: {data['DEX']}  外貌: {data['APP']}  智力: {data['INT']}\n"
        f"意志: {data['POW']}  教育: {data['EDU']}\n"
        f"生命: {data['HP']}  魔力: {data['MP']}  理智: {data['SAN']}  幸运: {data['LUCK']}\n"
        f"DB: {data['DB']}  总和 : {data['TOTAL']} / {data['TOTAL'] + data['LUCK']}"
    )

def roll_4d6_drop_lowest():
    """
    掷4d6去最低，返回总和。
    """
    rolls = [random.randint(1, 6) for _ in range(4)]
    return sum(sorted(rolls)[1:])

def roll_dnd_character():
    """
    生成DND角色属性（六项，每项4d6去最低）。
    """
    return [roll_4d6_drop_lowest() for _ in range(6)]

def format_dnd_character(data, index=1):
    """
    格式化DND角色属性输出。
    """
    data = sorted(data, reverse=True)
    return (
        f"第 {index} 位冒险者\n"
        f"[{data[0]}, {data[1]}, {data[2]}, {data[3]}, {data[4]}, {data[5]}] → 共计 {sum(data)}"
    )