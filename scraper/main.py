import os
import time
import shutil
import csv
import json
import calendar
import logging
from datetime import date
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
# AJOUT : Import du Service pour définir le chemin du driver
from selenium.webdriver.chrome.service import Service 
import paho.mqtt.client as mqtt
import glob
import threading

# --- Configuration logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

# --- Chargement des variables d'environnement ---
logging.info("🔧 Chargement de la configuration…")
load_dotenv()

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT") or 1883)
MQTT_TOPIC_BASE = os.getenv("MQTT_TOPIC_BASE")
MQTT_RETAIN = os.getenv("MQTT_RETAIN", "true").lower() in ["1", "true", "yes"]
FORCE_START_DATE = os.getenv("FORCE_START_DATE")

MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

if not LOGIN or not PASSWORD:
    raise ValueError("❌ LOGIN ou PASSWORD manquant dans .env")
if not MQTT_HOST or not MQTT_TOPIC_BASE:
    raise ValueError("❌ MQTT_HOST ou MQTT_TOPIC_BASE manquant dans .env")

# MODIFICATION : Utilisation de /data pour la persistance Home Assistant
APP_DIR = "/data"
DOWNLOADED_FILE_PATH   = os.path.join(APP_DIR, "export.csv")
INTERMEDIATE_FILE_PATH = os.path.join(APP_DIR, "mes_consommations.csv")
FILTERED_FILE_PATH     = os.path.join(APP_DIR, "consommation_litres.csv")
CACHE_FILE_PATH        = os.path.join(APP_DIR, "last_sent.json")

BASE_URL = "https://www.mel-ileo.fr"
LOGIN_URL = f"{BASE_URL}/connexion.aspx"
CONSUMPTION_BASE_URL = f"{BASE_URL}/espaceperso/mes-consommations.aspx"

SELENIUM_WAIT_TIMEOUT = 15
DOWNLOAD_TIMEOUT_SEC  = 60
MQTT_CONNECT_TIMEOUT  = 10

# --- Calcul des dates ---
logging.info("📅 Calcul des dates de la période de consommation…")
today = date.today()
date_debut_str = date(2025, 3, 1).strftime("%d/%m/%Y")
date_fin_str   = date(today.year, today.month,
                      calendar.monthrange(today.year, today.month)[1]
                     ).strftime("%d/%m/%Y")
download_csv_url = (f"{CONSUMPTION_BASE_URL}?ex=1"
                    f"&dateDebut={date_debut_str}&dateFin={date_fin_str}")

# --- Préparation Selenium ---
logging.info("🌐 Démarrage de Selenium et configuration du navigateur…")
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--headless")
options.add_argument("--disable-gpu")

# AJOUT CRITIQUE : Définir l'emplacement du binaire Chromium
options.binary_location = "/usr/bin/chromium-browser"

prefs = {
    "download.default_directory": APP_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
}
options.add_experimental_option("prefs", prefs)

# Création du dossier si inexistant
os.makedirs(APP_DIR, exist_ok=True)

driver = None
try:
    # AJOUT CRITIQUE : Utilisation du Service pour pointer vers chromedriver système
    # Cela empêche Selenium d'essayer de le télécharger et d'échouer sur ARM64
    service = Service(executable_path="/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, SELENIUM_WAIT_TIMEOUT)

    logging.info("🔐 Connexion à mel-ileo.fr…")
    driver.get(LOGIN_URL)

    wait.until(EC.presence_of_element_located((By.ID, "email"))).send_keys(LOGIN)
    wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD)

    try:
        cookie_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Accepter')]"))
        )
        driver.execute_script("arguments[0].click();", cookie_btn)
        logging.info("🍪 Bandeau cookies accepté.")
    except Exception:
        pass

    login_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//input[@type='submit' and @value='je me connecte']")))
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});", login_btn)
    time.sleep(0.3)
    wait.until(lambda d: login_btn.is_displayed() and login_btn.is_enabled())
    driver.execute_script("arguments[0].click();", login_btn)

    wait.until(EC.url_contains("espaceperso"))
    logging.info("✅ Connexion réussie.")

    logging.info("🧹 Nettoyage des anciens fichiers…")
    for old in [DOWNLOADED_FILE_PATH, INTERMEDIATE_FILE_PATH, FILTERED_FILE_PATH]:
        if os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass

    logging.info("🔗 URL de téléchargement : %s", download_csv_url)
    logging.info("⬇️ Téléchargement du CSV de consommation…")
    driver.get(download_csv_url)
    start = time.time()
    last_size = -1
    file_present = False
    while time.time() - start < DOWNLOAD_TIMEOUT_SEC:
        if glob.glob(os.path.join(APP_DIR, '*.crdownload')):
            time.sleep(1)
            continue
        if os.path.exists(DOWNLOADED_FILE_PATH):
            size = os.path.getsize(DOWNLOADED_FILE_PATH)
            if size > 0 and size == last_size:
                time.sleep(0.5)
                if os.path.getsize(DOWNLOADED_FILE_PATH) == size:
                    file_present = True
                    break
            elif size > last_size:
                last_size = size
                time.sleep(1)
            else:
                time.sleep(1)
        else:
            time.sleep(1)
    if not file_present:
        raise FileNotFoundError("❌ Fichier CSV non détecté.")
    logging.info("✅ Fichier téléchargé avec succès.")
finally:
    if driver:
        driver.quit()
        logging.info("🛑 Selenium fermé.")

if os.path.exists(DOWNLOADED_FILE_PATH):
    shutil.move(DOWNLOADED_FILE_PATH, INTERMEDIATE_FILE_PATH)
    logging.info("📁 Fichier déplacé pour traitement.")

# --- Filtrage du fichier CSV ---
if os.path.exists(INTERMEDIATE_FILE_PATH):
    try:
        logging.info("🧼 Nettoyage et filtrage du CSV…")
        with open(INTERMEDIATE_FILE_PATH, newline='', encoding='utf-8') as fin, \
             open(FILTERED_FILE_PATH, "w", newline='', encoding='utf-8') as fout:
            reader = csv.DictReader(fin, delimiter=';')
            writer = csv.writer(fout)
            writer.writerow(["date", "litres", "index"])
            for row in reader:
                d = row.get("date")
                l = row.get("consommation (litres)")
                i = row.get("index")
                if not d or not l or not i:
                    continue
                if l.strip() == "0":
                    continue
                writer.writerow([d, l.strip(), i.strip()])
        logging.info("✅ Fichier filtré.")
    except Exception as e:
        logging.error(f"❌ Erreur pendant le filtrage : {e}")
        FILTERED_FILE_PATH = None
else:
    FILTERED_FILE_PATH = None

# --- Fonctions cache ---
def load_last_sent():
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Erreur lecture fichier cache : {e}")
    return None

def save_last_sent(data):
    try:
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logging.warning(f"Erreur sauvegarde fichier cache : {e}")

# --- Traitement final & MQTT ---
if FILTERED_FILE_PATH and os.path.exists(FILTERED_FILE_PATH):
    logging.info("📦 Traitement des données à envoyer…")
    last_sent = load_last_sent()
    last_sent_date  = last_sent["date"]  if last_sent else None
    last_sent_index = int(last_sent["index"]) if last_sent and "index" in last_sent else -1

    all_rows, to_send, seen_dates = [], [], set()
    with open(FILTERED_FILE_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("date") and r.get("litres") and r.get("index"):
                all_rows.append({"date": r["date"],
                                 "litres": r["litres"].strip(),
                                 "index": r["index"].strip()})

    for row in sorted(all_rows, key=lambda x: x["date"]):
        d = row["date"]
        if FORCE_START_DATE and d < FORCE_START_DATE:
            continue
        if d in seen_dates:
            continue
        seen_dates.add(d)

        try:
            idx = int(row["index"])
            lit = float(row["litres"])
            if lit <= 0:
                continue
        except ValueError:
            continue

        if (last_sent_date and d <= last_sent_date) or idx <= last_sent_index:
            continue
        to_send.append(row)

    if not to_send:
        logging.info("🔁 Aucune nouvelle donnée à envoyer.")
    else:
        to_send = sorted(to_send, key=lambda x: x["date"])[-30:]
        payload = {
            "releves": [
                {
                    "date": r["date"],
                    "index": int(r["index"]),
                    "litres": float(r["litres"])
                }
                for r in to_send
            ]
        }

        logging.info(f"📡 Envoi d’un lot de {len(to_send)} relevés via MQTT…")

        client = mqtt.Client(protocol=mqtt.MQTTv5)

        if MQTT_USERNAME and MQTT_PASSWORD:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        evt = threading.Event()

        def on_connect(c, u, flags, rc, props=None):
            if rc == 0:
                evt.set()

        client.on_connect = on_connect
        client.loop_start()
        client.connect(MQTT_HOST, MQTT_PORT, 60)

        if evt.wait(timeout=MQTT_CONNECT_TIMEOUT):
            res = client.publish(
                MQTT_TOPIC_BASE,
                json.dumps(payload),
                qos=1,
                retain=MQTT_RETAIN
            )
            res.wait_for_publish()
            save_last_sent(to_send[-1])
            logging.info(f"✅ Données envoyées ({len(to_send)} relevés).")
        else:
            logging.error("⛔ Connexion MQTT échouée.")

        client.loop_stop()
        client.disconnect()
else:
    logging.warning("⚠️ Aucun fichier CSV filtré valide trouvé.")