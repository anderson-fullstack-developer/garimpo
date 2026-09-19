"""Listas prontas de palavras a excluir. `PHONES` é a lista de acessórios do app antigo (find_iphone11.py)."""

PHONES = [
    "capa", "coque", "hoesje", "beschermhoes", "funda", "pelicula", "vidro",
    "carregador", "chargeur", "oplader", "cargador", "cabo", "case", "etui",
    "custodia", "custodie", "hulle", "tasche", "skin", "protetor", "protector",
    "protectores", "suporte", "cordon", "correa", "bumper", "folie", "glas",
    "cover", "vitre", "verre", "carcasa", "tempered", "temperato", "protecao",
    "pelicola", "screen", "fone", "earphone", "airpods", "auriculares",
    "adaptador", "adaptateur", "cable", "cavo", "cavi", "pecas", "peca",
    "ecran", "ecrans", "scocca", "manette", "casse", "cassado", "quebrado",
    "a remplacer", "remplacer", "avariado", "defeito", "reparar", "reparation",
    "riparazione", "hs", "caja", "cajas", "boite", "vazia", "vazio", "vacia",
    "vacio", "vide", "cuffie", "cuffiette", "glace", "cristal", "templado",
    "wallet", "scatola", "adattatore", "adattatori",
]  # fmt: skip

CONSOLES_GAMES = [
    "controle", "comando", "manette", "mando", "joystick", "cabo", "cable", "capa", "case",
    "suporte", "soporte", "support", "carregador", "dock", "skin", "vazio", "vazia",
    "avariado", "pecas", "peca",
]  # fmt: skip

AUDIO_VIDEO = [
    "estojo", "case", "capa", "cabo", "cable", "almofada", "tampa", "pecas", "peca",
    "avariado", "defeito", "vazio", "vazia",
]  # fmt: skip

PRESETS = [
    {"id": "PHONES", "label": "Telemóveis / iPhones", "words": PHONES},
    {"id": "CONSOLES_GAMES", "label": "Consolas e jogos", "words": CONSOLES_GAMES},
    {"id": "AUDIO_VIDEO", "label": "Áudio e vídeo", "words": AUDIO_VIDEO},
]
