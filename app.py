import json
import os
import re
import sys
import time
import traceback

import requests
import webview

APP_NAME = "MYAMO Translate"
# newest first; older ones are only tried if a model is unavailable for the key
MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]


def resource(name):
    # when frozen by PyInstaller, bundled files live in sys._MEIPASS
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def config_file():
    # the exe's own folder is temporary / read-only, so settings go in %APPDATA%
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "config.json")


def log_error():
    # frozen windowed apps have no console, so keep crashes in a file next to the config
    try:
        path = os.path.join(os.path.dirname(config_file()), "error.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
    except OSError:
        pass


PROMPTS = {
    "fr_en": (
        "Tu es un traducteur Discord/gaming. Traduis en anglais ABRÉGÉ style Discord : "
        "pas de phrases complètes, 6-8 mots max, argot naturel (ngl, nvm, bro, pls, idk, rn, fr). "
        "Jamais de ton scolaire. Donne 3 variantes : casual, ultra court, full gamer. "
        'JSON uniquement : {"results":[{"tag":"Discord","text":"...","note":"sens en français"},'
        '{"tag":"Short","text":"...","note":"..."},{"tag":"Gamer","text":"...","note":"..."}]}'
    ),
    "fr_ru": (
        "Tu es un traducteur Discord/gaming russe. Traduis en russe ABRÉGÉ style Discord/Telegram, "
        "argot naturel (бро, ку, уд, норм, пж, го, имхо). Jamais de ton formel, 6-8 mots max. "
        "Donne 3 variantes : casual, ultra court, full gamer. "
        'JSON uniquement : {"results":[{"tag":"Discord RU","text":"...","note":"sens en français"},'
        '{"tag":"Short RU","text":"...","note":"..."},{"tag":"Gamer RU","text":"...","note":"..."}]}'
    ),
    "auto_fr": (
        "Traduis ce message (anglais ou russe, souvent de l'argot gaming) en français naturel et court. "
        "Explique l'argot en note si besoin. "
        'JSON uniquement : {"results":[{"tag":"FR","text":"...","note":"explication si besoin"}]}'
    ),
}


class Api:
    def __init__(self):
        self.window = None
        self.on_top = False
        self.session = requests.Session()
        self.config = self._load()

    def _load(self):
        try:
            with open(config_file(), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"api_key": ""}

    def _save(self):
        with open(config_file(), "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    # called from index.html
    def get_api_key(self):
        return self.config.get("api_key", "")

    def save_api_key(self, key):
        self.config["api_key"] = key.strip()
        self._save()
        return {"ok": True}

    def toggle_on_top(self):
        self.on_top = not self.on_top
        if self.window:
            self.window.on_top = self.on_top
        return {"on_top": self.on_top}

    def translate(self, text, mode):
        key = self.config.get("api_key", "").strip()
        if not key:
            return {"error": "Ajoute ta clé API dans les paramètres (engrenage en haut à droite)."}
        if not text.strip():
            return {"error": "Écris un texte à traduire."}

        prompt = f"{PROMPTS.get(mode, PROMPTS['auto_fr'])}\n\nMessage :\n{text}"
        last_error = "Erreur inconnue."

        for model in MODELS:
            if key.startswith("AQ."):
                url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            config = {
                "temperature": 0.7,
                "maxOutputTokens": 350,
                "responseMimeType": "application/json",
            }
            if model.startswith("gemini-2.5"):
                config["thinkingConfig"] = {"thinkingBudget": 0}
            body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}

            try:
                r = self.session.post(url, params={"key": key}, json=body, timeout=(5, 10))
                if r.status_code == 404:
                    last_error = f"Modèle {model} indisponible."
                    continue
                if r.status_code in (429, 500, 503):
                    # overloaded or rate limited: pause briefly, then try the next model
                    last_error = "Les serveurs de Google sont surchargés, réessaie dans quelques secondes."
                    time.sleep(1.5)
                    continue
                if r.status_code != 200:
                    try:
                        msg = r.json()["error"]["message"]
                    except (ValueError, KeyError):
                        msg = r.text[:200]
                    if r.status_code in (400, 403):
                        msg += " (clé invalide ? Utilise une clé AIza... depuis aistudio.google.com/apikey)"
                    return {"error": f"Erreur API {r.status_code} : {msg}"}

                raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                results = json.loads(raw).get("results", [])
                if not results:
                    return {"error": "Réponse vide, réessaie."}
                return {"ok": True, "results": results}
            except requests.exceptions.Timeout:
                last_error = "Timeout, vérifie ta connexion."
                continue
            except requests.exceptions.RequestException:
                return {"error": "Pas de connexion à l'API."}
            except (ValueError, KeyError, IndexError):
                return {"error": "Réponse illisible de l'API, réessaie."}
            except Exception as exc:
                log_error()
                return {"error": f"Erreur interne : {exc!r}"}

        return {"error": last_error}


if __name__ == "__main__":
    api = Api()
    api.window = webview.create_window(
        APP_NAME,
        url=resource("index.html"),
        js_api=api,
        width=500,
        height=760,
        min_size=(400, 580),
        background_color="#060403",
    )
    webview.start(http_server=True)