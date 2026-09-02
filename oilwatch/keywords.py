# -*- coding: utf-8 -*-
"""原油相关性关键词分组（中英双语）。

weight: 该组命中首个关键词时的基础分；同组每多命中一个词再加 1 分。
打分逻辑见 filter.score_text。维护时直接往各组 terms 里加词即可，
匹配方式为忽略大小写的子串匹配。
"""

KEYWORD_GROUPS = {
    "核心油价": {
        "weight": 3,
        "terms": [
            "crude", "brent", "wti", "opec", "opec+", "barrel", "bbl",
            "oil price", "crude oil", "west texas", "north sea",
            "原油", "油价", "布伦特", "美油", "欧佩克", "石油价格", "每桶",
        ],
    },
    "供需产量": {
        "weight": 2,
        "terms": [
            "production", "output", "supply", "output cut", "production cut",
            "voluntary cut", "shale", "permian", "drilling", "rig count",
            "spare capacity", "exports", "imports", "cargo", "pump",
            "产量", "减产", "供给", "供应", "出口", "进口", "页岩油",
            "钻机", "产能", "增产",
        ],
    },
    "库存炼厂": {
        "weight": 2,
        "terms": [
            "inventory", "inventories", "stockpile", "crude stock",
            "gasoline stock", "distillate", "eia", "api weekly",
            "refinery", "refining", "refinery runs", "throughput", "draw",
            "build", "库存", "炼厂", "炼油", "去库", "累库", "补库",
        ],
    },
    "需求消费": {
        "weight": 2,
        "terms": [
            "demand", "consumption", "jet fuel", "diesel", "gasoline demand",
            "fuel demand", "需求", "消费", "航煤", "柴油", "汽油需求",
        ],
    },
    "地缘制裁": {
        "weight": 2,
        "terms": [
            "sanction", "embargo", "price cap", "russia", "russian oil",
            "ukraine", "iran", "iranian", "saudi", "aramco", "israel",
            "middle east", "hormuz", "red sea", "houthi", "venezuela",
            "iraq", "libya", "hezbollah", "ceasefire", "golan",
            "制裁", "禁运", "俄罗斯", "伊朗", "沙特", "中东", "红海",
            "胡塞", "委内瑞拉", "地缘", "伊拉克", "利比亚",
        ],
    },
    "航运油轮": {
        "weight": 2,
        "terms": [
            "tanker", "vlcc", "suezmax", "aframax", "freight", "shipping",
            "fleet", "dark fleet", "油轮", "运费", "航运", "影子船队",
        ],
    },
    "宏观金融": {
        "weight": 1,
        "terms": [
            "dollar", "dxy", "fed ", "rate cut", "rate hike", "recession",
            "inflation", "pmi", "treasury yields", "risk-off", "central bank",
            "美元", "美联储", "加息", "降息", "衰退", "通胀", "汇率",
        ],
    },
    "天然气与成品油": {
        "weight": 1,
        "terms": [
            "natural gas", "natgas", "lng", "propane", "naphtha", "fuel oil",
            "天然气", "液化天然气",
        ],
    },
}

# 组的展示顺序（报告里按此顺序分节）
GROUP_ORDER = [
    "核心油价", "供需产量", "库存炼厂", "需求消费",
    "地缘制裁", "航运油轮", "宏观金融", "天然气与成品油",
]
