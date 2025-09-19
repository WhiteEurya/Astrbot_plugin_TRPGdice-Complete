CREATE TABLE BasicInfo (
    id INT NOT NULL,     -- id will be set in .stv20
    QQ_id INT NOT NULL,  -- QQ_id will be fetched in .stv20
    char_name VARCHAR(50),
    generation INT CHECK (generation BETWEEN 4 AND 13),
    clan INT CHECK (clan BETWEEN 1 AND 15),
    char_concept VARCHAR(50),
    demeanor INT,   -- see "Trait"
    nature INT,     -- see "Trait"
    PRIMARY KEY (id)
);

CREATE TABLE ClanName (
    clan INT NOT NULL CHECK (clan BETWEEN 1 AND 15),
    clan_str VARCHAR(20),
    clan_alias VARCHAR(20),
    PRIMARY KEY (clan)
);
INSERT INTO ClanName(clan, clan_str, clan_alias) VALUES 
    (1, "阿刹迈", "哈基姆圣裔"),
    (2, "布鲁赫", "布鲁贾"),
    (3, "塞特信徒", "塞特之子"),
    (4, "冈格罗", "冈格罗"),
    (5, "乔凡尼", "乔瓦尼"),
    (6, "勒森魃", "勒森布拉"),
    (7, "末卡维", "迈卡维安"),
    (8, "诺斯费拉图", "诺斯费拉图"),
    (9, "雷伏诺", "雷夫诺"),
    (10, "妥瑞朵", "托瑞多"),
    (11, "棘秘魑", "茨密希"),
    (12, "睿魔尔", "特雷米尔"),
    (13, "梵卓", "梵卓"),
    (14, "劣族", "弃子"),
    (15, "其他血系", "其他氏族")
;

