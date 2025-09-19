import os
import sqlite3

from .output import get_output

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

GREAT_SF_RULE_DEFAULT = 2
GREAT_SF_RULE_STR = ["", "严格规则", "COC7版规则", "阶段性规则", "宽松规则"]

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  COC great success/failure rule.                                          #
#  -- 1: strict rule.                                                       #
#        1 => great success, 100 => great failure                           #
#  -- 2: official COC7th rule (default, recommended).                       #
#        for skills < 50:                                                   #
#            1 => great success, 96~100 => great failure                    #
#        for skills >= 50:                                                  #
#            1 => great success, 96~100 => great failure                    #
#  -- 3: phased rule (recommended).                                         #
#        for skills < 50:                                                   #
#            1 => great success, 96~100 => great failure                    #
#        for skills >= 50:                                                  #
#            1~5 => great success, 100 => great failure                     #
#  -- 4: loose rule.                                                        #
#        1~min(5, skill level) => great success, 96~100 => great failure    #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
GLOBAL_SET = True

def coc_rule_init():
    '''
    Create table of cocrule.db
    Args:
        None.
    Returns:
        None.
    '''
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/../data/cocrule.db")
    csr = ruledb.cursor()
    csr.execute('CREATE TABLE IF NOT EXISTS GroupRule(GroupID VARCHAR(15) PRIMARY KEY, Rule INTEGER);')
    ruledb.commit()
    ruledb.close()

def fetch_group_rule(group:str)->int:
    '''
    Ask rule # in given group.
    Args:
        group(str): QQ group id.
    Returns:
        int: rule id, -1 for group not exist.
    '''
    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/../data/cocrule.db")
    csr = ruledb.cursor()
    
    # search for existence
    try: csr.execute(f"SELECT Rule FROM GroupRule WHERE GroupID = \"{group}\"")
    except:
        ruledb.close()
        return -1   # Selecting Failed
    res = csr.fetchone()
    return int(res)    # Exec Succeed

def great_success_range(skill_level:int, rule:int)->list:
    '''
    Ask for range of great success in current rule.
    Args:
        skill_level(int): Skill level of ra check.
    Returns:
        list: The range of great success (if first member is pos), or error info (if neg). 
    '''

    def min(a:int, b:int)->int: return a if a < b else b

    res = []
        
    # get result
    if   rule == 1 or rule == 2:
        res = range(1, 1+1)
    elif rule == 3:
        res = range(1, 1+1) if skill_level < 50 else range(1, 5+1)
    elif rule == 4:
        res = range(1, min(5, skill_level)+1)
    else:
        res = [-2, "InvalidRuleNum"]
    
    return res

def great_failure_range(skill_level:int, rule:int)->list:
    '''
    Ask for range of great failure in current rule.
    Args:
        skill_level(int): Skill level of ra check.
    Returns:
        list: The range of great failure (if first member is pos), or error info (if neg). 
    '''

    res = []
        
    # get result
    if   rule == 1:
        res = range(100, 100+1)
    elif rule == 2 or rule == 3:
        res = range(96, 100+1) if skill_level < 50 else range(100, 100+1)
    elif rule == 4:
        res = range(96, 100+1)
    else:
        res = [-2, "InvalidRuleNum"]
    
    return res

def set_great_sf_rule(rule:int, group:str)->int:
    '''
    Change rule # in given group.
    Args:
        group(str): QQ group id.
        rule(int): rule id.
    Returns:
        int: 1 for succeed, neg number for error. 
    '''

    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/../data/cocrule.db")
    csr = ruledb.cursor()

    if rule < 1 or rule > 4:
        rule = GREAT_SF_RULE_DEFAULT
    
    # search for existence
    csr.execute(f"SELECT * FROM GroupRule WHERE GroupID = \"{group}\"")
    
    res = csr.fetchone()
    if res == None:
        # create new record
        csr.execute(f"INSERT INTO GroupRule VALUES (\"{group}\", {rule});")
        
    else:
        # modify rule
        csr.execute(f"UPDATE GroupRule SET Rule = {rule} WHERE GroupID = \"{group}\";")
        
    ruledb.commit()
    ruledb.close()
    return 1    # Exec Succeed

def get_great_sf_rule(group:str)->int:
    '''
    Ask rule # in given group.
    Args:
        group(str): QQ group id.
    Returns:
        int: rule id, -1 for group not exist.
    '''
    # db connection
    ruledb = sqlite3.connect(f"{PLUGIN_DIR}/../data/cocrule.db")
    csr = ruledb.cursor()
    
    # search for existence
    try: csr.execute(f"SELECT Rule FROM GroupRule WHERE GroupID = \"{group}\"")
    except:
        ruledb.close()
        return -1   # Selecting Failed
    
    res = csr.fetchone()[0]
    return int(res)    # Exec Succeed


def modify_coc_great_sf_rule_command(group_id, command: str = " "):
    """
    Check or Modify current great success/failure rule.
    """
    coc_rule_init()

    # check command
    rule_set = 0
    if command[0] == "1":
        rule_set = 1
    elif command[0] == "2":
        rule_set = 2
    elif command[0] == "3":
        rule_set = 3
    elif command[0] == "4":
        rule_set = 4
    elif command[0] == "0":
        rule_set = GREAT_SF_RULE_DEFAULT
    else:
        rule_set = -1

    # set rule
    if rule_set > 0:
        sgsfr_res = set_great_sf_rule(rule_set, str(group_id))
        return get_output("coc_roll.set_rule", rule=GREAT_SF_RULE_STR[rule_set])
    # plain help
    else:
        res_str = (
            "setcoc帮助：\n"
            f"/setcoc 1 → {GREAT_SF_RULE_STR[1]}（大成功1，大失败100）\n"
            f"/setcoc 2 → {GREAT_SF_RULE_STR[2]}（大成功1，阶段性大失败）\n"
            f"/setcoc 3 → {GREAT_SF_RULE_STR[3]}（阶段性大成功，阶段性大失败）\n"
            f"/setcoc 4 → {GREAT_SF_RULE_STR[4]}（大成功1~5，大失败96~100）\n"
            f"/setcoc 0 → 默认规则（当前为{GREAT_SF_RULE_STR[GREAT_SF_RULE_DEFAULT]}）\n"
            f"当前规则：{GREAT_SF_RULE_STR[int(get_great_sf_rule(group_id))]}"
        )
        return res_str