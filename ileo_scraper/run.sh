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

# --- 2. Récupération MQTT ---
MQTT_HOST=$(bashio::services 'mqtt' 'host')
MQTT_PORT=$(bashio::services 'mqtt' 'port')
MQTT_USERNAME=$(bashio::services 'mqtt' 'username')
MQTT_PASSWORD=$(bashio::services 'mqtt' 'password')

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

# --- 4. Boucle d'exécution infinie ---
while true; do
    bashio::log.info "▶️  Lancement du scraping..."
    
    # Lancement du script python
    # On capture la sortie pour voir les erreurs dans les logs
    python3 /scraper/main.py
    
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