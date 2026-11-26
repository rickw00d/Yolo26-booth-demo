"""COCO 80 類別的繁體中文名稱。"""
COCO_ZH = {
    "person": "人", "bicycle": "腳踏車", "car": "汽車", "motorcycle": "機車",
    "airplane": "飛機", "bus": "公車", "train": "火車", "truck": "卡車",
    "boat": "船", "traffic light": "紅綠燈", "fire hydrant": "消防栓",
    "stop sign": "停止標誌", "parking meter": "停車計時器", "bench": "長椅",
    "bird": "鳥", "cat": "貓", "dog": "狗", "horse": "馬", "sheep": "羊",
    "cow": "牛", "elephant": "大象", "bear": "熊", "zebra": "斑馬",
    "giraffe": "長頸鹿", "backpack": "背包", "umbrella": "雨傘",
    "handbag": "手提包", "tie": "領帶", "suitcase": "行李箱",
    "frisbee": "飛盤", "skis": "滑雪板", "snowboard": "單板滑雪板",
    "sports ball": "球", "kite": "風箏", "baseball bat": "球棒",
    "baseball glove": "棒球手套", "skateboard": "滑板", "surfboard": "衝浪板",
    "tennis racket": "網球拍", "bottle": "瓶子", "wine glass": "酒杯",
    "cup": "杯子", "fork": "叉子", "knife": "刀子", "spoon": "湯匙",
    "bowl": "碗", "banana": "香蕉", "apple": "蘋果", "sandwich": "三明治",
    "orange": "柳橙", "broccoli": "花椰菜", "carrot": "紅蘿蔔",
    "hot dog": "熱狗", "pizza": "披薩", "donut": "甜甜圈", "cake": "蛋糕",
    "chair": "椅子", "couch": "沙發", "potted plant": "盆栽", "bed": "床",
    "dining table": "桌子", "toilet": "馬桶", "tv": "電視", "laptop": "筆電",
    "mouse": "滑鼠", "remote": "遙控器", "keyboard": "鍵盤",
    "cell phone": "手機", "microwave": "微波爐", "oven": "烤箱",
    "toaster": "烤麵包機", "sink": "水槽", "refrigerator": "冰箱",
    "book": "書", "clock": "時鐘", "vase": "花瓶", "scissors": "剪刀",
    "teddy bear": "泰迪熊", "hair drier": "吹風機", "toothbrush": "牙刷",
}


def label(name: str, lang: str = "zh", extra: dict | None = None) -> str:
    """依語言回傳顯示名稱;英文直接用模型類別名稱。"""
    if lang == "en":
        return name
    return zh(name, extra)


def zh(name: str, extra: dict | None = None) -> str:
    if extra and name in extra:
        return extra[name]
    return COCO_ZH.get(name, name)
