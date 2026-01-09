#!/usr/bin/with-contenv bashio

bashio::log.info "🚀 Démarrage du service Scraper ILEO..."

# --- 1. Récupération de la configuration ---
LOGIN=$(bashio::config 'ileo_username')
PASSWORD=$(bashio::config 'ileo_password')
CUSTOM_TOPIC=$(bashio::config 'mqtt_topic')
FREQUENCY_MIN=$(bashio::config 'frequency')

# Sécurité : Si la fréquence n'est pas définie, on met 240 minutes (4h) par défaut
if [ -z "$FREQUENCY_MIN" ]; then
    FREQUENCY_MIN=240
fi

# Conversion en secondes pour le sleep
FREQUENCY_SEC=$((FREQUENCY_MIN * 60))

# --- 2. Récupération MQTT (Sécurisée) ---
# C'est ici que l'erreur "Forbidden" se produisait. On vérifie d'abord.
if bashio::services.available "mqtt"; then
    bashio::log.info "✅ Service MQTT détecté via l'API Supervisor."
    MQTT_HOST=$(bashio::services 'mqtt' 'host')
    MQTT_PORT=$(bashio::services 'mqtt' 'port')
    MQTT_USERNAME=$(bashio::services 'mqtt' 'username')
    MQTT_PASSWORD=$(bashio::services 'mqtt' 'password')
else
    bashio::log.warning "⚠️  ATTENTION : Service MQTT non détecté par l'API Supervisor !"
    bashio::log.warning "👉 Vérifiez que 'Mosquitto Broker' est bien installé et démarré sur cette machine."
    bashio::log.warning "👉 On tente d'utiliser 'core-mosquitto' par défaut..."
    
    # Valeurs de repli pour essayer de fonctionner quand même
    MQTT_HOST="core-mosquitto"
    MQTT_PORT=1883
    MQTT_USERNAME=""
    MQTT_PASSWORD=""
fi

# --- 3. Export des variables pour Python ---
export LOGIN
export PASSWORD
export MQTT_HOST
export MQTT_PORT
export MQTT_USERNAME
export MQTT_PASSWORD
export MQTT_TOPIC_BASE="$CUSTOM_TOPIC"
export MQTT_RETAIN="true"

bashio::log.info "ℹ️  Configuration chargée :"
bashio::log.info "   - Topic MQTT : $MQTT_TOPIC_BASE"
bashio::log.info "   - Fréquence  : Toutes les $FREQUENCY_MIN minutes"
bashio::log.info "   - Cible MQTT : $MQTT_HOST:$MQTT_PORT"

# --- 4. Boucle d'exécution infinie ---
while true; do
    bashio::log.info "▶️  Lancement du scraping..."
    
    # Recherche automatique du script Python (pour éviter l'erreur 'File not found')
    if [ -f "/ileo_scraper/main.py" ]; then
        SCRIPT_PATH="/ileo_scraper/main.py"
    elif [ -f "/scraper/main.py" ]; then
        SCRIPT_PATH="/scraper/main.py"
    else
        # Fallback au cas où (souvent utilisé dans les Dockerfiles simples)
        SCRIPT_PATH="/main.py"
    fi
    
    if [ ! -f "$SCRIPT_PATH" ]; then
        bashio::log.error "❌ CRITIQUE : Impossible de trouver le fichier main.py !"
        bashio::log.error "   Cherché dans : /ileo_scraper, /scraper et /"
        exit 1
    fi

    # Lancement du script python
    python3 "$SCRIPT_PATH"
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        bashio::log.info "✅ Scraping terminé avec succès."
    else
        bashio::log.error "❌ Le script Python a rencontré une erreur (Code: $EXIT_CODE)."
    fi
    
    bashio::log.info "💤 Pause de $FREQUENCY_MIN minutes..."
    
    # Pause avant la prochaine boucle
    sleep "$FREQUENCY_SEC"
done